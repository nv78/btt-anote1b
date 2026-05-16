import React, { useState } from "react";

const API_BASE = process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001";

const TASK_TYPES = [
  { value: "text_classification", label: "Text Classification" },
  { value: "named_entity_recognition", label: "Named Entity Recognition (NER)" },
  { value: "document_qa", label: "Document Q&A" },
  { value: "retrieval", label: "Retrieval / RAG" },
  { value: "translation", label: "Translation" },
  { value: "other", label: "Other (specify below)" },
];

const empty = { dataset_name: "", task_type: "text_classification", custom_task_type: "", description: "", url: "", requested_by: "" };

export default function RequestDataset() {
  const [form, setForm] = useState(empty);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  const update = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/public/request_dataset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dataset_name: form.dataset_name.trim(),
          task_type: form.task_type === "other" ? (form.custom_task_type.trim() || "other") : form.task_type,
          description: form.description.trim(),
          url: form.url.trim() || undefined,
          requested_by: form.requested_by.trim() || "anonymous",
        }),
      });
      const data = await res.json();
      if (!res.ok || data.success !== true) throw new Error(data.error || "Submission failed");
      setSuccess(true);
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-[#111827] flex items-center justify-center px-4">
        <div className="max-w-md w-full text-center">
          <div className="text-5xl mb-4">🎉</div>
          <h2 className="text-2xl font-bold text-white mb-2">Request submitted!</h2>
          <p className="text-gray-400 text-sm mb-6">
            Our team will review your dataset request and add it to the leaderboard if it's a good fit. We'll reach out if we have questions.
          </p>
          <button
            type="button"
            onClick={() => { setSuccess(false); setForm(empty); }}
            className="text-sm text-[#defe47] hover:underline"
          >
            Submit another request
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#111827] text-gray-100 px-4 py-12">
      <div className="max-w-xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white">Request a Dataset</h1>
          <p className="text-gray-400 text-sm mt-2">
            Don't see the benchmark you need? Tell us about it and we'll review it for addition to the leaderboard.
          </p>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-5">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Dataset name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="e.g. AG News, SQuAD, CoNLL-2003"
              value={form.dataset_name}
              onChange={(e) => update("dataset_name", e.target.value)}
              className="w-full rounded-lg bg-[#0d1421] border border-gray-700 text-white text-sm px-4 py-2.5 focus:outline-none focus:border-[#defe47]/50"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Task type <span className="text-red-400">*</span>
            </label>
            <select
              required
              value={form.task_type}
              onChange={(e) => update("task_type", e.target.value)}
              className="w-full rounded-lg bg-[#0d1421] border border-gray-700 text-white text-sm px-4 py-2.5 focus:outline-none focus:border-[#defe47]/50"
            >
              {TASK_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
            {form.task_type === "other" && (
              <input
                type="text"
                required
                placeholder="Describe the task type (e.g. Summarization, Code Generation)"
                value={form.custom_task_type}
                onChange={(e) => update("custom_task_type", e.target.value)}
                className="mt-2 w-full rounded-lg bg-[#0d1421] border border-gray-700 text-white text-sm px-4 py-2.5 focus:outline-none focus:border-[#defe47]/50"
              />
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Why this dataset? <span className="text-red-400">*</span>
            </label>
            <textarea
              required
              rows={4}
              placeholder="Describe what this dataset benchmarks and why it would be valuable on the leaderboard..."
              value={form.description}
              onChange={(e) => update("description", e.target.value)}
              className="w-full rounded-lg bg-[#0d1421] border border-gray-700 text-white text-sm px-4 py-2.5 focus:outline-none focus:border-[#defe47]/50 resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Dataset URL <span className="text-gray-500">(optional)</span>
            </label>
            <input
              type="url"
              placeholder="https://huggingface.co/datasets/..."
              value={form.url}
              onChange={(e) => update("url", e.target.value)}
              className="w-full rounded-lg bg-[#0d1421] border border-gray-700 text-white text-sm px-4 py-2.5 focus:outline-none focus:border-[#defe47]/50"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Your email <span className="text-gray-500">(optional — so we can follow up)</span>
            </label>
            <input
              type="email"
              placeholder="you@example.com"
              value={form.requested_by}
              onChange={(e) => update("requested_by", e.target.value)}
              className="w-full rounded-lg bg-[#0d1421] border border-gray-700 text-white text-sm px-4 py-2.5 focus:outline-none focus:border-[#defe47]/50"
            />
          </div>

          {error && (
            <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 rounded-lg bg-[#defe47] px-6 py-2.5 text-sm font-semibold text-black hover:bg-[#e8ff70] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? "Submitting…" : "Submit request"}
          </button>
        </form>
      </div>
    </div>
  );
}
