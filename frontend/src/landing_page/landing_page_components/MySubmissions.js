import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { formatMetricsSummary } from "../../utils/formatMetricsSummary";
import { submittoleaderboardPath } from "../../constants/RouteConstants";
import { getLeaderboardJwt } from "../../utils/leaderboardAuth";

const API_BASE =
  process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001";

const MySubmissions = () => {
  const navigate = useNavigate();
  const [apiKey, setApiKey] = useState(() => localStorage.getItem("leaderboard_api_key") || "");
  const [submitterId, setSubmitterId] = useState(() => localStorage.getItem("leaderboard_submitter_id") || "");
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [nextCursor, setNextCursor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [expandedRows, setExpandedRows] = useState({});

  useEffect(() => {
    localStorage.setItem("leaderboard_api_key", apiKey);
  }, [apiKey]);
  useEffect(() => {
    localStorage.setItem("leaderboard_submitter_id", submitterId);
  }, [submitterId]);

  const load = async () => {
    setLoading(true);
    setError("");
    setNextCursor(null);
    try {
      const jwt = getLeaderboardJwt();
      if (!submitterId.trim() && !jwt) {
        setRows([]);
        setTotal(0);
        setError("Set a submitter id (same as on Submit page) or sign in so the API receives your JWT.");
        setLoading(false);
        return;
      }
      const qs = new URLSearchParams({ page_size: "50" });
      if (submitterId.trim()) qs.set("submitter_id", submitterId.trim());
      const headers = {};
      if (apiKey.trim()) headers["X-API-Key"] = apiKey.trim();
      if (jwt) headers["Authorization"] = `Bearer ${jwt}`;
      const res = await fetch(`${API_BASE}/public/my_submissions?${qs}`, { headers });
      const data = await res.json();
      if (!res.ok || data.success !== true) {
        throw new Error(data.error || "Failed to load");
      }
      setRows(data.submissions || []);
      setTotal(data.total || 0);
      setNextCursor(data.next_cursor || null);
    } catch (e) {
      setError(e.message || "Error");
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  const loadMore = async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    setError("");
    try {
      const jwt = getLeaderboardJwt();
      const qs = new URLSearchParams({ page_size: "50", cursor: nextCursor });
      if (submitterId.trim()) qs.set("submitter_id", submitterId.trim());
      const headers = {};
      if (apiKey.trim()) headers["X-API-Key"] = apiKey.trim();
      if (jwt) headers["Authorization"] = `Bearer ${jwt}`;
      const res = await fetch(`${API_BASE}/public/my_submissions?${qs}`, { headers });
      const data = await res.json();
      if (!res.ok || data.success !== true) {
        throw new Error(data.error || "Failed to load more");
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

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleExpanded = (key) => {
    setExpandedRows((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const formatScore = (value) => {
    if (typeof value !== "number") return value ?? "—";
    return value >= 0 && value <= 1 ? value.toFixed(4) : value.toFixed(2);
  };

  return (
    <div className="min-h-screen bg-[#111827] text-gray-100 py-10 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <h1 className="text-2xl font-bold text-white">My submissions</h1>
          <button
            type="button"
            onClick={() => navigate(submittoleaderboardPath)}
            className="text-sm px-3 py-2 rounded-lg border border-[#defe47]/50 text-[#defe47] hover:bg-[#defe47]/10"
          >
            Submit
          </button>
        </div>
        <p className="text-sm text-gray-400 mb-4">
          Lists rows for your account: either sign in (Bearer <code className="text-gray-300">sub</code> from the session JWT) or set a{" "}
          <code className="text-gray-300">submitter_id</code> that matches your submissions.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
          <input
            type="password"
            placeholder="X-API-Key (if required)"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
          />
          <input
            type="text"
            placeholder="Submitter id"
            value={submitterId}
            onChange={(e) => setSubmitterId(e.target.value)}
            className="px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white"
          />
        </div>
        <button
          type="button"
          onClick={load}
          className="mb-6 px-4 py-2 rounded-md bg-[#defe47] text-black font-semibold"
        >
          Refresh
        </button>
        {error && <div className="text-red-400 text-sm mb-4">{error}</div>}
        {loading ? (
          <div className="text-gray-400">Loading…</div>
        ) : (
          <div className="text-sm text-gray-500 mb-2">Total: {total}</div>
        )}
        <div className="space-y-2">
          {rows.map((r, idx) => (
            <div
              key={`${r.submission_id}-${idx}`}
              className="bg-[#0d1421] border border-gray-800 rounded-lg overflow-hidden"
            >
              <button
                type="button"
                onClick={() => toggleExpanded(`${r.submission_id}-${idx}`)}
                className="w-full p-4 text-left flex flex-col gap-1 hover:bg-white/[0.03]"
              >
                <div className="flex flex-wrap justify-between gap-2">
                  <span className="font-medium text-white">{r.dataset_name}</span>
                  <span className="tabular-nums text-[#defe47]">{formatScore(r.score)}</span>
                </div>
                <div className="flex flex-wrap justify-between gap-2 text-gray-400 text-xs">
                  <span>{r.model_name} · {r.submitted_at || ""}</span>
                  <span className="text-[#28b2fb]">
                    {expandedRows[`${r.submission_id}-${idx}`] ? "Hide details" : "Show details"}
                  </span>
                </div>
                {r.detailed_scores && (
                  <div className="text-xs font-mono text-gray-500 break-all">{formatMetricsSummary(r.detailed_scores)}</div>
                )}
              </button>
              {expandedRows[`${r.submission_id}-${idx}`] && (
                <div className="border-t border-gray-800 bg-[#0a101a] p-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                    <div>
                      <div className="text-xs uppercase tracking-wide text-gray-500">Primary score</div>
                      <div className="text-3xl font-bold text-[#defe47] tabular-nums">{formatScore(r.score)}</div>
                      <div className="text-xs text-gray-500">{r.primary_metric || "primary metric"}</div>
                    </div>
                    <div className="md:col-span-2 text-xs text-gray-400 space-y-1">
                      <div><span className="text-gray-500">Dataset:</span> {r.dataset_name}</div>
                      <div><span className="text-gray-500">Task type:</span> {r.task_type || "—"}</div>
                      <div><span className="text-gray-500">Submitted:</span> {r.submitted_at || "—"}</div>
                    </div>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead className="text-gray-500 uppercase tracking-wide">
                        <tr className="border-b border-gray-800">
                          <th className="text-left py-2 pr-3 font-semibold">Key</th>
                          <th className="text-right py-2 pl-3 font-semibold">Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(r.detailed_scores || {}).map(([key, value]) => (
                          <tr key={key} className="border-b border-gray-800/60 last:border-0">
                            <td className="py-2 pr-3 font-mono text-gray-300">{key}</td>
                            <td className="py-2 pl-3 text-right tabular-nums text-gray-200">
                              {typeof value === "number" ? formatScore(value) : String(value)}
                            </td>
                          </tr>
                        ))}
                        {!r.detailed_scores && (
                          <tr>
                            <td className="py-3 text-gray-500" colSpan={2}>No detailed scores returned for this submission.</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
        {nextCursor && !loading && (
          <div className="mt-6 flex justify-center">
            <button
              type="button"
              onClick={loadMore}
              disabled={loadingMore}
              className="px-4 py-2 rounded-lg border border-[#defe47]/50 text-[#defe47] text-sm font-semibold hover:bg-[#defe47]/10 disabled:opacity-50"
            >
              {loadingMore ? "Loading…" : "Load more"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default MySubmissions;
