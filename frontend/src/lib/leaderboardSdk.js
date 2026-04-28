// Simple SDK for the leaderboard API (browser-friendly)
const API_BASE = process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001";

function browserBearer() {
  if (typeof sessionStorage === "undefined") return "";
  return sessionStorage.getItem("lb_jwt") || "";
}

async function http(method, path, body) {
  const apiKey = process.env.REACT_APP_LEADERBOARD_API_KEY;
  const jwt = browserBearer();
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(apiKey ? { 'X-API-Key': apiKey } : {}),
      ...(jwt ? { Authorization: `Bearer ${jwt}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data?.message || data?.error || `${method} ${path} failed`;
    throw new Error(msg);
  }
  return data;
}

export const LeaderboardSDK = {
  addDataset: (payload) => http('POST', '/api/leaderboard/add_dataset', payload),
  addModel: (payload) => http('POST', '/api/leaderboard/add_model', payload),
  listDatasets: () => http('GET', '/api/leaderboard/list'),
  listPublicDatasets: () => http('GET', '/public/datasets'),
  addDatasetPublic: (payload) => http('POST', '/public/add_dataset', payload),
  importHfDataset: (payload) => http('POST', '/public/import_hf_dataset', payload),
  getLeaderboard: () => http('GET', '/public/get_leaderboard'),
  listBenchmarkCsvs: () => http('GET', '/public/benchmark_csvs'),
  listBenchmarkModels: () => http('GET', '/public/benchmark_models'),
  runCsvBenchmarks: (payload) => http('POST', '/public/run_csv_benchmarks', payload),
  getSourceSentences: (params = {}) => {
    const url = new URL(`${API_BASE}/public/get_source_sentences`);
    if (params.dataset_name) url.searchParams.set('dataset_name', params.dataset_name);
    if (params.count) url.searchParams.set('count', String(params.count));
    if (params.start_idx) url.searchParams.set('start_idx', String(params.start_idx));
    return fetch(url.toString()).then(async (res) => {
      const data = await res.json();
      if (!res.ok || data.success !== true) {
        throw new Error(data?.error || 'Failed to fetch source sentences');
      }
      return data;
    });
  },
  submitModel: (payload) => http('POST', '/public/submit_model', payload),
};

export default LeaderboardSDK;
