import React, { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { addDatasetPath, csvBenchmarksPath, submittoleaderboardPath } from "../../constants/RouteConstants";

const API_BASE = process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || process.env.REACT_APP_BACK_END_HOST || "http://localhost:5001";

const Evaluations = () => {
  const [error, setError] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  // Fetch dynamic leaderboard data
  useEffect(() => {
    const fetchLeaderboardData = async () => {
      try {
        setLoading(true);
        // Fetch dataset info to enrich cards (url/task/metric/size)
        const metaRes = await axios.get(`${API_BASE}/public/datasets`);
        const meta = {};
        if (metaRes.data?.success && Array.isArray(metaRes.data.datasets)) {
          metaRes.data.datasets.forEach(d => { meta[d.name] = d; });
        }
        const response = await axios.get(`${API_BASE}/public/get_leaderboard`);

        if (response.data.success && response.data.leaderboard) {
          // Group submissions by dataset and metric
          const groupedData = {};
          response.data.leaderboard.forEach(submission => {
            const key = submission.dataset_name;
            const metaRow = meta[key] || {};
            const displayName = key;

            if (!groupedData[key]) {
              groupedData[key] = {
                name: displayName,
                url: metaRow.url,
                task_type: submission.task_type || metaRow.task_type,
                evaluation_metric: submission.evaluation_metric || metaRow.evaluation_metric,
                models: []
              };
            }
            groupedData[key].models.push({
              model: submission.model_name,
              score: submission.score,
              updated: new Date(submission.submitted_at).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
            });
          });

          // Sort models by score (descending) and assign ranks
          Object.keys(groupedData).forEach(key => {
            groupedData[key].models.sort((a, b) => b.score - a.score);
            groupedData[key].models = groupedData[key].models.map((model, index) => ({
              ...model,
              rank: index + 1
            }));
          });

          const datasetsArray = Object.values(groupedData);

          setDatasets(datasetsArray);
          setError(null);
        } else {
          setDatasets([]);
          setError(null);
        }
      } catch (err) {
        setError(`Failed to load leaderboard data: ${err.message}`);
      }
      finally {
        setLoading(false);
      }
    };

    fetchLeaderboardData();
  }, []);

  const filteredDatasets = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return datasets;
    return datasets.filter(d => {
      const inHeader = (d.name || '').toLowerCase().includes(q) || (d.task_type || '').toLowerCase().includes(q) || (d.evaluation_metric || '').toLowerCase().includes(q);
      const inModels = (d.models || []).some(m => (m.model || '').toLowerCase().includes(q));
      return inHeader || inModels;
    });
  }, [datasets, query]);

  return (
    <section className="bg-[#111827] min-h-screen py-10 px-4 text-gray-100">
      <div className="text-center mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-[#defe47] mb-3">Live Results</div>
        <h1 className="text-4xl sm:text-5xl font-extrabold bg-gradient-to-r from-[#defe47] to-[#28b2fb] bg-clip-text text-transparent mb-4">
          Evaluation Leaderboard
        </h1>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-6">
          <button
            className="px-6 py-2 rounded-md border border-[#defe47] bg-[#defe47] text-black font-semibold hover:bg-[#28b2fb] transition"
            onClick={() => navigate("/")}
          >
            Main Leaderboard
          </button>
          <button
            className="px-6 py-2 rounded-md border border-[#defe47]/60 text-[#defe47] hover:bg-[#defe47]/10 transition"
            onClick={() => navigate(submittoleaderboardPath)}
          >
            Submit Model
          </button>
          <button
            className="px-6 py-2 rounded-md border border-[#defe47]/60 text-[#defe47] hover:bg-[#defe47]/10 transition"
            onClick={() => navigate(addDatasetPath)}
          >
            Add Dataset
          </button>
          <button
            className="px-6 py-2 rounded-md border border-[#defe47]/60 text-[#defe47] hover:bg-[#defe47]/10 transition"
            onClick={() => navigate(csvBenchmarksPath)}
          >
            Run Benchmarks
          </button>
        </div>
        <div className="max-w-xl mx-auto mt-2">
          <input
            type="text"
            placeholder="Search by dataset, model, task, or metric"
            value={query}
            onChange={(e)=>setQuery(e.target.value)}
            className="w-full px-4 py-2 rounded-md bg-gray-950 border border-gray-800 text-gray-200 focus:outline-none focus:border-[#defe47]/70"
          />
        </div>
      </div>

      {loading ? (
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-6">
          {[...Array(4)].map((_,i)=>(
            <div key={i} className="bg-gray-950 p-6 rounded-lg shadow-md border border-gray-800 animate-pulse">
              <div className="h-6 bg-gray-800 rounded w-2/3 mb-3" />
              <div className="h-4 bg-gray-800 rounded w-1/3 mb-6" />
              {[...Array(3)].map((__,j)=>(<div key={j} className="h-12 bg-gray-800 rounded mb-2" />))}
            </div>
          ))}
        </div>
      ) : (
      <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-6">
        {filteredDatasets.map((dataset, i) => (
          <div key={i} className="bg-gray-950 p-6 rounded-lg shadow-md border border-gray-800 hover:border-[#defe47]/50 transition-colors">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xl font-semibold text-[#defe47]">{dataset.name}</h2>
              <span className="text-xs text-gray-300 border border-gray-700 rounded-md px-2 py-0.5">{dataset.task_type || '—'} / {dataset.evaluation_metric || '—'}</span>
            </div>
            <div className="flex items-center gap-3 mb-2">
              {dataset.url ? (
                <a href={dataset.url} target="_blank" rel="noopener noreferrer" className="text-sm text-[#defe47] hover:underline">View Dataset</a>
              ) : null}
              <button
                className="text-sm text-[#defe47] hover:underline"
                onClick={() => navigate(`/dataset/${encodeURIComponent(dataset.name)}`)}
              >
                Details
              </button>
            </div>
            <div className="mt-2 space-y-2">
              {dataset.models.slice(0, 5).map((m) => (
                <div
                  key={m.rank}
                  className="flex items-center justify-between bg-gray-900 p-3 rounded-md border border-gray-800"
                >
                  <div>
                    <p className="font-medium text-white">
                      {m.rank}. {m.model}
                    </p>
                    <p className="text-sm text-gray-400">
                      Updated: {m.updated}
                    </p>
                  </div>
                  <div className="text-lg font-bold text-[#28b2fb]">{typeof m.score === 'number' ? m.score.toFixed(3) : m.score}</div>
                </div>
              ))}
              {dataset.models.length > 5 && (
                <div className="mt-4 text-center">
                  <button
                    onClick={() => navigate('/leaderboard', {
                      state: {
                        selectedDataset: dataset.name
                      }
                    })}
                    className="text-[#defe47] hover:text-[#28b2fb] underline text-sm font-medium transition-colors"
                  >
                    View all {dataset.models.length} models →
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      )}


      <div className="max-w-4xl mx-auto mt-16 flex flex-col items-center">
        {!loading && filteredDatasets.length === 0 && !error && (
          <div className="mt-6 text-gray-300 bg-gray-950 border border-gray-800 p-4 rounded-md w-full text-center">
            No leaderboard data yet. Add a dataset or submit model outputs to populate this view.
          </div>
        )}
        {error && (
          <div className="mt-6 text-red-500 bg-red-900 p-4 rounded-md w-full text-center">
            {error}
          </div>
        )}
      </div>
    </section>
  );
};

export default Evaluations;
