import React, { useEffect, useMemo, useState } from "react";

const METRIC_GROUPS = [
  {
    name: "Core",
    keys: ["accuracy", "f1", "exact_match", "bleu", "retrieval_accuracy", "balanced_accuracy"],
  },
  {
    name: "Precision / Recall",
    keys: [
      "precision",
      "recall",
      "micro_f1",
      "micro_precision",
      "micro_recall",
      "ner_f1",
      "ner_precision",
      "ner_recall",
      "partial_f1",
    ],
  },
  {
    name: "Semantic overlap",
    keys: ["rouge_1", "rouge_l", "meteor", "token_f1", "squad_f1", "squad_em"],
  },
  {
    name: "Ranking",
    keys: ["mrr", "map", "ndcg", "precision_at_1", "recall_at_1", "hits_at_10"],
  },
  {
    name: "Translation",
    keys: ["chrf", "ter"],
  },
];

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

function sentenceCase(value) {
  const text = String(value || "")
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .trim()
    .toLowerCase();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "Metric";
}

function buildMetricGroups(defs) {
  const allKeys = Object.keys(defs || {});
  const available = new Set(allKeys);
  const used = new Set();
  const groups = METRIC_GROUPS.map((group) => {
    const keys = group.keys.filter((key) => available.has(key));
    keys.forEach((key) => used.add(key));
    return { name: group.name, keys };
  });
  const otherKeys = allKeys.filter((key) => !used.has(key));
  groups.push({ name: "Other", keys: otherKeys });
  return groups.filter((group) => group.keys.length > 0);
}

/**
 * Full glossary + optional per-model values from evaluation detailed_scores.
 * Loads definitions from GET /api/metrics/task/:taskType
 */
export default function TaskAdvancedMetricsPanel({ apiBase, taskType, models, className = "" }) {
  const [defs, setDefs] = useState(null);
  const [normalizedTask, setNormalizedTask] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState({ Core: true });

  const modelRows = Array.isArray(models) && models.length > 0 ? models : [];
  const groupedMetrics = useMemo(() => buildMetricGroups(defs || {}), [defs]);

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
        <div className="text-[11px] text-gray-400 font-semibold uppercase tracking-wide inline-flex items-center gap-1.5">
          Advanced metrics for this task
          <span
            className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-gray-700 text-[10px] text-gray-500"
            title="Metrics are computed from each model's submitted predictions against hidden reference labels."
          >
            i
          </span>
        </div>
        {normalizedTask && (
          <div className="text-[10px] text-gray-600">
            Task key: <span className="text-gray-400 font-mono">{normalizedTask}</span>
          </div>
        )}
      </div>
      <div className="overflow-x-auto rounded-lg border border-gray-800/60">
        <table className="w-full text-left text-[11px] min-w-[44rem]">
          <thead>
            <tr className="bg-[#0a101a] text-[10px] uppercase tracking-wider text-gray-500">
              <th className="py-2 pl-2 pr-2 align-bottom sticky left-0 bg-[#0a101a] z-[1]">Metric</th>
              <th className="py-2 pr-2 align-bottom max-w-[14rem]">Formula</th>
              <th className="py-2 pr-2 align-bottom">Range</th>
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
            {groupedMetrics.map((group) => {
              const expanded = !!expandedGroups[group.name];
              return (
                <React.Fragment key={group.name}>
                  <tr
                    className="cursor-pointer bg-[#0b111d] hover:bg-[#111a2a] text-gray-300"
                    onClick={() => setExpandedGroups((prev) => ({ ...prev, [group.name]: !prev[group.name] }))}
                  >
                    <td colSpan={3 + modelRows.length} className="py-2 px-2">
                      <div className="flex items-center justify-between gap-4">
                        <span className="font-semibold">{group.name}</span>
                        <span className="text-gray-500">{expanded ? "▼" : "▶"}</span>
                      </div>
                    </td>
                  </tr>
                  {expanded &&
                    group.keys.map((key) => {
                      const meta = defs[key] || {};
                      return (
                        <tr key={key} className="hover:bg-white/[0.02]">
                          <td className="py-2 pl-2 pr-2 align-top sticky left-0 bg-[#0d1421]/95 z-[1] border-r border-gray-800/40">
                            <div className="text-[#EDDC8F] font-bold">{sentenceCase(meta.name || key)}</div>
                          </td>
                          <td className="py-2 pr-2 align-top text-gray-400 max-w-[14rem] leading-snug">
                            <code className="inline-block rounded-md bg-gray-800/80 px-2 py-1 text-[10px] text-gray-300">
                              {meta.formula || "—"}
                            </code>
                          </td>
                          <td className="py-2 pr-2 align-top text-gray-500 whitespace-nowrap">
                            <span className="inline-flex rounded-full border border-gray-700 bg-gray-900/80 px-2 py-0.5 text-[10px] text-gray-400">
                              {meta.range || "—"}
                            </span>
                          </td>
                          {modelRows.map((m, i) => (
                            <td key={`${m.model}-${key}-${i}`} className="py-2 px-1 text-right tabular-nums text-gray-300 align-top">
                              {formatValue(lookupDetailedScore(m.detailed_scores, key))}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
