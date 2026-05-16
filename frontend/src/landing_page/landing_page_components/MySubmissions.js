import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as d3 from "d3";
import { formatMetricsSummary } from "../../utils/formatMetricsSummary";
import { submittoleaderboardPath } from "../../constants/RouteConstants";
import { getLeaderboardJwt } from "../../utils/leaderboardAuth";

const API_BASE =
  process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001";

// ── Tiny sparkline chart ──────────────────────────────────────────────────────

const ScoreChart = ({ data }) => {
  // data: [{date: ISO string, score: number, model: string, dataset: string}]
  const svgRef = useRef(null);

  useEffect(() => {
    if (!svgRef.current || !data.length) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const W = svgRef.current.clientWidth || 600;
    const H = 180;
    const margin = { top: 12, right: 16, bottom: 36, left: 44 };
    const iW = W - margin.left - margin.right;
    const iH = H - margin.top - margin.bottom;

    const g = svg.attr("width", W).attr("height", H)
      .append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    const dates = data.map((d) => new Date(d.date));
    const scores = data.map((d) => d.score);

    const xScale = d3.scaleTime().domain(d3.extent(dates)).range([0, iW]);
    const yScale = d3.scaleLinear()
      .domain([Math.max(0, d3.min(scores) - 0.05), Math.min(1, d3.max(scores) + 0.05)])
      .range([iH, 0]);

    // group by dataset
    const byDataset = d3.group(data, (d) => d.dataset);
    const colorScale = d3.scaleOrdinal(d3.schemeTableau10).domain([...byDataset.keys()]);

    const line = d3.line()
      .x((d) => xScale(new Date(d.date)))
      .y((d) => yScale(d.score))
      .curve(d3.curveMonotoneX);

    byDataset.forEach((pts, dsName) => {
      const sorted = [...pts].sort((a, b) => new Date(a.date) - new Date(b.date));
      g.append("path")
        .datum(sorted)
        .attr("fill", "none")
        .attr("stroke", colorScale(dsName))
        .attr("stroke-width", 2)
        .attr("d", line);

      g.selectAll(null)
        .data(sorted)
        .join("circle")
        .attr("cx", (d) => xScale(new Date(d.date)))
        .attr("cy", (d) => yScale(d.score))
        .attr("r", 3)
        .attr("fill", colorScale(dsName))
        .append("title")
        .text((d) => `${d.dataset}\n${d.model}\n${d.score.toFixed(4)}\n${d.date}`);
    });

    g.append("g")
      .attr("transform", `translate(0,${iH})`)
      .call(d3.axisBottom(xScale).ticks(4).tickFormat(d3.timeFormat("%b %d")))
      .call((ax) => ax.select(".domain").attr("stroke", "#374151"))
      .call((ax) => ax.selectAll("text").attr("fill", "#9ca3af").attr("font-size", 10));

    g.append("g")
      .call(d3.axisLeft(yScale).ticks(4).tickFormat((v) => v.toFixed(2)))
      .call((ax) => ax.select(".domain").attr("stroke", "#374151"))
      .call((ax) => ax.selectAll("text").attr("fill", "#9ca3af").attr("font-size", 10));

    // legend
    let lx = 0;
    byDataset.forEach((_, dsName) => {
      const short = dsName.length > 20 ? dsName.slice(0, 18) + "…" : dsName;
      g.append("rect").attr("x", lx).attr("y", iH + 22).attr("width", 8).attr("height", 8).attr("fill", colorScale(dsName));
      g.append("text").attr("x", lx + 11).attr("y", iH + 30).attr("fill", "#9ca3af").attr("font-size", 9).text(short);
      lx += short.length * 5.5 + 16;
    });
  }, [data]);

  return <svg ref={svgRef} style={{ width: "100%", display: "block" }} />;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const formatScore = (value) => {
  if (typeof value !== "number") return value ?? "—";
  return value >= 0 && value <= 1 ? value.toFixed(4) : value.toFixed(2);
};

const authHeaders = (apiKey) => {
  const jwt = getLeaderboardJwt();
  const h = {};
  if (jwt) h["Authorization"] = `Bearer ${jwt}`;
  if (apiKey?.trim()) h["X-API-Key"] = apiKey.trim();
  return h;
};

// ── Main component ────────────────────────────────────────────────────────────

const MySubmissions = () => {
  const navigate = useNavigate();
  const [apiKey] = useState(() => localStorage.getItem("leaderboard_api_key") || "");
  const [submitterId] = useState(() => localStorage.getItem("leaderboard_submitter_id") || "");

  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [nextCursor, setNextCursor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [expandedRows, setExpandedRows] = useState({});
  const [quota, setQuota] = useState(null);
  const [showChart, setShowChart] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null); // submission_id pending delete
  const [actionBusy, setActionBusy] = useState({}); // {id: true} when delete/toggle in flight
  const [filterDataset, setFilterDataset] = useState("");

  const estimateQuota = (submissionRows) => {
    const today = new Date().toISOString().slice(0, 10);
    return (submissionRows || []).filter((r) => (r.submitted_at || "").slice(0, 10) === today).length;
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setNextCursor(null);
    const jwt = getLeaderboardJwt();
    if (!submitterId.trim() && !jwt) {
      setRows([]);
      setTotal(0);
      setQuota(null);
      setError("Sign in with Google or set a Submitter ID on the Submit page to view your submissions.");
      setLoading(false);
      return;
    }
    try {
      const qs = new URLSearchParams({ page_size: "50" });
      if (submitterId.trim()) qs.set("submitter_id", submitterId.trim());
      const res = await fetch(`${API_BASE}/public/my_submissions?${qs}`, { headers: authHeaders(apiKey) });
      const data = await res.json();
      if (!res.ok || data.success !== true) throw new Error(data.error || "Failed to load");
      const submissionRows = data.submissions || [];
      setRows(submissionRows);
      setTotal(data.total || 0);
      setNextCursor(data.next_cursor || null);

      // quota
      try {
        const qRes = await fetch(
          `${API_BASE}/public/submission_quota?${submitterId.trim() ? `submitter_id=${encodeURIComponent(submitterId.trim())}` : ""}`,
        );
        const qData = await qRes.json();
        const limit = Number(qData.daily_limit ?? 5);
        const used = Number(qData.used_today ?? Math.max(0, limit - Number(qData.remaining ?? limit)));
        setQuota({ daily_limit: limit, used_today: used, remaining: Math.max(0, limit - used) });
      } catch {
        const used = Math.min(5, estimateQuota(submissionRows));
        setQuota({ daily_limit: 5, used_today: used, remaining: Math.max(0, 5 - used) });
      }
    } catch (e) {
      setError(e.message || "Error");
      setRows([]);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey, submitterId]);

  const loadMore = async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const qs = new URLSearchParams({ page_size: "50", cursor: nextCursor });
      if (submitterId.trim()) qs.set("submitter_id", submitterId.trim());
      const res = await fetch(`${API_BASE}/public/my_submissions?${qs}`, { headers: authHeaders(apiKey) });
      const data = await res.json();
      if (!res.ok || data.success !== true) throw new Error(data.error || "Failed to load more");
      setRows((prev) => [...prev, ...(data.submissions || [])]);
      setNextCursor(data.next_cursor || null);
    } catch (e) {
      setError(e.message || "Error");
    } finally {
      setLoadingMore(false);
    }
  };

  useEffect(() => { load(); }, [load]);

  // ── Delete ────────────────────────────────────────────────────────────────

  const handleDelete = async (id) => {
    setActionBusy((p) => ({ ...p, [id]: true }));
    try {
      const res = await fetch(`${API_BASE}/public/submissions/${id}`, {
        method: "DELETE",
        headers: authHeaders(apiKey),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "Delete failed");
      setRows((prev) => prev.filter((r) => r.submission_id !== id));
      setTotal((t) => Math.max(0, t - 1));
    } catch (e) {
      setError(e.message);
    } finally {
      setActionBusy((p) => ({ ...p, [id]: false }));
      setDeleteConfirm(null);
    }
  };

  // ── Visibility toggle ─────────────────────────────────────────────────────

  const handleVisibilityToggle = async (id, currentlyPublic) => {
    setActionBusy((p) => ({ ...p, [`vis-${id}`]: true }));
    try {
      const res = await fetch(`${API_BASE}/public/submissions/${id}/visibility`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders(apiKey) },
        body: JSON.stringify({ is_public: !currentlyPublic }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "Update failed");
      setRows((prev) =>
        prev.map((r) => r.submission_id === id ? { ...r, is_public: data.is_public } : r)
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setActionBusy((p) => ({ ...p, [`vis-${id}`]: false }));
    }
  };

  // ── Derived data ──────────────────────────────────────────────────────────

  const filteredRows = filterDataset
    ? rows.filter((r) => r.dataset_name?.toLowerCase().includes(filterDataset.toLowerCase()))
    : rows;

  const chartData = rows
    .filter((r) => r.submitted_at && typeof r.score === "number")
    .map((r) => ({ date: r.submitted_at, score: r.score, model: r.model_name, dataset: r.dataset_name }));

  const datasets = [...new Set(rows.map((r) => r.dataset_name).filter(Boolean))].sort();

  const quotaLimit = quota?.daily_limit || 5;
  const quotaUsed = quota ? Math.min(quotaLimit, quota.used_today || 0) : 0;
  const quotaPercent = quotaLimit > 0 ? Math.min(100, (quotaUsed / quotaLimit) * 100) : 0;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#111827] text-gray-100 py-10 px-4">
      <div className="max-w-4xl mx-auto">

        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">My Submissions</h1>
            <p className="text-sm text-gray-400 mt-1">
              Track your model performance across benchmarks. Private submissions are hidden from the public leaderboard.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setShowChart((v) => !v)}
              className="text-sm px-3 py-2 rounded-lg border border-gray-600 text-gray-300 hover:bg-white/5"
            >
              {showChart ? "Hide chart" : "Score history"}
            </button>
            <button
              type="button"
              onClick={() => navigate(submittoleaderboardPath)}
              className="text-sm px-3 py-2 rounded-lg border border-[#defe47]/50 text-[#defe47] hover:bg-[#defe47]/10"
            >
              + Submit
            </button>
          </div>
        </div>

        {/* Score history chart */}
        {showChart && chartData.length > 0 && (
          <div className="mb-6 rounded-lg border border-gray-800 bg-[#0d1421] p-4">
            <h2 className="text-sm font-semibold text-white mb-3">Score over time</h2>
            <ScoreChart data={chartData} />
          </div>
        )}
        {showChart && chartData.length === 0 && (
          <div className="mb-6 rounded-lg border border-gray-800 bg-[#0d1421] p-4 text-sm text-gray-500">
            No scored submissions yet to chart.
          </div>
        )}

        {/* Quota bar */}
        {quota && (
          <div className="mb-6 rounded-lg border border-gray-800 bg-[#0d1421] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="font-semibold text-white">
                {quotaUsed} of {quotaLimit} daily submissions used
              </span>
              <span className="text-gray-400">{Math.max(0, quota.remaining || 0)} remaining today</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-gray-800">
              <div
                className="h-full rounded-full bg-[#defe47] transition-all"
                style={{ width: `${quotaPercent}%` }}
              />
            </div>
          </div>
        )}

        {/* Filters + refresh */}
        <div className="flex flex-wrap gap-2 mb-4">
          {datasets.length > 1 && (
            <select
              value={filterDataset}
              onChange={(e) => setFilterDataset(e.target.value)}
              className="px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white text-sm"
            >
              <option value="">All datasets</option>
              {datasets.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="px-3 py-2 rounded-md bg-gray-800 text-gray-300 text-sm hover:bg-gray-700 disabled:opacity-50"
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>

        {error && <div className="text-red-400 text-sm mb-4 p-3 rounded-lg bg-red-900/20 border border-red-800">{error}</div>}
        {!loading && <div className="text-xs text-gray-500 mb-2">Total: {total}{filterDataset ? ` (filtered)` : ""}</div>}

        {/* Delete confirmation dialog */}
        {deleteConfirm !== null && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
            <div className="bg-[#1a2332] border border-gray-700 rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl">
              <h3 className="text-white font-semibold mb-2">Delete submission?</h3>
              <p className="text-gray-400 text-sm mb-5">
                This will permanently remove the submission and its score from the leaderboard. This cannot be undone.
              </p>
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setDeleteConfirm(null)}
                  className="px-4 py-2 rounded-lg border border-gray-600 text-gray-300 text-sm hover:bg-white/5"
                >
                  Cancel
                </button>
                <button
                  onClick={() => handleDelete(deleteConfirm)}
                  disabled={actionBusy[deleteConfirm]}
                  className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-semibold hover:bg-red-500 disabled:opacity-50"
                >
                  {actionBusy[deleteConfirm] ? "Deleting…" : "Delete"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Submission list */}
        <div className="space-y-2">
          {loading && <div className="text-gray-400 text-sm">Loading…</div>}
          {!loading && filteredRows.length === 0 && !error && (
            <div className="text-gray-500 text-sm py-8 text-center">
              No submissions yet.{" "}
              <button
                onClick={() => navigate(submittoleaderboardPath)}
                className="text-[#defe47] underline"
              >
                Submit your first model
              </button>
            </div>
          )}
          {filteredRows.map((r, idx) => {
            const key = `${r.submission_id}-${idx}`;
            const isExpanded = expandedRows[key];
            const isPublic = r.is_public !== false && r.is_public !== 0;
            const visLoading = actionBusy[`vis-${r.submission_id}`];
            const delLoading = actionBusy[r.submission_id];

            return (
              <div
                key={key}
                className="bg-[#0d1421] border border-gray-800 rounded-lg overflow-hidden"
              >
                {/* Row header */}
                <div className="p-4 flex flex-col gap-1">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => setExpandedRows((p) => ({ ...p, [key]: !p[key] }))}
                      className="text-left flex-1 min-w-0"
                    >
                      <div className="flex flex-wrap justify-between gap-2">
                        <span className="font-medium text-white truncate">{r.dataset_name}</span>
                        <span className="tabular-nums text-[#defe47] shrink-0">{formatScore(r.score)}</span>
                      </div>
                      <div className="flex flex-wrap justify-between gap-2 text-gray-400 text-xs mt-1">
                        <span>{r.model_name} · {(r.submitted_at || "").slice(0, 10)}</span>
                        <span className="text-[#28b2fb]">{isExpanded ? "Hide" : "Details"}</span>
                      </div>
                      {r.detailed_scores && (
                        <div className="text-xs font-mono text-gray-500 break-all mt-1">
                          {formatMetricsSummary(r.detailed_scores)}
                        </div>
                      )}
                    </button>

                    {/* Action buttons */}
                    <div className="flex items-center gap-2 shrink-0 ml-2">
                      {/* Public/private toggle */}
                      <button
                        type="button"
                        onClick={() => handleVisibilityToggle(r.submission_id, isPublic)}
                        disabled={visLoading}
                        title={isPublic ? "Visible on leaderboard — click to make private" : "Private — click to make public"}
                        className={`text-xs px-2 py-1 rounded-md border transition-colors disabled:opacity-50 ${
                          isPublic
                            ? "border-green-700 text-green-400 hover:bg-green-900/20"
                            : "border-gray-600 text-gray-500 hover:bg-white/5"
                        }`}
                      >
                        {visLoading ? "…" : isPublic ? "Public" : "Private"}
                      </button>

                      {/* Delete */}
                      <button
                        type="button"
                        onClick={() => setDeleteConfirm(r.submission_id)}
                        disabled={delLoading}
                        title="Delete this submission"
                        className="text-xs px-2 py-1 rounded-md border border-red-900/60 text-red-500 hover:bg-red-900/20 disabled:opacity-50"
                      >
                        {delLoading ? "…" : "Delete"}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="border-t border-gray-800 bg-[#0a101a] p-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                      <div>
                        <div className="text-xs uppercase tracking-wide text-gray-500">Primary score</div>
                        <div className="text-3xl font-bold text-[#defe47] tabular-nums">{formatScore(r.score)}</div>
                        <div className="text-xs text-gray-500">{r.primary_metric || "primary metric"}</div>
                      </div>
                      <div className="md:col-span-2 text-xs text-gray-400 space-y-1">
                        <div><span className="text-gray-500">Dataset:</span> {r.dataset_name}</div>
                        <div><span className="text-gray-500">Task:</span> {r.task_type || "—"}</div>
                        <div><span className="text-gray-500">Submitted:</span> {r.submitted_at || "—"}</div>
                        <div>
                          <span className="text-gray-500">Visibility:</span>{" "}
                          <span className={isPublic ? "text-green-400" : "text-gray-400"}>
                            {isPublic ? "Public (appears on leaderboard)" : "Private (hidden from leaderboard)"}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead className="text-gray-500 uppercase tracking-wide">
                          <tr className="border-b border-gray-800">
                            <th className="text-left py-2 pr-3 font-semibold">Metric</th>
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
                              <td className="py-3 text-gray-500" colSpan={2}>No detailed scores.</td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Load more */}
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
