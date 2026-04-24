import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import LeaderboardSDK from "../../lib/leaderboardSdk";
import { csvBenchmarksPath, evaluationsPath, submittoleaderboardPath } from "../../constants/RouteConstants";

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

const popularDatasets = [
  { name: "ag_news", task_type: "text_classification", description: "AG News classification" },
  { name: "imdb", task_type: "text_classification", description: "Movie review sentiment" },
  { name: "squad", task_type: "document_qa", description: "Extractive QA" },
  { name: "conll2003", task_type: "named_entity_recognition", description: "Named entity recognition" },
  { name: "financial_phrasebank", task_type: "text_classification", description: "Financial sentiment" },
];

const emptyRows = [{ source: "", answer: "" }];

const AddDataset = () => {
  const [form, setForm] = useState(emptyForm);
  const [rows, setRows] = useState(emptyRows);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const updateRow = (index, key, value) => {
    setRows((current) => current.map((row, rowIndex) => (rowIndex === index ? { ...row, [key]: value } : row)));
  };
  const addRow = () => setRows((current) => [...current, { source: "", answer: "" }]);
  const removeRow = (index) => setRows((current) => current.filter((_, rowIndex) => rowIndex !== index));

  const referenceDataFromRows = () => {
    const cleanRows = rows.filter((row) => row.source.trim() && row.answer.trim());
    const referenceData = {
      description: form.description || undefined,
      url: form.url || undefined,
      source_texts: cleanRows.map((row) => row.source.trim()),
    };
    if (form.task_type === "text_classification") {
      referenceData.labels = cleanRows.map((row) => row.answer.trim());
    } else if (form.task_type === "named_entity_recognition") {
      referenceData.entities = cleanRows.map((row) => row.answer.split(";").map((value) => value.trim()).filter(Boolean));
    } else if (form.task_type === "translation") {
      referenceData.reference_translations = cleanRows.map((row) => row.answer.trim());
    } else {
      referenceData.answers = cleanRows.map((row) => row.answer.trim());
    }
    return referenceData;
  };

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
            ...referenceDataFromRows(),
          },
        });
        setMessage(`Created ${form.name}`);
      }
      setForm(emptyForm);
      setRows(emptyRows);
    } catch (err) {
      setError(err.message || "Failed to create dataset");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="bg-black min-h-screen py-10 px-4 text-gray-100">
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 mb-6">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-[#EDDC8F] mb-3">Dataset Registry</div>
            <h1 className="text-3xl sm:text-4xl font-extrabold bg-gradient-to-r from-[#EDDC8F] to-[#F1CA57] bg-clip-text text-transparent">Add Dataset</h1>
          </div>
          <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="px-3 py-2 rounded-md border border-[#EDDC8F] bg-[#EDDC8F] text-black font-semibold hover:bg-[#F1CA57]"
            onClick={() => navigate(evaluationsPath)}
          >
            View Evaluations
          </button>
          <button
            type="button"
            className="px-3 py-2 rounded-md border border-[#EDDC8F]/60 text-[#EDDC8F] hover:bg-[#EDDC8F]/10"
            onClick={() => navigate(submittoleaderboardPath)}
          >
            Submit Model
          </button>
          <button
            type="button"
            className="px-3 py-2 rounded-md border border-gray-700 text-gray-300 hover:bg-gray-900"
            onClick={() => navigate(csvBenchmarksPath)}
          >
            Run Benchmarks
          </button>
          <button
            type="button"
            className="px-3 py-2 rounded-md border border-gray-700 text-gray-300 hover:bg-gray-900"
            onClick={() => navigate("/")}
          >
            Leaderboard
          </button>
          </div>
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
            <>
              <div>
                <label className="block text-sm text-gray-300 mb-2">Popular Datasets</label>
                <div className="flex flex-wrap gap-2">
                  {popularDatasets.map((dataset) => (
                    <button
                      key={dataset.name}
                      type="button"
                      title={dataset.description}
                      className="px-3 py-1 rounded border border-gray-700 text-sm text-gray-300 hover:bg-gray-900"
                      onClick={() => {
                        update("hf_dataset", dataset.name);
                        update("task_type", dataset.task_type);
                      }}
                    >
                      {dataset.name}
                    </button>
                  ))}
                </div>
              </div>
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
            </>
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
              <div className="border border-gray-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <label className="block text-sm text-gray-300">Ground Truth Rows</label>
                  <button
                    type="button"
                    className="px-3 py-1 rounded border border-gray-700 text-sm text-gray-300 hover:bg-gray-900"
                    onClick={addRow}
                  >
                    Add Row
                  </button>
                </div>
                <div className="space-y-3">
                  {rows.map((row, index) => (
                    <div key={index} className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-3">
                      <input
                        placeholder="Question, source text, or document"
                        className="px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
                        value={row.source}
                        onChange={(event) => updateRow(index, "source", event.target.value)}
                      />
                      <input
                        placeholder="Label, answer, translation, or entities separated by semicolons"
                        className="px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
                        value={row.answer}
                        onChange={(event) => updateRow(index, "answer", event.target.value)}
                      />
                      <button
                        type="button"
                        className="px-3 py-2 rounded border border-gray-700 text-gray-400 hover:bg-gray-900"
                        onClick={() => removeRow(index)}
                        disabled={rows.length === 1}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
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
