import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import LeaderboardSDK from "../../lib/leaderboardSdk";
import { evaluationsPath } from "../../constants/RouteConstants";

const emptyForm = {
  source: "manual",
  name: "",
  task_type: "text_classification",
  evaluation_metric: "accuracy",
  description: "",
  url: "",
  hf_dataset: "",
  hf_config: "",
  hf_split: "test",
  hf_limit: 100,
};

const AddDataset = () => {
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setMessage("");
    setError("");
    try {
      if (form.source === "huggingface") {
        const result = await LeaderboardSDK.importHfDataset({
          dataset_name: form.hf_dataset,
          config: form.hf_config || undefined,
          split: form.hf_split,
          limit: Number(form.hf_limit) || 100,
          task_type: form.task_type,
          display_name: form.name || undefined,
        });
        setMessage(`Imported ${result.dataset?.name || form.hf_dataset}`);
      } else {
        await LeaderboardSDK.addDatasetPublic({
          name: form.name,
          task_type: form.task_type,
          evaluation_metric: form.evaluation_metric,
          reference_data: {
            description: form.description || undefined,
            url: form.url || undefined,
            source_texts: [],
          },
        });
        setMessage(`Created ${form.name}`);
      }
      setForm(emptyForm);
    } catch (err) {
      setError(err.message || "Failed to create dataset");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="bg-black min-h-screen py-10 px-4 text-gray-100">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between gap-4 mb-6">
          <h1 className="text-3xl sm:text-4xl font-extrabold text-[#EDDC8F]">Add Dataset</h1>
          <button
            type="button"
            className="px-3 py-2 rounded-md border border-gray-700 text-gray-300 hover:bg-gray-900"
            onClick={() => navigate(evaluationsPath)}
          >
            View Leaderboard
          </button>
        </div>

        <form onSubmit={submit} className="border border-gray-800 rounded-lg bg-gray-950 p-5 space-y-4">
          <div>
            <label className="block text-sm text-gray-300 mb-1">Source</label>
            <select
              className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
              value={form.source}
              onChange={(event) => update("source", event.target.value)}
            >
              <option value="manual">Manual</option>
              <option value="huggingface">Hugging Face</option>
            </select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-300 mb-1">Display Name</label>
              <input
                className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
                value={form.name}
                onChange={(event) => update("name", event.target.value)}
                required={form.source === "manual"}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1">Task Type</label>
              <select
                className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
                value={form.task_type}
                onChange={(event) => update("task_type", event.target.value)}
              >
                <option value="text_classification">Text Classification</option>
                <option value="translation">Translation</option>
                <option value="document_qa">Document QA</option>
                <option value="line_qa">Line QA</option>
                <option value="named_entity_recognition">Named Entity Recognition</option>
              </select>
            </div>
          </div>

          {form.source === "huggingface" ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-gray-300 mb-1">Dataset ID</label>
                <input
                  placeholder="ag_news"
                  className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
                  value={form.hf_dataset}
                  onChange={(event) => update("hf_dataset", event.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Config</label>
                <input
                  placeholder="optional"
                  className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
                  value={form.hf_config}
                  onChange={(event) => update("hf_config", event.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Split</label>
                <input
                  className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
                  value={form.hf_split}
                  onChange={(event) => update("hf_split", event.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Max Samples</label>
                <input
                  type="number"
                  min="1"
                  max="5000"
                  className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
                  value={form.hf_limit}
                  onChange={(event) => update("hf_limit", event.target.value)}
                  required
                />
              </div>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Evaluation Metric</label>
                <select
                  className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
                  value={form.evaluation_metric}
                  onChange={(event) => update("evaluation_metric", event.target.value)}
                >
                  <option value="accuracy">Accuracy</option>
                  <option value="f1">F1</option>
                  <option value="bleu">BLEU</option>
                  <option value="bertscore">BERTScore</option>
                  <option value="exact">Exact Match</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Dataset URL</label>
                <input
                  className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
                  value={form.url}
                  onChange={(event) => update("url", event.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Description</label>
                <textarea
                  className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
                  value={form.description}
                  onChange={(event) => update("description", event.target.value)}
                />
              </div>
            </>
          )}

          {error ? <div className="text-sm text-red-400">{error}</div> : null}
          {message ? <div className="text-sm text-green-400">{message}</div> : null}

          <button
            type="submit"
            disabled={submitting}
            className="px-5 py-2 rounded-md border border-[#EDDC8F] text-[#EDDC8F] hover:bg-[#EDDC8F] hover:text-black disabled:opacity-50"
          >
            {submitting ? "Saving..." : "Save Dataset"}
          </button>
        </form>
      </div>
    </section>
  );
};

export default AddDataset;
