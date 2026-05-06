import React, { useState } from "react";

const API_BASE =
  process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001";

const taskTypes = [
  "text_classification",
  "document_qa",
  "named_entity_recognition",
  "retrieval",
  "translation",
];

const CreateLeaderboardFromHF = () => {
  const [apiKey, setApiKey] = useState(() => localStorage.getItem("leaderboard_api_key") || "");
  const [step, setStep] = useState(1);
  const [importing, setImporting] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [importResult, setImportResult] = useState(null);
  const [runResult, setRunResult] = useState(null);
  const [pollStatus, setPollStatus] = useState("");
  const [form, setForm] = useState({
    dataset_name: "nyu-mll/glue",
    config: "sst2",
    split: "validation",
    limit: 200,
    task_type: "text_classification",
    display_name: "GLUE SST-2 Validation",
  });
  const [modelForm, setModelForm] = useState({
    model_id: "distilbert/distilbert-base-uncased-finetuned-sst-2-english",
    batch_size: 16,
  });

  const headers = () => {
    const h = { "Content-Type": "application/json" };
    if (apiKey.trim()) h["X-API-Key"] = apiKey.trim();
    return h;
  };

  const updateForm = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));
  const updateModelForm = (key, value) => setModelForm((prev) => ({ ...prev, [key]: value }));

  const importDataset = async (event) => {
    event.preventDefault();
    setError("");
    setImporting(true);
    setImportResult(null);
    try {
      localStorage.setItem("leaderboard_api_key", apiKey);
      const payload = {
        dataset_name: form.dataset_name.trim(),
        config: form.config.trim() || undefined,
        split: form.split,
        limit: Number(form.limit) || 200,
        task_type: form.task_type,
        display_name: form.display_name.trim() || undefined,
      };
      const res = await fetch(`${API_BASE}/public/import_hf_dataset`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || data.success !== true) throw new Error(data.error || "Import failed");
      setImportResult(data.dataset);
      setStep(2);
    } catch (e) {
      setError(e.message || "Import failed");
    } finally {
      setImporting(false);
    }
  };

  const pollJob = async (jobId) => {
    for (let i = 0; i < 180; i++) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const res = await fetch(`${API_BASE}/public/eval_jobs/${jobId}`);
      const data = await res.json();
      setPollStatus(data.status || "pending");
      if (data.status === "completed") {
        setRunResult(data);
        return;
      }
      if (data.status === "failed") {
        throw new Error(data.error || "Model run failed");
      }
    }
    throw new Error("Timed out waiting for model run");
  };

  const runModel = async (event) => {
    event.preventDefault();
    setError("");
    setRunning(true);
    setRunResult(null);
    setPollStatus("starting");
    try {
      const datasetName = importResult?.name || form.display_name || `${form.dataset_name} (${form.split})`;
      const res = await fetch(`${API_BASE}/public/run_hf_model`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          dataset_name: datasetName,
          model_id: modelForm.model_id.trim(),
          batch_size: Number(modelForm.batch_size) || 16,
          async: true,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.success !== true) throw new Error(data.error || "Model run failed");
      setRunResult({ job_id: data.job_id, status: data.status });
      setPollStatus(data.status || "pending");
      await pollJob(data.job_id);
    } catch (e) {
      setError(e.message || "Model run failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#111827] text-gray-100 px-4 py-10">
      <div className="max-w-5xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white">Create Leaderboard From Hugging Face</h1>
          <p className="text-sm text-gray-400 mt-2">
            Import a bounded dataset split, then optionally run a local Hugging Face model to publish an initial result.
          </p>
        </div>

        <div className="flex items-center gap-3 mb-6 text-sm">
          <div className={`px-3 py-1 rounded-md border ${step === 1 ? "border-[#defe47] text-[#defe47]" : "border-gray-700 text-gray-400"}`}>
            1. Import dataset
          </div>
          <div className={`px-3 py-1 rounded-md border ${step === 2 ? "border-[#28b2fb] text-[#28b2fb]" : "border-gray-700 text-gray-400"}`}>
            2. Run model
          </div>
        </div>

        <label className="block text-sm text-gray-300 mb-6 max-w-xl">
          API key
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="X-API-Key if your backend requires one"
            className="mt-1 w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
          />
        </label>

        {error && <div className="mb-5 text-sm text-red-400 border border-red-900/60 bg-red-950/30 rounded-md px-3 py-2">{error}</div>}

        {step === 1 && (
          <form onSubmit={importDataset} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="text-sm text-gray-300">
              HF Dataset ID
              <input className="mt-1 w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={form.dataset_name} onChange={(e) => updateForm("dataset_name", e.target.value)} />
            </label>
            <label className="text-sm text-gray-300">
              Config / subset
              <input className="mt-1 w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={form.config} onChange={(e) => updateForm("config", e.target.value)} />
            </label>
            <label className="text-sm text-gray-300">
              Split
              <select className="mt-1 w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={form.split} onChange={(e) => updateForm("split", e.target.value)}>
                <option value="validation">validation</option>
                <option value="test">test</option>
                <option value="train">train</option>
              </select>
            </label>
            <label className="text-sm text-gray-300">
              Limit
              <input type="number" min={1} max={5000} className="mt-1 w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={form.limit} onChange={(e) => updateForm("limit", e.target.value)} />
            </label>
            <label className="text-sm text-gray-300">
              Task type
              <select className="mt-1 w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={form.task_type} onChange={(e) => updateForm("task_type", e.target.value)}>
                {taskTypes.map((task) => <option key={task} value={task}>{task}</option>)}
              </select>
            </label>
            <label className="text-sm text-gray-300">
              Leaderboard display name
              <input className="mt-1 w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={form.display_name} onChange={(e) => updateForm("display_name", e.target.value)} />
            </label>
            <div className="md:col-span-2">
              <button type="submit" disabled={importing} className="px-4 py-2 rounded-md bg-[#defe47] text-black font-semibold disabled:opacity-50">
                {importing ? "Importing..." : "Import dataset"}
              </button>
            </div>
          </form>
        )}

        {step === 2 && (
          <div className="space-y-6">
            {importResult && (
              <div className="rounded-md border border-gray-800 bg-[#0d1421] p-4 text-sm text-gray-300">
                Imported <span className="font-semibold text-white">{importResult.name}</span> as {importResult.task_type} / {importResult.evaluation_metric}
                {importResult.size ? ` with ${importResult.size} items.` : "."}
              </div>
            )}
            <form onSubmit={runModel} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="text-sm text-gray-300 md:col-span-2">
                HF Model ID
                <input className="mt-1 w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={modelForm.model_id} onChange={(e) => updateModelForm("model_id", e.target.value)} />
              </label>
              <label className="text-sm text-gray-300">
                Batch size
                <input type="number" min={1} max={128} className="mt-1 w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white" value={modelForm.batch_size} onChange={(e) => updateModelForm("batch_size", e.target.value)} />
              </label>
              <div className="md:col-span-2 flex flex-wrap gap-3">
                <button type="submit" disabled={running} className="px-4 py-2 rounded-md bg-[#28b2fb] text-black font-semibold disabled:opacity-50">
                  {running ? "Running..." : "Run HF model"}
                </button>
                <button type="button" onClick={() => setStep(1)} className="px-4 py-2 rounded-md border border-gray-700 text-gray-300">
                  Back
                </button>
              </div>
            </form>
            {runResult && (
              <div className="rounded-md border border-gray-800 bg-[#0d1421] p-4 text-sm text-gray-300">
                <div>Job ID: <span className="font-mono text-gray-100">{runResult.job_id || "completed synchronously"}</span></div>
                <div>Status: <span className="text-[#defe47]">{pollStatus || runResult.status}</span></div>
                {runResult.score != null && (
                  <div className="mt-2 text-lg text-white">
                    Score: <span className="text-[#defe47]">{Number(runResult.score).toFixed(4)}</span> {runResult.metric}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default CreateLeaderboardFromHF;
