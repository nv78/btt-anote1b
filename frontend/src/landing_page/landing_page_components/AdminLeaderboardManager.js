import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LeaderboardSDK } from '../../lib/leaderboardSdk';
import { adminSubmissionsPath, adminDatasetRequestsPath } from '../../constants/RouteConstants';

const API_BASE = process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || 'http://localhost:5001';

const AdminLeaderboardManager = () => {
  const navigate = useNavigate();
  const [dsForm, setDsForm] = useState({ name: '', url: '', task_type: '', description: '' });
  const [dsSubmitting, setDsSubmitting] = useState(false);
  const [dsResult, setDsResult] = useState(null);
  const [dsError, setDsError] = useState('');

  const [datasets, setDatasets] = useState([]);
  const [modelForm, setModelForm] = useState({ dataset_name: '', model: '', rank: '', score: '', ci: '', updated: '' });
  const [modelSubmitting, setModelSubmitting] = useState(false);
  const [modelResult, setModelResult] = useState(null);
  const [modelError, setModelError] = useState('');

  const resetDatasetForm = () => setDsForm({ name: '', url: '', task_type: '', description: '' });
  const resetModelForm = () => setModelForm({ dataset_name: '', model: '', rank: '', score: '', ci: '', updated: '' });

  // ── Quota usage panel ────────────────────────────────────────────────────
  const [quotaData, setQuotaData] = useState(null);
  const [quotaLoading, setQuotaLoading] = useState(false);
  const [quotaError, setQuotaError] = useState('');

  const loadQuotaUsage = async () => {
    if (!adminKey.trim()) return;
    setQuotaLoading(true); setQuotaError('');
    try {
      const res = await fetch(`${API_BASE}/api/admin/quota_usage`, {
        headers: { 'X-Admin-Key': adminKey.trim() },
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || 'Failed');
      setQuotaData(data);
    } catch (e) {
      setQuotaError(e.message || 'Error loading quota data');
    } finally {
      setQuotaLoading(false);
    }
  };

  // ── Questions-public panel ────────────────────────────────────────────────
  const [adminKey, setAdminKey] = useState(() => localStorage.getItem('leaderboard_admin_key') || '');
  const [qpDatasets, setQpDatasets] = useState([]);
  const [qpLoading, setQpLoading] = useState(false);
  const [qpError, setQpError] = useState('');
  const [qpBusy, setQpBusy] = useState({});
  const [activeBusy, setActiveBusy] = useState({});

  useEffect(() => { localStorage.setItem('leaderboard_admin_key', adminKey); }, [adminKey]);

  const loadQpDatasets = async () => {
    if (!adminKey.trim()) return;
    setQpLoading(true); setQpError('');
    try {
      const res = await fetch(`${API_BASE}/public/datasets`);
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Failed');
      // Fetch questions_public state for each dataset via dataset_details
      const detailed = await Promise.all(
        (data.datasets || []).map(async (ds) => {
          try {
            const r = await fetch(`${API_BASE}/public/dataset_details?name=${encodeURIComponent(ds.name)}`);
            const d = await r.json();
            return {
              ...ds,
              questions_public: d.dataset?.questions_public !== false,
              active: d.dataset?.active !== false,
            };
          } catch {
            return { ...ds, questions_public: true, active: true };
          }
        })
      );
      setQpDatasets(detailed);
    } catch (e) {
      setQpError(e.message || 'Error loading datasets');
    } finally {
      setQpLoading(false);
    }
  };

  const toggleQuestionsPublic = async (dsName, current) => {
    setQpBusy((p) => ({ ...p, [dsName]: true }));
    try {
      const res = await fetch(`${API_BASE}/api/admin/datasets/${encodeURIComponent(dsName)}/questions_public`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Admin-Key': adminKey.trim() },
        body: JSON.stringify({ questions_public: !current }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || 'Update failed');
      setQpDatasets((prev) => prev.map((d) => d.name === dsName ? { ...d, questions_public: data.questions_public } : d));
    } catch (e) {
      setQpError(e.message || 'Toggle failed');
    } finally {
      setQpBusy((p) => ({ ...p, [dsName]: false }));
    }
  };

  const toggleActive = async (dsName, current) => {
    setActiveBusy((p) => ({ ...p, [dsName]: true }));
    try {
      const action = current ? 'deactivate' : 'activate';
      const res = await fetch(`${API_BASE}/api/admin/datasets/${encodeURIComponent(dsName)}/${action}`, {
        method: 'POST',
        headers: { 'X-Admin-Key': adminKey.trim() },
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || 'Update failed');
      setQpDatasets((prev) => prev.map((d) => d.name === dsName ? { ...d, active: data.active } : d));
    } catch (e) {
      setQpError(e.message || 'Toggle failed');
    } finally {
      setActiveBusy((p) => ({ ...p, [dsName]: false }));
    }
  };

  const loadDatasets = async () => {
    try {
      const data = await LeaderboardSDK.listDatasets();
      setDatasets(Array.isArray(data.datasets) ? data.datasets : []);
    } catch (e) {
      // Keep silent; UI will still allow creation
    }
  };

  useEffect(() => { loadDatasets(); }, []);

  const datasetNameOptions = useMemo(() => datasets.map(d => d.name), [datasets]);

  const onSubmitDataset = async (e) => {
    e.preventDefault();
    setDsSubmitting(true);
    setDsError('');
    setDsResult(null);
    try {
      const payload = { ...dsForm };
      const res = await LeaderboardSDK.addDataset(payload);
      setDsResult(res);
      resetDatasetForm();
      loadDatasets();
    } catch (e) {
      setDsError(e.message || 'Failed to add dataset');
    } finally {
      setDsSubmitting(false);
    }
  };

  const onSubmitModel = async (e) => {
    e.preventDefault();
    setModelSubmitting(true);
    setModelError('');
    setModelResult(null);
    try {
      const payload = { ...modelForm };
      payload.rank = payload.rank ? Number(payload.rank) : undefined;
      payload.score = payload.score ? Number(payload.score) : undefined;
      const res = await LeaderboardSDK.addModel(payload);
      setModelResult(res);
      resetModelForm();
      loadDatasets();
    } catch (e) {
      setModelError(e.message || 'Failed to add model');
    } finally {
      setModelSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-start min-h-screen bg-gray-900 pb-24 mx-3">
      <header className="w-full max-w-5xl mt-10 pt-10 text-center">
        <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-white">Manage Leaderboard</h1>
        <p className="mt-3 text-gray-300/90 text-sm md:text-base">Add datasets and models to the curated leaderboard.</p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <button
            type="button"
            onClick={() => navigate(adminSubmissionsPath)}
            className="text-sm px-4 py-2 rounded-lg border border-amber-500/50 text-amber-200 hover:bg-amber-500/10"
          >
            All submissions
          </button>
          <button
            type="button"
            onClick={() => navigate(adminDatasetRequestsPath)}
            className="text-sm px-4 py-2 rounded-lg border border-[#28b2fb]/50 text-[#28b2fb] hover:bg-[#28b2fb]/10"
          >
            Dataset requests
          </button>
        </div>
      </header>

      <div className="w-full max-w-5xl grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
        <section className="bg-gray-900/70 rounded-xl border border-gray-800 p-5">
          <h2 className="text-lg font-bold text-white mb-3">Add Dataset</h2>
          <form onSubmit={onSubmitDataset} className="space-y-3">
            <div>
              <label className="block text-sm text-gray-300 mb-1">Name</label>
              <input className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={dsForm.name} onChange={e=>setDsForm(f=>({...f,name:e.target.value}))} required />
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1">URL (optional)</label>
              <input className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={dsForm.url} onChange={e=>setDsForm(f=>({...f,url:e.target.value}))} />
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1">Task Type</label>
              <input placeholder="text_classification | ner | chatbot | prompting | translation" className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={dsForm.task_type} onChange={e=>setDsForm(f=>({...f,task_type:e.target.value}))} required />
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1">Description (optional)</label>
              <textarea className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={dsForm.description} onChange={e=>setDsForm(f=>({...f,description:e.target.value}))} />
            </div>
            {dsError && <div className="text-sm text-red-400">{dsError}</div>}
            {dsResult && <div className="text-sm text-green-400">Dataset added (id: {dsResult.dataset_id})</div>}
            <button type="submit" disabled={dsSubmitting} className="px-4 py-2 rounded-md border border-blue-500/60 text-blue-300 hover:bg-blue-500/10 disabled:opacity-50">{dsSubmitting? 'Adding...' : 'Add Dataset'}</button>
          </form>
        </section>

        <section className="bg-gray-900/70 rounded-xl border border-gray-800 p-5">
          <h2 className="text-lg font-bold text-white mb-3">Add Model</h2>
          <form onSubmit={onSubmitModel} className="space-y-3">
            <div>
              <label className="block text-sm text-gray-300 mb-1">Dataset Name</label>
              <input list="dataset-names" className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={modelForm.dataset_name} onChange={e=>setModelForm(f=>({...f,dataset_name:e.target.value}))} required />
              <datalist id="dataset-names">
                {datasetNameOptions.map((n,i)=>(<option key={i} value={n} />))}
              </datalist>
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1">Model</label>
              <input className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={modelForm.model} onChange={e=>setModelForm(f=>({...f,model:e.target.value}))} required />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-sm text-gray-300 mb-1">Rank</label>
                <input type="number" className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={modelForm.rank} onChange={e=>setModelForm(f=>({...f,rank:e.target.value}))} />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Score</label>
                <input type="number" step="0.0001" className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={modelForm.score} onChange={e=>setModelForm(f=>({...f,score:e.target.value}))} />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Updated</label>
                <input placeholder="e.g., Sep 2024" className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={modelForm.updated} onChange={e=>setModelForm(f=>({...f,updated:e.target.value}))} required />
              </div>
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1">Confidence Interval (optional)</label>
              <input placeholder="e.g., 0.90 - 0.94" className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={modelForm.ci} onChange={e=>setModelForm(f=>({...f,ci:e.target.value}))} />
            </div>
            {modelError && <div className="text-sm text-red-400">{modelError}</div>}
            {modelResult && <div className="text-sm text-green-400">Model added to dataset.</div>}
            <button type="submit" disabled={modelSubmitting} className="px-4 py-2 rounded-md border border-green-500/60 text-green-300 hover:bg-green-500/10 disabled:opacity-50">{modelSubmitting? 'Adding...' : 'Add Model'}</button>
          </form>
        </section>
      </div>

      {/* ── Questions-public panel ── */}
      <div className="w-full max-w-5xl mt-8">
        <section className="bg-gray-900/70 rounded-xl border border-gray-800 p-5">
          <h2 className="text-lg font-bold text-white mb-1">Test Question Visibility</h2>
          <p className="text-sm text-gray-400 mb-4">
            When <span className="text-[#defe47] font-semibold">Questions Public</span> is ON, users can see the exact test inputs before submitting — useful for open benchmarks.
            Turn it <span className="text-red-400 font-semibold">OFF</span> to force blind evaluation: users receive only question IDs/count, not the text.
          </p>

          {/* Admin key input */}
          <div className="flex items-center gap-3 mb-4">
            <input
              type="password"
              placeholder="X-Admin-Key"
              value={adminKey}
              onChange={(e) => setAdminKey(e.target.value)}
              className="w-56 px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white text-sm focus:outline-none focus:border-amber-500/60"
            />
            <button
              type="button"
              onClick={loadQpDatasets}
              disabled={!adminKey.trim() || qpLoading}
              className="px-4 py-2 rounded-md border border-amber-500/50 text-amber-200 hover:bg-amber-500/10 text-sm disabled:opacity-40"
            >
              {qpLoading ? 'Loading…' : 'Load datasets'}
            </button>
          </div>

          {qpError && <div className="text-sm text-red-400 mb-3">{qpError}</div>}

          {qpDatasets.length > 0 && (
            <div className="divide-y divide-gray-800 border border-gray-800 rounded-lg overflow-hidden">
              <div className="grid grid-cols-[1fr_auto_auto_auto] text-[11px] font-semibold uppercase tracking-wider text-gray-500 px-4 py-2 bg-gray-950/50">
                <span>Dataset</span>
                <span className="text-center w-24">Questions</span>
                <span className="text-center w-24">Active</span>
                <span className="w-36" />
              </div>
              {qpDatasets.map((ds) => (
                <div key={ds.name} className={`grid grid-cols-[1fr_auto_auto_auto] items-center px-4 py-3 hover:bg-white/[0.02] ${ds.active === false ? 'opacity-50' : ''}`}>
                  <div>
                    <div className="text-sm text-white truncate" title={ds.name}>{ds.name}</div>
                    {ds.task_type && <div className="text-xs text-gray-600">{ds.task_type}</div>}
                  </div>
                  <div className="w-24 text-center">
                    {ds.questions_public
                      ? <span className="inline-flex items-center gap-1 text-xs font-semibold text-green-400 bg-green-500/10 border border-green-500/30 rounded-full px-2 py-0.5">● Public</span>
                      : <span className="inline-flex items-center gap-1 text-xs font-semibold text-yellow-400 bg-yellow-500/10 border border-yellow-500/30 rounded-full px-2 py-0.5">● Hidden</span>
                    }
                  </div>
                  <div className="w-24 text-center">
                    {ds.active !== false
                      ? <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-400 bg-blue-500/10 border border-blue-500/30 rounded-full px-2 py-0.5">● Active</span>
                      : <span className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 bg-gray-500/10 border border-gray-600/30 rounded-full px-2 py-0.5">● Inactive</span>
                    }
                  </div>
                  <div className="w-36 flex gap-2 justify-end">
                    <button
                      type="button"
                      disabled={!!qpBusy[ds.name]}
                      onClick={() => toggleQuestionsPublic(ds.name, ds.questions_public)}
                      className={`text-xs px-2.5 py-1 rounded-lg border transition-colors disabled:opacity-40 ${
                        ds.questions_public
                          ? 'border-yellow-500/40 text-yellow-300 hover:bg-yellow-500/10'
                          : 'border-green-500/40 text-green-300 hover:bg-green-500/10'
                      }`}
                    >
                      {qpBusy[ds.name] ? '…' : ds.questions_public ? 'Hide Qs' : 'Show Qs'}
                    </button>
                    <button
                      type="button"
                      disabled={!!activeBusy[ds.name]}
                      onClick={() => toggleActive(ds.name, ds.active !== false)}
                      className={`text-xs px-2.5 py-1 rounded-lg border transition-colors disabled:opacity-40 ${
                        ds.active !== false
                          ? 'border-red-500/40 text-red-300 hover:bg-red-500/10'
                          : 'border-blue-500/40 text-blue-300 hover:bg-blue-500/10'
                      }`}
                    >
                      {activeBusy[ds.name] ? '…' : ds.active !== false ? 'Deactivate' : 'Activate'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* ── Quota usage panel ── */}
      <div className="w-full max-w-5xl mt-8">
        <section className="bg-gray-900/70 rounded-xl border border-gray-800 p-5">
          <h2 className="text-lg font-bold text-white mb-1">Quota &amp; Rate Usage</h2>
          <p className="text-sm text-gray-400 mb-4">
            Daily submission counts per user and active rate-limit windows.
          </p>

          <div className="flex items-center gap-3 mb-4">
            <span className="text-xs text-gray-500">Uses the same admin key above.</span>
            <button
              type="button"
              onClick={loadQuotaUsage}
              disabled={!adminKey.trim() || quotaLoading}
              className="px-4 py-2 rounded-md border border-amber-500/50 text-amber-200 hover:bg-amber-500/10 text-sm disabled:opacity-40"
            >
              {quotaLoading ? 'Loading…' : 'Load usage'}
            </button>
          </div>

          {quotaError && <div className="text-sm text-red-400 mb-3">{quotaError}</div>}

          {quotaData && (
            <div className="space-y-6">
              {/* Daily quota table */}
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
                  Daily submission quota (limit: {quotaData.daily_limit}/day)
                </div>
                {quotaData.quota.length === 0 ? (
                  <div className="text-sm text-gray-600 italic">No submissions today.</div>
                ) : (
                  <div className="border border-gray-800 rounded-lg overflow-hidden">
                    <div className="grid grid-cols-[1fr_auto_auto_auto] text-[11px] font-semibold uppercase tracking-wider text-gray-500 px-4 py-2 bg-gray-950/50">
                      <span>Submitter</span>
                      <span className="w-16 text-center">Date</span>
                      <span className="w-20 text-center">Used</span>
                      <span className="w-24 text-right">Bar</span>
                    </div>
                    {quotaData.quota.slice(0, 50).map((row) => {
                      const pct = quotaData.daily_limit > 0
                        ? Math.min(100, Math.round((row.used / quotaData.daily_limit) * 100))
                        : 0;
                      const atLimit = row.remaining === 0;
                      return (
                        <div key={`${row.submitter_id}:${row.date}`}
                          className="grid grid-cols-[1fr_auto_auto_auto] items-center px-4 py-2.5 border-t border-gray-800 hover:bg-white/[0.02]">
                          <div className="text-sm text-white font-mono truncate" title={row.submitter_id}>
                            {row.submitter_id.length > 36 ? row.submitter_id.slice(0, 34) + '…' : row.submitter_id}
                          </div>
                          <div className="w-16 text-center text-xs text-gray-500">{row.date}</div>
                          <div className={`w-20 text-center text-sm font-semibold ${atLimit ? 'text-red-400' : 'text-[#defe47]'}`}>
                            {row.used} / {row.limit}
                          </div>
                          <div className="w-24 flex items-center justify-end gap-2">
                            <div className="w-16 h-1.5 rounded-full bg-gray-800 overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all ${atLimit ? 'bg-red-500' : 'bg-[#defe47]'}`}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Active rate windows */}
              {quotaData.rate_windows.length > 0 && (
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
                    Active rate-limit windows (last 60 s)
                  </div>
                  <div className="border border-gray-800 rounded-lg overflow-hidden">
                    <div className="grid grid-cols-[1fr_2fr_auto] text-[11px] font-semibold uppercase tracking-wider text-gray-500 px-4 py-2 bg-gray-950/50">
                      <span>IP</span>
                      <span>Endpoint</span>
                      <span className="text-right">Req/min</span>
                    </div>
                    {quotaData.rate_windows.map((w, i) => (
                      <div key={i} className="grid grid-cols-[1fr_2fr_auto] items-center px-4 py-2.5 border-t border-gray-800 hover:bg-white/[0.02]">
                        <div className="text-sm font-mono text-gray-300">{w.ip}</div>
                        <div className="text-sm text-gray-400 truncate" title={w.path}>{w.path}</div>
                        <div className="text-sm text-right font-semibold text-amber-300">{w.requests_last_minute}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      {/* <div className="w-full max-w-5xl mt-10">
        <h3 className="text-white font-semibold mb-3">Current Datasets</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {datasets.map((d, i) => (
            <div key={i} className="bg-gray-900/70 rounded-xl border border-gray-800 p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="text-white font-semibold">{d.name}</div>
                {d.task_type ? <div className="text-xs text-gray-300">{d.task_type}</div> : null}
              </div>
              {d.models?.length ? (
                <div className="divide-y divide-gray-800 border border-gray-800 rounded-lg overflow-hidden">
                  <div className="grid grid-cols-4 text-white font-semibold text-center bg-gray-900/80 px-3 py-2">
                    <div>Rank</div><div>Model</div><div>Score</div><div>Updated</div>
                  </div>
                  {d.models.map((m, j) => (
                    <div key={j} className="grid grid-cols-4 text-center px-3 py-2 text-white">
                      <div>{m.rank ?? '-'}</div>
                      <div className="truncate" title={m.model}>{m.model}</div>
                      <div>{typeof m.score === 'number' ? (m.score < 1 ? m.score.toFixed(3) : m.score.toFixed(2)) : (m.score ?? '-')}{m.ci ? <span className="ml-2 text-xs text-gray-300">({m.ci})</span> : null}</div>
                      <div className="text-gray-300">{m.updated}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-gray-400 text-sm">No models yet.</div>
              )}
            </div>
          ))}
        </div>
      </div> */}
    </div>
  );
};

export default AdminLeaderboardManager;

