import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

const API_BASE = process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || 'http://localhost:5001';

const MODEL_COLORS = [
  { border: 'border-[#defe47]/60', text: 'text-[#defe47]', bg: 'bg-[#defe47]/10', tag: 'bg-[#defe47]/20 text-[#defe47]' },
  { border: 'border-[#28b2fb]/60', text: 'text-[#28b2fb]', bg: 'bg-[#28b2fb]/10', tag: 'bg-[#28b2fb]/20 text-[#28b2fb]' },
  { border: 'border-[#f87171]/60', text: 'text-[#f87171]', bg: 'bg-[#f87171]/10', tag: 'bg-[#f87171]/20 text-[#f87171]' },
  { border: 'border-[#a78bfa]/60', text: 'text-[#a78bfa]', bg: 'bg-[#a78bfa]/10', tag: 'bg-[#a78bfa]/20 text-[#a78bfa]' },
  { border: 'border-[#34d399]/60', text: 'text-[#34d399]', bg: 'bg-[#34d399]/10', tag: 'bg-[#34d399]/20 text-[#34d399]' },
];

function fmt(score) {
  if (typeof score !== 'number' || Number.isNaN(score)) return '—';
  return score < 1 ? score.toFixed(4) : score.toFixed(2);
}

function humanizeMetric(m) {
  if (!m) return '';
  return m.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function ScoreBar({ score, maxScore }) {
  if (typeof score !== 'number' || maxScore === 0) return null;
  const pct = Math.min(100, (score / maxScore) * 100);
  return (
    <div className="w-full h-1 bg-gray-800 rounded-full mt-1.5 overflow-hidden">
      <div className="h-full rounded-full bg-[#defe47]/60" style={{ width: `${pct}%` }} />
    </div>
  );
}

function ModelAutocomplete({ value, index, availableModels, color, onChange, onRemove, canRemove }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const ref = useRef(null);

  useEffect(() => { setQuery(value); }, [value]);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const filtered = availableModels.filter(n =>
    !query || n.toLowerCase().includes(query.toLowerCase())
  ).slice(0, 12);

  return (
    <div ref={ref} className="relative">
      <div className={`flex items-center gap-1.5 rounded-lg border ${color.border} bg-gray-900/80 px-3 py-2`}>
        <span className={`text-[10px] font-bold ${color.text} shrink-0 mr-1`}>M{index + 1}</span>
        <input
          type="text"
          value={query}
          placeholder="Type model name…"
          onChange={e => {
            setQuery(e.target.value);
            onChange(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          className="bg-transparent text-white text-sm w-52 focus:outline-none placeholder-gray-600"
        />
        {canRemove && (
          <button onClick={onRemove} className="text-gray-600 hover:text-red-400 ml-1 text-base leading-none">×</button>
        )}
      </div>
      {open && filtered.length > 0 && (
        <div className="absolute z-50 top-full mt-1 left-0 w-full bg-[#0d1421] border border-gray-700 rounded-lg shadow-xl overflow-auto max-h-52">
          {filtered.map(name => (
            <button
              key={name}
              className="w-full text-left px-3 py-2 text-sm text-gray-200 hover:bg-white/5 truncate"
              onMouseDown={e => { e.preventDefault(); setQuery(name); onChange(name); setOpen(false); }}
            >
              {name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ComparisonTable({ models, comparisons }) {
  const winCounts = Object.fromEntries(models.map(m => [m, 0]));
  const missing = Object.fromEntries(models.map(m => [m, 0]));

  for (const row of comparisons) {
    const scored = models.filter(m => row.scores[m] != null);
    if (scored.length < 2) continue;
    const best = Math.max(...scored.map(m => row.scores[m].score));
    const winners = scored.filter(m => row.scores[m].score === best);
    if (winners.length === 1) winCounts[winners[0]]++;
    models.forEach(m => { if (row.scores[m] == null) missing[m]++; });
  }

  const exactlyTwo = models.length === 2;

  return (
    <div className="bg-[#0d1421] border border-gray-800 rounded-xl overflow-hidden">
      {/* Summary bar */}
      <div className="flex flex-wrap gap-4 px-5 py-4 border-b border-gray-800/60 bg-gray-950/40">
        {models.map((m, i) => (
          <div key={m} className="flex items-center gap-2">
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${MODEL_COLORS[i % MODEL_COLORS.length].tag}`}>M{i + 1}</span>
            <span className="text-sm text-white truncate max-w-[14rem]" title={m}>{m}</span>
            <span className={`text-xs font-semibold ${MODEL_COLORS[i % MODEL_COLORS.length].text}`}>
              {winCounts[m]} win{winCounts[m] !== 1 ? 's' : ''}
            </span>
          </div>
        ))}
        <span className="text-xs text-gray-500 ml-auto self-center">{comparisons.length} shared dataset{comparisons.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-800/50">
              <th className="text-left px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-gray-500 w-48 min-w-[11rem]">Dataset</th>
              <th className="text-left px-3 py-3 text-[11px] font-semibold uppercase tracking-wider text-gray-500 w-24">Metric</th>
              {models.map((m, i) => (
                <th key={m} className="text-right px-4 py-3 text-[11px] font-semibold uppercase tracking-wider min-w-[7rem]">
                  <span className={`${MODEL_COLORS[i % MODEL_COLORS.length].text}`}>M{i + 1}</span>
                </th>
              ))}
              {exactlyTwo && (
                <th className="text-right px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-gray-500 w-20">Δ</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/30">
            {comparisons.map((row, ri) => {
              const scored = models.filter(m => row.scores[m] != null);
              const maxScore = scored.length ? Math.max(...scored.map(m => row.scores[m].score)) : 0;
              const bestScore = maxScore;
              const delta = exactlyTwo && row.scores[models[0]] != null && row.scores[models[1]] != null
                ? row.scores[models[0]].score - row.scores[models[1]].score
                : null;

              return (
                <tr key={ri} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-5 py-3 text-gray-200 font-medium max-w-[14rem]">
                    <div className="truncate" title={row.dataset_name}>{row.dataset_name}</div>
                    {row.task_type && (
                      <div className="text-[10px] text-gray-600 mt-0.5 truncate">{row.task_type.replace(/_/g, ' ')}</div>
                    )}
                  </td>
                  <td className="px-3 py-3 text-gray-500 text-xs whitespace-nowrap">
                    {humanizeMetric(row.evaluation_metric) || '—'}
                  </td>
                  {models.map((m, mi) => {
                    const entry = row.scores[m];
                    const score = entry?.score;
                    const isWinner = scored.length >= 2 && typeof score === 'number' && score === bestScore;
                    const color = MODEL_COLORS[mi % MODEL_COLORS.length];
                    return (
                      <td key={m} className={`px-4 py-3 text-right tabular-nums`}>
                        {entry == null ? (
                          <span className="text-gray-700">—</span>
                        ) : (
                          <div className={`inline-flex flex-col items-end ${isWinner ? color.text + ' font-bold' : 'text-gray-300'}`}>
                            <span>{fmt(score)}</span>
                            <ScoreBar score={score} maxScore={maxScore} />
                          </div>
                        )}
                      </td>
                    );
                  })}
                  {exactlyTwo && (
                    <td className="px-4 py-3 text-right tabular-nums text-xs">
                      {delta == null ? (
                        <span className="text-gray-700">—</span>
                      ) : delta > 0.0001 ? (
                        <span className="text-[#defe47]">+{fmt(Math.abs(delta))}</span>
                      ) : delta < -0.0001 ? (
                        <span className="text-[#28b2fb]">−{fmt(Math.abs(delta))}</span>
                      ) : (
                        <span className="text-gray-600">tie</span>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const ModelComparison = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const initModels = () => {
    const p = searchParams.get('models');
    const parsed = p ? p.split(',').map(s => s.trim()).filter(Boolean) : [];
    if (parsed.length >= 2) return parsed;
    return ['', ''];
  };

  const [selectedModels, setSelectedModels] = useState(initModels);
  const [availableModels, setAvailableModels] = useState([]);
  const [comparisons, setComparisons] = useState([]);
  const [resultModels, setResultModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/public/model_names`)
      .then(r => r.json())
      .then(d => { if (d.success) setAvailableModels(d.models || []); })
      .catch(() => {});
  }, []);

  const compare = useCallback(async (models) => {
    const valid = models.filter(Boolean);
    if (valid.length < 2) return;
    setLoading(true);
    setError('');
    setHasSearched(true);
    try {
      const url = new URL(`${API_BASE}/public/compare_models`);
      url.searchParams.set('models', valid.join(','));
      const res = await fetch(url.toString());
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || 'Comparison failed');
      setComparisons(data.comparisons || []);
      setResultModels(data.models || valid);
    } catch (e) {
      setError(e.message || 'Error loading comparison');
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-run if URL has models
  useEffect(() => {
    const p = searchParams.get('models');
    const parsed = p ? p.split(',').map(s => s.trim()).filter(Boolean) : [];
    if (parsed.length >= 2) compare(parsed);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCompare = () => {
    const valid = selectedModels.filter(Boolean);
    if (valid.length < 2) return;
    setSearchParams({ models: valid.join(',') });
    compare(selectedModels);
  };

  const updateModel = (i, val) => {
    setSelectedModels(prev => { const n = [...prev]; n[i] = val; return n; });
  };

  const removeModel = (i) => {
    setSelectedModels(prev => prev.filter((_, j) => j !== i));
  };

  const addModel = () => setSelectedModels(prev => [...prev, '']);

  const validCount = selectedModels.filter(Boolean).length;

  return (
    <div className="flex flex-col items-center min-h-screen bg-[#111827] pb-24 px-4 text-gray-100">
      <div className="w-full max-w-5xl mt-8">

        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="text-gray-500 hover:text-gray-200 text-sm transition-colors"
          >
            ← Leaderboard
          </button>
          <span className="text-gray-700">/</span>
          <h1 className="text-xl font-bold text-white">Model Comparison</h1>
        </div>

        {/* Picker card */}
        <div className="bg-[#0d1421] border border-gray-800 rounded-2xl p-6 mb-6">
          <p className="text-sm text-gray-400 mb-5">
            Select 2–5 models to compare head-to-head across all datasets where both have submissions.
          </p>
          <div className="flex flex-wrap gap-3 items-start">
            {selectedModels.map((m, i) => (
              <ModelAutocomplete
                key={i}
                index={i}
                value={m}
                availableModels={availableModels}
                color={MODEL_COLORS[i % MODEL_COLORS.length]}
                onChange={val => updateModel(i, val)}
                onRemove={() => removeModel(i)}
                canRemove={selectedModels.length > 2}
              />
            ))}
            {selectedModels.length < 5 && (
              <button
                type="button"
                onClick={addModel}
                className="px-3 py-2 rounded-lg border border-dashed border-gray-700 text-gray-500 hover:text-gray-300 hover:border-gray-500 text-sm transition-colors self-start mt-0"
              >
                + Add model
              </button>
            )}
          </div>

          <div className="mt-5 flex items-center gap-3">
            <button
              type="button"
              onClick={handleCompare}
              disabled={validCount < 2 || loading}
              className="px-5 py-2 rounded-lg bg-[#defe47] text-black text-sm font-semibold hover:bg-[#e8ff70] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Comparing…' : 'Compare'}
            </button>
            {validCount < 2 && (
              <span className="text-xs text-gray-600">Select at least 2 models</span>
            )}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 rounded-lg border border-red-800/40 bg-red-900/20 px-4 py-2.5 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="text-gray-400 text-sm text-center py-16">Loading comparison…</div>
        )}

        {/* Empty state */}
        {hasSearched && !loading && !error && comparisons.length === 0 && (
          <div className="bg-[#0d1421] border border-gray-800 rounded-2xl px-6 py-16 text-center">
            <div className="text-white font-semibold mb-2">No shared datasets found</div>
            <p className="text-gray-400 text-sm">
              These models have not both been evaluated on any common dataset yet.
            </p>
          </div>
        )}

        {/* Results */}
        {!loading && comparisons.length > 0 && (
          <ComparisonTable models={resultModels} comparisons={comparisons} />
        )}

        {/* Helper: delta legend when exactly 2 models */}
        {!loading && comparisons.length > 0 && resultModels.length === 2 && (
          <div className="mt-3 flex items-center gap-4 text-xs text-gray-600 px-1">
            <span><span className="text-[#defe47]">+x.xxxx</span> = M1 wins by that margin</span>
            <span><span className="text-[#28b2fb]">−x.xxxx</span> = M2 wins by that margin</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default ModelComparison;
