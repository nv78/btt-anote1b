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
              className="bg-[#0d1421] border border-gray-800 rounded-lg p-4 flex flex-col gap-1"
            >
              <div className="flex flex-wrap justify-between gap-2">
                <span className="font-medium text-white">{r.dataset_name}</span>
                <span className="tabular-nums text-[#defe47]">{typeof r.score === "number" ? r.score.toFixed(4) : r.score}</span>
              </div>
              <div className="text-gray-400 text-xs">
                {r.model_name} · {r.submitted_at || ""}
              </div>
              {r.detailed_scores && (
                <div className="text-xs font-mono text-gray-500 break-all">{formatMetricsSummary(r.detailed_scores)}</div>
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
