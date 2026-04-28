import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { adminLeaderboardPath } from "../../constants/RouteConstants";

const API_BASE =
  process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001";

/**
 * Lists `GET /api/admin/submissions` for keys in `LEADERBOARD_ADMIN_API_KEYS`.
 * Uses `X-Admin-Key` (stored in localStorage as `leaderboard_admin_key` for convenience).
 */
export default function AdminSubmissionsModeration() {
  const navigate = useNavigate();
  const [adminKey, setAdminKey] = useState(() => localStorage.getItem("leaderboard_admin_key") || "");
  const [dataset, setDataset] = useState("");
  const [submitterId, setSubmitterId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [includeOutputs, setIncludeOutputs] = useState(false);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [nextCursor, setNextCursor] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    localStorage.setItem("leaderboard_admin_key", adminKey);
  }, [adminKey]);

  const buildQuery = (cursor) => {
    const qs = new URLSearchParams({ page_size: "40" });
    if (dataset.trim()) qs.set("dataset", dataset.trim());
    if (submitterId.trim()) qs.set("submitter_id", submitterId.trim());
    if (dateFrom.trim()) qs.set("from", dateFrom.trim());
    if (dateTo.trim()) qs.set("to", dateTo.trim());
    if (includeOutputs) qs.set("include_outputs", "1");
    if (cursor) qs.set("cursor", cursor);
    return qs;
  };

  const load = async () => {
    if (!adminKey.trim()) {
      setError("Enter an admin key that matches LEADERBOARD_ADMIN_API_KEYS.");
      setRows([]);
      setTotal(0);
      setNextCursor(null);
      return;
    }
    setLoading(true);
    setError("");
    setNextCursor(null);
    try {
      const qs = buildQuery(null);
      const res = await fetch(`${API_BASE}/api/admin/submissions?${qs}`, {
        headers: { "X-Admin-Key": adminKey.trim() },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.success !== true) {
        throw new Error(data.error || `Request failed (${res.status})`);
      }
      setRows(data.submissions || []);
      setTotal(data.total ?? 0);
      setNextCursor(data.next_cursor || null);
    } catch (e) {
      setError(e.message || "Error");
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  const loadMore = async () => {
    if (!nextCursor || loadingMore || !adminKey.trim()) return;
    setLoadingMore(true);
    setError("");
    try {
      const qs = buildQuery(nextCursor);
      const res = await fetch(`${API_BASE}/api/admin/submissions?${qs}`, {
        headers: { "X-Admin-Key": adminKey.trim() },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.success !== true) {
        throw new Error(data.error || `Request failed (${res.status})`);
      }
      const chunk = data.submissions || [];
      setRows((prev) => [...prev, ...chunk]);
      setNextCursor(data.next_cursor || null);
    } catch (e) {
      setError(e.message || "Error");
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-start min-h-screen bg-gray-900 pb-24 px-4 text-gray-100">
      <header className="w-full max-w-5xl mt-10 pt-6 text-center">
        <h1 className="text-2xl md:text-3xl font-extrabold text-white">Admin: all submissions</h1>
        <p className="mt-2 text-gray-400 text-sm max-w-xl mx-auto">
          Calls <code className="text-gray-300">GET /api/admin/submissions</code>. Keys must match{" "}
          <code className="text-gray-300">LEADERBOARD_ADMIN_API_KEYS</code> only (not regular write keys).
        </p>
        <button
          type="button"
          onClick={() => navigate(adminLeaderboardPath)}
          className="mt-3 text-sm text-[#28b2fb] hover:underline"
        >
          Back to curated admin
        </button>
      </header>

      <div className="w-full max-w-5xl mt-8 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <input
            type="password"
            placeholder="X-Admin-Key"
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            className="px-3 py-2 rounded-md bg-gray-950 border border-gray-700 text-white md:col-span-2"
          />
          <input
            type="text"
            placeholder="Filter dataset name (optional)"
            value={dataset}
            onChange={(e) => setDataset(e.target.value)}
            className="px-3 py-2 rounded-md bg-gray-950 border border-gray-700 text-white"
          />
          <input
            type="text"
            placeholder="Filter submitter_id (optional)"
            value={submitterId}
            onChange={(e) => setSubmitterId(e.target.value)}
            className="px-3 py-2 rounded-md bg-gray-950 border border-gray-700 text-white"
          />
          <input
            type="text"
            placeholder="from (ISO date/time, optional)"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="px-3 py-2 rounded-md bg-gray-950 border border-gray-700 text-white"
          />
          <input
            type="text"
            placeholder="to (ISO date/time, optional)"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="px-3 py-2 rounded-md bg-gray-950 border border-gray-700 text-white"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-400">
          <input
            type="checkbox"
            checked={includeOutputs}
            onChange={(e) => setIncludeOutputs(e.target.checked)}
            className="rounded border-gray-600"
          />
          Include full evaluation_details and model_results (support / debugging)
        </label>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="px-4 py-2 rounded-md bg-[#defe47] text-black font-semibold disabled:opacity-50"
          >
            {loading ? "Loading…" : "Fetch"}
          </button>
        </div>
        {error && <div className="text-sm text-red-400 bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2">{error}</div>}
        {!loading && rows.length > 0 && (
          <div className="text-xs text-gray-500">Total matching filter (server): {total}</div>
        )}
        <div className="space-y-2">
          {rows.map((r, idx) => (
            <div
              key={`${r.submission_id}-${idx}`}
              className="bg-gray-950/80 border border-gray-800 rounded-lg p-4 text-sm"
            >
              <div className="flex flex-wrap justify-between gap-2 text-white font-medium">
                <span>
                  #{r.submission_id} · {r.dataset_name}
                </span>
                <span className="tabular-nums text-[#defe47]">{r.score}</span>
              </div>
              <div className="text-gray-400 text-xs mt-1">
                {r.model_name} · {r.created || ""}
              </div>
              {r.submitted_by != null && (
                <div className="text-xs text-gray-500 mt-1">by {r.submitted_by}</div>
              )}
              {r.submitter_id != null && r.submitter_id !== r.submitted_by && (
                <div className="text-xs text-gray-500">submitter_id: {r.submitter_id}</div>
              )}
              {r.evaluation_snippet != null && (
                <pre className="mt-2 text-xs text-gray-500 whitespace-pre-wrap break-all max-h-32 overflow-y-auto">
                  {typeof r.evaluation_snippet === "string"
                    ? r.evaluation_snippet
                    : JSON.stringify(r.evaluation_snippet, null, 2)}
                </pre>
              )}
              {r.evaluation_details != null && (
                <pre className="mt-2 text-xs text-gray-600 whitespace-pre-wrap break-all max-h-48 overflow-y-auto">
                  {JSON.stringify(r.evaluation_details, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
        {nextCursor && !loading && (
          <div className="flex justify-center pt-4">
            <button
              type="button"
              onClick={loadMore}
              disabled={loadingMore}
              className="px-4 py-2 rounded-lg border border-[#defe47]/50 text-[#defe47] text-sm font-semibold disabled:opacity-50"
            >
              {loadingMore ? "Loading…" : "Load more"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
