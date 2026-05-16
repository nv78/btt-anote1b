import React, { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001";

const STATUS_COLORS = {
  pending: "bg-yellow-500/15 text-yellow-300 border-yellow-400/30",
  approved: "bg-emerald-500/15 text-emerald-300 border-emerald-400/30",
  rejected: "bg-red-500/15 text-red-300 border-red-400/30",
};

export default function AdminDatasetRequests() {
  const [adminKey, setAdminKey] = useState(() => localStorage.getItem("leaderboard_admin_key") || "");
  const [requests, setRequests] = useState([]);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [actionState, setActionState] = useState({}); // { [id]: { notes, submitting, error } }

  const headers = useCallback(() => ({
    "Content-Type": "application/json",
    "X-Admin-Key": adminKey.trim(),
  }), [adminKey]);

  const load = useCallback(async () => {
    if (!adminKey.trim()) return;
    localStorage.setItem("leaderboard_admin_key", adminKey.trim());
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/admin/dataset_requests?status=${statusFilter}`, { headers: headers() });
      const data = await res.json();
      if (!res.ok || data.success !== true) throw new Error(data.error || "Failed to load");
      setRequests(data.requests || []);
    } catch (e) {
      setError(e.message || "Failed to load requests");
    } finally {
      setLoading(false);
    }
  }, [adminKey, statusFilter, headers]);

  useEffect(() => { load(); }, [load]);

  const updateAction = (id, patch) =>
    setActionState((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));

  const act = async (id, action) => {
    updateAction(id, { submitting: true, error: "" });
    try {
      const res = await fetch(`${API_BASE}/api/admin/dataset_requests/${id}/${action}`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ admin_notes: actionState[id]?.notes || "" }),
      });
      const data = await res.json();
      if (!res.ok || data.success !== true) throw new Error(data.error || `${action} failed`);
      await load();
    } catch (e) {
      updateAction(id, { error: e.message || `${action} failed` });
    } finally {
      updateAction(id, { submitting: false });
    }
  };

  return (
    <div className="min-h-screen bg-[#111827] text-gray-100 px-4 py-12">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white">Dataset Requests</h1>
          <p className="text-gray-400 text-sm mt-1">Review, approve, or reject user-submitted dataset requests.</p>
        </div>

        {/* Admin key input */}
        <div className="mb-6 flex gap-2 items-center">
          <input
            type="password"
            placeholder="Admin key"
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            className="rounded-lg bg-[#0d1421] border border-gray-700 text-white text-sm px-3 py-2 w-56 focus:outline-none focus:border-[#defe47]/50"
          />
          <button
            type="button"
            onClick={load}
            className="rounded-lg border border-gray-700 text-gray-300 text-sm px-4 py-2 hover:border-gray-500 transition-colors"
          >
            Load
          </button>
        </div>

        {/* Status filter */}
        <div className="flex gap-2 mb-6">
          {["pending", "approved", "rejected", ""].map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatusFilter(s)}
              className={[
                "px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-colors",
                statusFilter === s
                  ? "bg-[#defe47]/10 border-[#defe47]/50 text-[#defe47]"
                  : "bg-transparent border-gray-700 text-gray-400 hover:border-gray-500",
              ].join(" ")}
            >
              {s === "" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-gray-500 text-sm">Loading…</p>
        ) : requests.length === 0 ? (
          <div className="rounded-2xl border border-gray-800 bg-[#0d1421] px-6 py-12 text-center">
            <p className="text-gray-500 text-sm">No {statusFilter} requests.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {requests.map((req) => {
              const a = actionState[req.id] || {};
              return (
                <div key={req.id} className="rounded-2xl border border-gray-800 bg-[#0d1421] p-5">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div>
                      <h2 className="text-base font-bold text-white">{req.dataset_name}</h2>
                      <div className="flex flex-wrap gap-2 mt-1">
                        <span className="text-xs text-gray-500">{req.task_type.replace(/_/g, " ")}</span>
                        {req.url && (
                          <a href={req.url} target="_blank" rel="noopener noreferrer" className="text-xs text-[#28b2fb] hover:underline">
                            {req.url}
                          </a>
                        )}
                      </div>
                    </div>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${STATUS_COLORS[req.status]}`}>
                      {req.status}
                    </span>
                  </div>

                  <p className="text-sm text-gray-300 mb-3 leading-relaxed">{req.description}</p>

                  <div className="flex flex-wrap gap-4 text-xs text-gray-500 mb-4">
                    <span>From: <span className="text-gray-400">{req.requested_by}</span></span>
                    <span>Submitted: <span className="text-gray-400">{new Date(req.created).toLocaleDateString()}</span></span>
                    {req.reviewed_at && (
                      <span>Reviewed: <span className="text-gray-400">{new Date(req.reviewed_at).toLocaleDateString()}</span></span>
                    )}
                  </div>

                  {req.admin_notes && (
                    <div className="mb-4 rounded-lg bg-gray-800/50 px-3 py-2 text-xs text-gray-400">
                      <span className="text-gray-500">Notes: </span>{req.admin_notes}
                    </div>
                  )}

                  {req.status === "pending" && (
                    <div className="flex flex-col gap-2">
                      <textarea
                        rows={2}
                        placeholder="Admin notes (optional)…"
                        value={a.notes || ""}
                        onChange={(e) => updateAction(req.id, { notes: e.target.value })}
                        className="w-full rounded-lg bg-gray-900 border border-gray-700 text-white text-xs px-3 py-2 focus:outline-none focus:border-gray-500 resize-none"
                      />
                      {a.error && <p className="text-xs text-red-400">{a.error}</p>}
                      <div className="flex gap-2">
                        <button
                          type="button"
                          disabled={a.submitting}
                          onClick={() => act(req.id, "approve")}
                          className="rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2 transition-colors"
                        >
                          {a.submitting ? "…" : "Approve"}
                        </button>
                        <button
                          type="button"
                          disabled={a.submitting}
                          onClick={() => act(req.id, "reject")}
                          className="rounded-lg border border-red-500/50 hover:border-red-400 disabled:opacity-50 text-red-400 text-xs font-semibold px-4 py-2 transition-colors"
                        >
                          {a.submitting ? "…" : "Reject"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
