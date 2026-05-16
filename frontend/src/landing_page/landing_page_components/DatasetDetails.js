import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import TaskAdvancedMetricsPanel from './TaskAdvancedMetricsPanel';

const API_BASE = process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || 'http://localhost:5001';

function MetricCard({ metricKey, metric }) {
  if (!metric || typeof metric !== 'object') return null;
  return (
    <div className="border border-gray-800 rounded-lg p-3 bg-gray-950">
      <div className="text-[#EDDC8F] font-semibold">{metric.name || metricKey}</div>
      {metric.formula && (
        <div className="text-gray-200 text-sm mt-2 font-mono bg-black/30 rounded px-2 py-1 border border-gray-800">
          {metric.formula}
        </div>
      )}
      <div className="text-gray-300 text-sm mt-2">{metric.description}</div>
      {metric.range && (
        <div className="text-gray-500 text-xs mt-2">Range: {metric.range}</div>
      )}
      {metric.when_to_use && (
        <div className="text-gray-500 text-xs mt-2">When to use: {metric.when_to_use}</div>
      )}
    </div>
  );
}

const DatasetDetails = () => {
  const { name } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);

  const decodedName = React.useMemo(() => {
    if (!name) return '';
    try {
      return decodeURIComponent(name);
    } catch {
      return name;
    }
  }, [name]);

  useEffect(() => {
    let ignore = false;
    const run = async () => {
      setLoading(true); setError('');
      try {
        const url = new URL(`${API_BASE}/public/dataset_details`);
        url.searchParams.set('name', decodedName);
        const res = await fetch(url.toString());
        const json = await res.json();
        if (!res.ok || json.success !== true) throw new Error(json.error || 'Failed to fetch dataset');
        if (!ignore) setData(json);
      } catch (e) {
        // Fall back to navigation state for static-only datasets
        const fallback = location.state;
        if (fallback && fallback.name) {
          if (!ignore) setData({
            dataset: {
              name: fallback.name,
              task_type: fallback.task_type || '',
              task_type_normalized: fallback.task_type || '',
              evaluation_metric: fallback.evaluation_metric || '',
              url: fallback.url,
              description: fallback.description,
              primary_metric_documentation: {},
              recommended_metrics_for_task: {},
            },
            top_models: (fallback.models || []).map(m => ({
              model: m.model,
              score: m.score,
              updated: m.updated,
            })),
          });
        } else {
          if (!ignore) setError(e.message || 'Error loading dataset');
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    };
    if (decodedName) run();
    else setLoading(false);
    return () => { ignore = true; };
  }, [decodedName, location.state]);

  const ds = data?.dataset;
  const primaryDoc = ds?.primary_metric_documentation;
  const recommended = ds?.recommended_metrics_for_task || {};
  const primaryKey = (ds?.evaluation_metric || '').toLowerCase().trim();

  return (
    <div className="flex flex-col items-center justify-start min-h-screen bg-gray-900 pb-24 mx-3">
      <div className="w-full max-w-5xl mt-6 flex justify-end">
        <button type="button" onClick={() => navigate('/')} className="px-3 py-1 rounded-md border border-gray-700 text-gray-300 hover:bg-gray-700/40">× Close</button>
      </div>
      <div className="w-full max-w-5xl bg-gray-900/70 rounded-xl border border-gray-800 p-6 mt-2">
        {loading ? (
          <div className="text-gray-300">Loading…</div>
        ) : error ? (
          <div className="text-red-400">{error}</div>
        ) : ds ? (
          <div>
            <h1 className="text-2xl font-bold text-white">{ds.name}</h1>
            <div className="text-sm text-gray-300 mt-2 space-y-1">
              <div>
                Task type: <span className="text-white">{ds.task_type}</span>
                {ds.task_type_normalized && ds.task_type_normalized !== ds.task_type && (
                  <span className="text-gray-500"> (normalized for metrics: {ds.task_type_normalized})</span>
                )}
              </div>
              <div>
                Leaderboard ranking metric:{' '}
                <span className="text-[#defe47] font-semibold">{ds.evaluation_metric || '—'}</span>
                <span className="text-gray-500 text-xs ml-2">The table below sorts by this primary score.</span>
              </div>
            </div>
            {ds.url && (
              <div className="mt-2"><a href={ds.url} className="text-[#defe47] underline" target="_blank" rel="noreferrer">Dataset URL</a></div>
            )}
            {ds.description && (
              <p className="text-gray-200 mt-3">{ds.description}</p>
            )}
            {typeof ds.size === 'number' && (
              <p className="text-gray-400 text-sm mt-2">Benchmark size: {ds.size} items</p>
            )}

            {primaryDoc && Object.keys(primaryDoc).length > 0 && (
              <div className="mt-6 border border-[#defe47]/20 rounded-xl p-4 bg-black/20">
                <div className="text-white font-semibold mb-2">Primary metric: how &quot;{ds.evaluation_metric}&quot; is defined</div>
                <MetricCard metricKey={primaryKey} metric={primaryDoc} />
              </div>
            )}

            {Object.keys(recommended).length > 0 && (
              <div className="mt-6">
                <div className="text-white font-semibold mb-2">Metrics commonly used for this task type</div>
                <p className="text-gray-400 text-xs mb-3">
                  Your leaderboard row may include extra fields in <code className="text-gray-300">detailed_scores</code> from evaluation;
                  the ranking column uses the primary metric above.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {Object.entries(recommended).map(([key, metric]) => (
                    <MetricCard key={key} metricKey={key} metric={metric} />
                  ))}
                </div>
              </div>
            )}

            {ds.task_type && (
              <div className="mt-8 border border-gray-800 rounded-xl overflow-hidden">
                <div className="px-4 py-3 bg-gray-950/80 border-b border-gray-800">
                  <div className="text-white font-semibold text-sm">Full metric glossary (this task)</div>
                  <p className="text-gray-500 text-xs mt-1">
                    Every advanced metric we surface for <span className="text-gray-300">{ds.task_type}</span>, with how it is computed.
                    Per-model cells appear when evaluation returns those keys in <code className="text-gray-400">detailed_scores</code>.
                  </p>
                </div>
                <TaskAdvancedMetricsPanel apiBase={API_BASE} taskType={ds.task_type} models={[]} className="border-t-0 bg-transparent px-2 pb-4" />
              </div>
            )}

            {Array.isArray(ds.examples) && ds.examples.length > 0 && (
              <div className="mt-6">
                <div className="text-white font-semibold mb-2">Examples</div>
                <ul className="list-disc pl-5 text-gray-200">
                  {ds.examples.map((ex, i) => (<li key={i}>{String(ex)}</li>))}
                </ul>
              </div>
            )}

            <div className="mt-6">
              <div className="text-white font-semibold mb-2">
                Top models (by {ds.evaluation_metric || 'primary score'})
              </div>
              {data.top_models && data.top_models.length ? (
                <div className="divide-y divide-gray-800 border border-gray-800 rounded-lg overflow-hidden">
                  <div className="grid grid-cols-3 text-white font-semibold text-center bg-gray-900/80 px-3 py-2 text-sm">
                    <div>Model</div>
                    <div>{ds.evaluation_metric || 'Score'}</div>
                    <div>Submitted</div>
                  </div>
                  {data.top_models.map((m, i) => (
                    <div key={i} className="grid grid-cols-3 text-center px-3 py-2 text-white text-sm">
                      <div className="truncate" title={m.model}>{m.model}</div>
                      <div className="tabular-nums">
                        {typeof m.score === 'number' ? (m.score < 1 ? m.score.toFixed(4) : m.score.toFixed(2)) : m.score}
                      </div>
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
