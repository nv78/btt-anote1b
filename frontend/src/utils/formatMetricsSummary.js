/** Compact one-line summary of API `detailed_scores` for leaderboard rows. */
export function formatMetricsSummary(detailedScores) {
  if (!detailedScores || typeof detailedScores !== "object") return null;
  const skip = new Set(["bertscore_unavailable"]);
  const parts = Object.entries(detailedScores)
    .filter(([k, v]) => v != null && typeof v === "number" && !skip.has(k))
    .map(([k, v]) => {
      const num = Number(v);
      const dec = Math.abs(num) < 1 ? 3 : 2;
      return `${k.replace(/_/g, " ")} ${num.toFixed(dec)}`;
    });
  return parts.length ? parts.join(" · ") : null;
}
