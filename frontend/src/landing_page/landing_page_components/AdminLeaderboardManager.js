import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LeaderboardSDK } from '../../lib/leaderboardSdk';
import { adminSubmissionsPath } from '../../constants/RouteConstants';

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
        <button
          type="button"
          onClick={() => navigate(adminSubmissionsPath)}
          className="mt-4 text-sm px-4 py-2 rounded-lg border border-amber-500/50 text-amber-200 hover:bg-amber-500/10"
        >
          All submissions (moderation API)
        </button>
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

