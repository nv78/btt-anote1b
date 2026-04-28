import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { formatMetricsSummary } from "../../utils/formatMetricsSummary";
import { submittoleaderboardPath } from "../../constants/RouteConstants";

const API_BASE =
  process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001";

const MySubmissions = () => {
  const navigate = useNavigate();
  const [apiKey, setApiKey] = useState(() => localStorage.getItem("leaderboard_api_key") || "");
  const [submitterId, setSubmitterId] = useState(() => localStorage.getItem("leaderboard_submitter_id") || "");
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
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
    try {
      if (!submitterId.trim()) {
        setRows([]);
        setTotal(0);
        setError("Set a submitter id (same as on Submit page) or use JWT on the API.");
        setLoading(false);
        return;
      }
      const qs = new URLSearchParams({ submitter_id: submitterId.trim(), page: "1", page_size: "50" });
      const headers = {};
      if (apiKey.trim()) headers["X-API-Key"] = apiKey.trim();
      const res = await fetch(`${API_BASE}/public/my_submissions?${qs}`, { headers });
      const data = await res.json();
      if (!res.ok || data.success !== true) {
        throw new Error(data.error || "Failed to load");
      }
      setRows(data.submissions || []);
      setTotal(data.total || 0);
    } catch (e) {
      setError(e.message || "Error");
      setRows([]);
    } finally {
      setLoading(false);
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
          Lists rows where <code className="text-gray-300">submitter_id</code> matches your submissions (set on the Submit page or via JWT{" "}
          <code className="text-gray-300">sub</code> claim when using the API).
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
          {rows.map((r) => (
            <div
              key={r.submission_id}
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
      </div>
    </div>
  );
};

export default MySubmissions;
