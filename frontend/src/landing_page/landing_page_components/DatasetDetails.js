import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

const API_BASE = process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || 'http://localhost:5001';

const DatasetDetails = () => {
  const { name } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);
  const [metrics, setMetrics] = useState({});

  useEffect(() => {
    let ignore = false;
    const run = async () => {
      setLoading(true); setError('');
      try {
        const url = new URL(`${API_BASE}/public/dataset_details`);
        url.searchParams.set('name', name);
        const res = await fetch(url.toString());
        const json = await res.json();
        if (!res.ok || json.success !== true) throw new Error(json.error || 'Failed to fetch dataset');
        if (!ignore) setData(json);
        if (json.dataset?.task_type) {
          const metricsRes = await fetch(`${API_BASE}/api/metrics/task/${encodeURIComponent(json.dataset.task_type)}`);
          const metricsJson = await metricsRes.json();
          if (!ignore && metricsRes.ok && metricsJson.success === true) {
            setMetrics(metricsJson.metrics || {});
          }
        }
      } catch (e) {
        if (!ignore) setError(e.message || 'Error loading dataset');
      } finally {
        if (!ignore) setLoading(false);
      }
    };
    run();
    return () => { ignore = true; };
  }, [name]);

  return (
    <div className="flex flex-col items-center justify-start min-h-screen bg-gray-900 pb-24 mx-3">
      <div className="w-full max-w-5xl mt-6 flex justify-end">
        <button onClick={() => navigate('/')} className="px-3 py-1 rounded-md border border-gray-700 text-gray-300 hover:bg-gray-700/40">× Close</button>
      </div>
      <div className="w-full max-w-5xl bg-gray-900/70 rounded-xl border border-gray-800 p-6 mt-2">
        {loading ? (
          <div className="text-gray-300">Loading…</div>
        ) : error ? (
          <div className="text-red-400">{error}</div>
        ) : data ? (
          <div>
            <h1 className="text-2xl font-bold text-white">{data.dataset.name}</h1>
            <div className="text-sm text-gray-300 mt-1">Task: {data.dataset.task_type} | Metric: {data.dataset.evaluation_metric}</div>
            {data.dataset.url && (
              <div className="mt-2"><a href={data.dataset.url} className="text-[#defe47] underline" target="_blank" rel="noreferrer">Dataset URL</a></div>
            )}
            {data.dataset.description && (
              <p className="text-gray-200 mt-3">{data.dataset.description}</p>
            )}
            {Array.isArray(data.dataset.examples) && data.dataset.examples.length > 0 && (
              <div className="mt-4">
                <div className="text-white font-semibold mb-2">Examples</div>
                <ul className="list-disc pl-5 text-gray-200">
                  {data.dataset.examples.map((ex, i) => (<li key={i}>{String(ex)}</li>))}
                </ul>
              </div>
            )}
            {Object.keys(metrics).length > 0 && (
              <div className="mt-6">
                <div className="text-white font-semibold mb-2">Metrics</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {Object.entries(metrics).map(([key, metric]) => (
                    <div key={key} className="border border-gray-800 rounded-lg p-3 bg-gray-950">
                      <div className="text-[#EDDC8F] font-semibold">{metric.name || key}</div>
                      <div className="text-gray-300 text-sm mt-1">{metric.description}</div>
                      <div className="text-gray-500 text-xs mt-2">{metric.range}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="mt-6">
              <div className="text-white font-semibold mb-2">Top Models</div>
              {data.top_models && data.top_models.length ? (
                <div className="divide-y divide-gray-800 border border-gray-800 rounded-lg overflow-hidden">
                  <div className="grid grid-cols-3 text-white font-semibold text-center bg-gray-900/80 px-3 py-2">
                    <div>Model</div><div>Score</div><div>Updated</div>
                  </div>
                  {data.top_models.map((m, i) => (
                    <div key={i} className="grid grid-cols-3 text-center px-3 py-2 text-white">
                      <div className="truncate" title={m.model}>{m.model}</div>
                      <div>{typeof m.score === 'number' ? (m.score < 1 ? m.score.toFixed(3) : m.score.toFixed(2)) : m.score}</div>
                      <div className="text-gray-300">{m.updated ? new Date(m.updated).toLocaleDateString() : ''}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-gray-400 text-sm">No submissions yet.</div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default DatasetDetails;
