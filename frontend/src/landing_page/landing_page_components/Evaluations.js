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
      <div className="text-center mb-8 relative">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none overflow-hidden">
          <div className="w-80 h-32 rounded-full bg-[#defe47]/[0.03] blur-3xl" />
        </div>
        <div className="relative">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#defe47]/[0.07] border border-[#defe47]/20 text-xs uppercase tracking-[0.18em] text-[#defe47] mb-4 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-[#defe47] animate-pulse" />
            Live Results
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold bg-gradient-to-r from-[#defe47] via-[#b8f030] to-[#28b2fb] bg-clip-text text-transparent mb-5 leading-tight">
            Evaluation Leaderboard
          </h1>

          {/* <div className="flex flex-wrap items-center justify-center gap-2 mb-7">
            <button
              className="px-5 py-2.5 rounded-lg border border-[#defe47] bg-[#defe47] text-black font-semibold text-sm hover:bg-[#eeff5a] transition-colors active:scale-95 shadow-lg shadow-[#defe47]/10"
              onClick={() => navigate("/")}
            >
              Main Leaderboard
            </button>
            <button
              className="px-5 py-2.5 rounded-lg border border-gray-700/80 text-gray-300 text-sm font-medium hover:border-[#28b2fb]/50 hover:text-[#28b2fb] transition-colors active:scale-95"
              onClick={() => navigate(submittoleaderboardPath)}
            >
              Submit Model
            </button>
            <button
              className="px-5 py-2.5 rounded-lg border border-gray-700/80 text-gray-300 text-sm font-medium hover:border-[#28b2fb]/50 hover:text-[#28b2fb] transition-colors active:scale-95"
              onClick={() => navigate(addDatasetPath)}
            >
              Add Dataset
            </button>
            <button
              className="px-5 py-2.5 rounded-lg border border-gray-700/80 text-gray-300 text-sm font-medium hover:border-[#28b2fb]/50 hover:text-[#28b2fb] transition-colors active:scale-95"
              onClick={() => navigate(csvBenchmarksPath)}
            >
              Run Benchmarks
            </button>
          </div> */}
          <div className="max-w-xl mx-auto">
            <div className="relative">
              <svg className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z" />
              </svg>
              <input
                type="text"
                placeholder="Search by dataset, model, task, or metric…"
                value={query}
                onChange={(e)=>setQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-[#0d1421] border border-gray-800/80 text-gray-200 placeholder-gray-600 focus:outline-none focus:border-[#28b2fb]/40 transition-colors"
              />
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-5">
          {[...Array(4)].map((_,i)=>(
            <div key={i} className="bg-[#0d1421] p-6 rounded-2xl border border-gray-800/80 animate-pulse">
              <div className="h-5 bg-gray-800/80 rounded-lg w-2/3 mb-3" />
              <div className="h-3.5 bg-gray-800/60 rounded-lg w-1/3 mb-6" />
              {[...Array(3)].map((__,j)=>(<div key={j} className="h-10 bg-gray-800/50 rounded-lg mb-2" />))}
            </div>
          ))}
        </div>
      ) : (
      <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-5">
        {filteredDatasets.map((dataset, i) => (
          <div key={i} className="flex flex-col bg-[#0d1421] rounded-2xl border border-gray-800/80 hover:border-[#defe47]/25 transition-all duration-200 shadow-xl shadow-black/20 overflow-hidden">
            {/* Card header */}
            <div className="flex items-start justify-between gap-3 px-5 pt-5 pb-4 border-b border-gray-800/50">
              <div className="flex-1 min-w-0">
                <h2 className="text-base font-bold text-white leading-snug truncate" title={dataset.name}>{dataset.name}</h2>
                {(dataset.task_type || dataset.evaluation_metric) && (
                  <span className="mt-1.5 inline-flex items-center px-2 py-0.5 rounded-full bg-gray-800/80 text-[11px] text-gray-400 font-medium border border-gray-700/50">
                    {[dataset.task_type, dataset.evaluation_metric].filter(Boolean).join(' · ')}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                {dataset.url && (
                  <a
                    href={dataset.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-gray-700/60 text-gray-500 hover:text-[#defe47] hover:border-[#defe47]/30 transition-colors"
                  >
                    Dataset ↗
                  </a>
                )}
                <button
                  className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-gray-700/60 text-gray-500 hover:text-[#28b2fb] hover:border-[#28b2fb]/30 transition-colors"
                  onClick={() => navigate(`/dataset/${encodeURIComponent(dataset.name)}`)}
                >
                  Details
                </button>
              </div>
            </div>

            {/* Rankings table */}
            <div className="flex-1">
              <div className="grid grid-cols-[3rem_1fr_6rem] text-[10px] font-semibold uppercase tracking-widest text-gray-600 px-5 py-2.5 border-b border-gray-800/40">
                <div>Rank</div>
                <div>Model</div>
                <div className="text-right">Score</div>
              </div>
              <div className="divide-y divide-gray-800/30">
                {dataset.models.slice(0, 5).map((m) => {
                  const isTop = m.rank === 1;
                  const score = typeof m.score === 'number' ? m.score.toFixed(3) : m.score;
                  const rankEmoji = m.rank === 1 ? '🥇' : m.rank === 2 ? '🥈' : m.rank === 3 ? '🥉' : null;
                  return (
                    <div
                      key={m.rank}
                      className={[
                        "grid grid-cols-[3rem_1fr_6rem] items-center px-5 py-2.5 text-sm transition-colors",
                        isTop ? "bg-[#defe47]/[0.04] hover:bg-[#defe47]/[0.07]" : "hover:bg-white/[0.03]"
                      ].join(' ')}
                    >
                      <div className="flex items-center gap-1">
                        {rankEmoji
                          ? <span className="mr-0.5">{rankEmoji}</span>
                          : <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-gray-800 text-[11px] text-gray-500 tabular-nums font-mono">{m.rank}</span>
                        }
                      </div>
                      <div className={["font-medium truncate", isTop ? "text-white" : "text-gray-300"].join(' ')} title={m.model}>
                        {m.model}
                      </div>
                      <div className="text-right">
                        <span className={["tabular-nums font-semibold", isTop ? "text-[#defe47]" : m.rank === 2 ? "text-gray-100" : "text-gray-400"].join(' ')}>
                          {score}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
              {dataset.models.length > 5 && (
                <div className="px-5 py-3 border-t border-gray-800/30 text-center">
                  <button
                    onClick={() => navigate('/leaderboard', { state: { selectedDataset: dataset.name } })}
                    className="text-xs text-gray-500 hover:text-[#defe47] transition-colors font-medium"
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
          <div className="mt-6 text-gray-400 bg-[#0d1421] border border-gray-800/80 p-5 rounded-xl w-full text-center text-sm">
            No leaderboard data yet. Add a dataset or submit model outputs to populate this view.
          </div>
        )}
        {error && (
          <div className="mt-6 text-red-400 bg-red-900/20 border border-red-800/40 p-4 rounded-xl w-full text-center text-sm">
            {error}
          </div>
        )}
      </div>
    </section>
  );
};

export default Evaluations;
