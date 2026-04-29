import React, { useEffect, useState } from "react";

/** Find a numeric value in detailed_scores for a catalog key (case / separator tolerant). */
export function lookupDetailedScore(detailedScores, catalogKey) {
  if (!detailedScores || typeof detailedScores !== "object") return null;
  const want = String(catalogKey).toLowerCase().replace(/-/g, "_");
  for (const [k, v] of Object.entries(detailedScores)) {
    if (k === "bertscore_unavailable" || k === "metric") continue;
    const kk = String(k).toLowerCase().replace(/-/g, "_");
    if (kk === want && typeof v === "number" && !Number.isNaN(v)) return v;
  }
  return null;
}

function formatValue(val) {
  if (typeof val !== "number" || Number.isNaN(val)) return "—";
  const a = Math.abs(val);
  if (a <= 1) return val.toFixed(3);
  if (a < 100) return val.toFixed(2);
  return val.toFixed(1);
}

/**
 * Full glossary + optional per-model values from evaluation detailed_scores.
 * Loads definitions from GET /api/metrics/task/:taskType
 */
export default function TaskAdvancedMetricsPanel({ apiBase, taskType, models, className = "" }) {
  const [defs, setDefs] = useState(null);
  const [normalizedTask, setNormalizedTask] = useState("");
  const [loading, setLoading] = useState(false);

  const modelRows = Array.isArray(models) && models.length > 0 ? models : [];

  useEffect(() => {
    const tt = taskType || "text_classification";
    let ignore = false;
    setLoading(true);
    setDefs(null);
    fetch(`${apiBase}/api/metrics/task/${encodeURIComponent(tt)}`)
      .then((r) => r.json())
      .then((j) => {
        if (ignore) return;
        if (j.success && j.metrics && typeof j.metrics === "object") {
          setDefs(j.metrics);
          setNormalizedTask(j.task_type_normalized || tt);
        } else {
          setDefs({});
        }
      })
      .catch(() => {
        if (!ignore) setDefs({});
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [apiBase, taskType]);

  if (loading && !defs) {
    return (
      <div className={`border-t border-gray-800/40 bg-black/25 px-4 py-3 text-xs text-gray-500 ${className}`.trim()}>
        Loading metric definitions…
      </div>
    );
  }

  const keys = defs ? Object.keys(defs) : [];
  if (!keys.length) {
    return (
      <div className={`border-t border-gray-800/40 bg-black/25 px-4 py-3 text-xs text-gray-500 ${className}`.trim()}>
        No metric glossary available for this task type.
      </div>
    );
  }

  return (
    <div className={`border-t border-gray-800/40 bg-black/25 px-3 py-3 ${className}`.trim()}>
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-2 px-1">
        <div className="text-[11px] text-gray-400 font-semibold uppercase tracking-wide">
          Advanced metrics for this task
        </div>
        {normalizedTask && (
          <div className="text-[10px] text-gray-600">
            Task key: <span className="text-gray-400 font-mono">{normalizedTask}</span>
          </div>
        )}
      </div>
      <p className="text-[10px] text-gray-500 px-1 mb-2">
        Values come from evaluation <span className="font-mono text-gray-400">detailed_scores</span> when the run reports them;
        dashes mean that metric was not returned for that model.
      </p>
      <div className="overflow-x-auto rounded-lg border border-gray-800/60">
        <table className="w-full text-left text-[11px] min-w-[20rem]">
          <thead>
            <tr className="bg-[#0a101a] text-[10px] uppercase tracking-wider text-gray-500">
              <th className="py-2 pl-2 pr-2 align-bottom sticky left-0 bg-[#0a101a] z-[1]">Metric</th>
              <th className="py-2 pr-2 align-bottom hidden lg:table-cell max-w-[14rem]">How it&apos;s computed</th>
              <th className="py-2 pr-2 align-bottom hidden md:table-cell">Typical range</th>
              {modelRows.map((m, i) => (
                <th
                  key={`${m.model}-${i}`}
                  className="py-2 px-1 text-right align-bottom text-gray-400 font-medium truncate max-w-[6rem]"
                  title={m.model}
                >
                  {m.model}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/70">
            {keys.map((key) => {
              const meta = defs[key] || {};
              return (
                <tr key={key} className="hover:bg-white/[0.02]">
                  <td className="py-2 pl-2 pr-2 align-top sticky left-0 bg-[#0d1421]/95 z-[1] border-r border-gray-800/40">
                    <div className="text-[#EDDC8F] font-medium">{meta.name || key}</div>
                    <div className="text-[10px] text-gray-500 mt-0.5 lg:hidden">{meta.formula}</div>
                  </td>
                  <td className="py-2 pr-2 align-top text-gray-400 hidden lg:table-cell max-w-[14rem] leading-snug">
                    {meta.formula || "—"}
                  </td>
                  <td className="py-2 pr-2 align-top text-gray-500 hidden md:table-cell whitespace-nowrap">
                    {meta.range || "—"}
                  </td>
                  {modelRows.map((m, i) => (
                    <td key={`${m.model}-${key}-${i}`} className="py-2 px-1 text-right tabular-nums text-gray-300 align-top">
                      {formatValue(lookupDetailedScore(m.detailed_scores, key))}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
