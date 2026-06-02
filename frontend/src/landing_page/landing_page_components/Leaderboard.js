import React, { useEffect, useMemo, useState } from "react";
import IconButton from "@mui/material/IconButton";
import Skeleton from "@mui/material/Skeleton";
import { addDatasetPath, csvBenchmarksPath, evaluationsPath, submittoleaderboardPath, compareModelsPath } from "../../constants/RouteConstants";
import { useNavigate } from "react-router-dom";
import { formatMetricsSummary } from "../../utils/formatMetricsSummary";

function humanizeMetricKey(metric) {
  if (!metric || String(metric).trim() === "") return "";
  return String(metric)
    .trim()
    .replace(/_/g, " ")
    .replace(/\b([a-z])/g, (c) => c.toUpperCase());
}

function domainMeta(datasetName, taskType) {
  const name = String(datasetName || "").toLowerCase();
  const task = String(taskType || "").toLowerCase();
  if (name.includes("financ") || name.includes("banking") || name.includes("phrasebank") || name.includes("finqa") || name.includes("fiq") || name.includes("wnut"))
    return { label: "Finance", className: "bg-emerald-500/15 text-emerald-300 border-emerald-400/30" };
  if (name.includes("medical") || name.includes("clinical") || name.includes("health") || name.includes("pubmed") || name.includes("bio") || name.includes("drug") || name.includes("pharma") || name.includes("mimic"))
    return { label: "Medical & Pharma", className: "bg-pink-500/15 text-pink-300 border-pink-400/30" };
  if (name.includes("legal") || name.includes("law") || name.includes("contract") || name.includes("court") || name.includes("statute"))
    return { label: "Legal", className: "bg-amber-500/15 text-amber-300 border-amber-400/30" };
  if (name.includes("code") || name.includes("mbpp") || name.includes("humaneval") || name.includes("gsm") || name.includes("math") || name.includes("aqua") || name.includes("ds-1000"))
    return { label: "Code & Math", className: "bg-cyan-500/15 text-cyan-300 border-cyan-400/30" };
  if (name.includes("science") || name.includes("arc") || name.includes("mmlu") || name.includes("commonsense") || name.includes("reasoning") || name.includes("hellaswag") || name.includes("winogrande"))
    return { label: "Science & Reasoning", className: "bg-violet-500/15 text-violet-300 border-violet-400/30" };
  if (name.includes("geoloc") || name.includes("location") || name.includes("geo") || name.includes("visual") || name.includes("image") || name.includes("vqa"))
    return { label: "Vision & Geography", className: "bg-teal-500/15 text-teal-300 border-teal-400/30" };
  if (name.includes("amazon") || name.includes("review") || name.includes("product") || name.includes("ecomm") || name.includes("shop"))
    return { label: "E-commerce", className: "bg-orange-500/15 text-orange-300 border-orange-400/30" };
  if (task === "translation" || name.includes("xnli") || name.includes("mgsm") || name.includes("xcopa") || name.includes("xquad") || name.includes("flores") || name.includes("multilingual") || name.includes("crosslingual"))
    return { label: "Multilingual", className: "bg-indigo-500/15 text-indigo-300 border-indigo-400/30" };
  if (task === "named_entity_recognition" || task === "ner" || name.includes("conll") || name.includes("ontonotes") || name.includes("relation") || name.includes("event"))
    return { label: "Information Extraction", className: "bg-rose-500/15 text-rose-300 border-rose-400/30" };
  if (task === "retrieval" || name.includes("retriev") || name.includes("rag") || name.includes("financebench") || name.includes("beir") || name.includes("msmarco"))
    return { label: "Retrieval / RAG", className: "bg-sky-500/15 text-sky-300 border-sky-400/30" };
  if (name.includes("cyber") || name.includes("security") || name.includes("malware") || name.includes("phish") || name.includes("vuln") || name.includes("cve"))
    return { label: "Cybersecurity", className: "bg-red-500/15 text-red-300 border-red-400/30" };
  if (name.includes("support") || name.includes("ticket") || name.includes("helpdesk") || name.includes("customer") || name.includes("dialogue") || name.includes("multiwoz"))
    return { label: "Customer Support", className: "bg-lime-500/15 text-lime-300 border-lime-400/30" };
  if (name.includes("edu") || name.includes("school") || name.includes("student") || name.includes("reading") || name.includes("essay") || name.includes("exam"))
    return { label: "Education", className: "bg-yellow-500/15 text-yellow-300 border-yellow-400/30" };
  if (name.includes("news") || name.includes("article") || name.includes("fake") || name.includes("headline") || name.includes("bbc") || name.includes("cnn"))
    return { label: "News & Journalism", className: "bg-blue-500/15 text-blue-300 border-blue-400/30" };
  if (name.includes("social") || name.includes("tweet") || name.includes("twitter") || name.includes("reddit") || name.includes("hate") || name.includes("toxic"))
    return { label: "Social Media", className: "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-400/30" };
  if (name.includes("hr") || name.includes("resum") || name.includes("job") || name.includes("recruit") || name.includes("hiring"))
    return { label: "HR & Recruiting", className: "bg-stone-500/15 text-stone-300 border-stone-400/30" };
  if (name.includes("climate") || name.includes("energy") || name.includes("environment") || name.includes("sustain"))
    return { label: "Climate & Energy", className: "bg-green-500/15 text-green-300 border-green-400/30" };
  return { label: "General NLP", className: "bg-gray-700/60 text-gray-300 border-gray-600/50" };
}

function taskBadgeMeta(taskType) {
  const key = String(taskType || "").toLowerCase();
  const badges = {
    text_classification:        { label: "Classification",  className: "bg-blue-500/15 text-blue-200 border-blue-400/30" },
    retrieval:                  { label: "Retrieval",       className: "bg-purple-500/15 text-purple-200 border-purple-400/30" },
    document_qa:                { label: "Q&A",             className: "bg-green-500/15 text-green-200 border-green-400/30" },
    translation:                { label: "Translation",     className: "bg-orange-500/15 text-orange-200 border-orange-400/30" },
    named_entity_recognition:   { label: "NER",             className: "bg-red-500/15 text-red-200 border-red-400/30" },
    ner:                        { label: "NER",             className: "bg-red-500/15 text-red-200 border-red-400/30" },
    summarization:              { label: "Summarization",   className: "bg-teal-500/15 text-teal-200 border-teal-400/30" },
    text_generation:            { label: "Generation",      className: "bg-violet-500/15 text-violet-200 border-violet-400/30" },
    multiple_choice_qa:         { label: "Multiple Choice", className: "bg-amber-500/15 text-amber-200 border-amber-400/30" },
    natural_language_inference: { label: "NLI",             className: "bg-pink-500/15 text-pink-200 border-pink-400/30" },
    semantic_similarity:        { label: "Similarity",      className: "bg-cyan-500/15 text-cyan-200 border-cyan-400/30" },
    code_generation:            { label: "Code",            className: "bg-emerald-500/15 text-emerald-200 border-emerald-400/30" },
    math_reasoning:             { label: "Math",            className: "bg-indigo-500/15 text-indigo-200 border-indigo-400/30" },
    fact_verification:          { label: "Fact Check",      className: "bg-rose-500/15 text-rose-200 border-rose-400/30" },
    dialogue:                   { label: "Dialogue",        className: "bg-sky-500/15 text-sky-200 border-sky-400/30" },
  };
  return badges[key] || {
    label: humanizeMetricKey(taskType) || "Task",
    className: "bg-gray-700/60 text-gray-300 border-gray-600/50",
  };
}

/** Extra numeric detailed_scores keys for leaderboard grid (excluding primary metric alias). */
function extraMetricKeys(models, evaluationMetric) {
  const pm = (evaluationMetric || "").toLowerCase().trim().replace(/\s+/g, "_");
  const seen = new Set();
  const ordered = [];
  for (const m of models || []) {
    const ds = m?.detailed_scores;
    if (!ds || typeof ds !== "object") continue;
    for (const [k, v] of Object.entries(ds)) {
      if (k === "bertscore_unavailable" || v == null || typeof v !== "number") continue;
      if (k.toLowerCase() === pm) continue;
      if (!seen.has(k)) {
        seen.add(k);
        ordered.push(k);
      }
    }
  }
  return ordered;
}

function formatMetricCell(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  const dec = Math.abs(value) < 1 ? 3 : 2;
  return value.toFixed(dec);
}

/** Display aggregate (0–100) from API composite_score, or scale legacy 0–1 primary scores for consistency. */
function formatAggregateScore(model) {
  if (typeof model.composite_score === "number" && !Number.isNaN(model.composite_score)) {
    return model.composite_score.toFixed(1);
  }
  const s = model.score;
  if (typeof s !== "number" || Number.isNaN(s)) return String(s ?? "—");
  if (s >= 0 && s <= 1) return (s * 100).toFixed(1);
  return s.toFixed(Math.abs(s) < 1 ? 3 : 2);
}

function compositeTooltip(model) {
  const br = model.composite_breakdown;
  if (!Array.isArray(br) || br.length === 0) return undefined;
  return br.map((x) => `${x.metric}: raw ${x.raw} (weight ${x.weight})`).join("\n");
}

function groupLeaderboardEntries(entries) {
  if (!Array.isArray(entries) || !entries.length) return [];
  const grouped = entries.reduce((acc, e) => {
    const key = e.dataset_name || "Unknown Dataset";
    if (!acc[key]) {
      acc[key] = {
        name: key,
        url: e.url || e.dataset_url || e.metadata?.url,
        evaluation_metric: e.evaluation_metric,
        task_type: e.task_type,
        submission_count: typeof e.submission_count === "number" ? e.submission_count : 0,
        models: [],
      };
    } else {
      if (e.task_type && !acc[key].task_type) acc[key].task_type = e.task_type;
      if (e.evaluation_metric && !acc[key].evaluation_metric) acc[key].evaluation_metric = e.evaluation_metric;
      if ((e.url || e.dataset_url || e.metadata?.url) && !acc[key].url) acc[key].url = e.url || e.dataset_url || e.metadata?.url;
      if (typeof e.submission_count === "number") acc[key].submission_count = Math.max(acc[key].submission_count || 0, e.submission_count);
    }
    const ciLow = e.ci_low ?? e.detailed_scores?.ci_low;
    const ciHigh = e.ci_high ?? e.detailed_scores?.ci_high;
    acc[key].models.push({
      model: e.model_name,
      score: typeof e.score === "number" ? e.score : Number(e.score) || 0,
      composite_score: typeof e.composite_score === "number" ? e.composite_score : undefined,
      composite_breakdown: Array.isArray(e.composite_breakdown) ? e.composite_breakdown : undefined,
      updated: e.submitted_at ? new Date(e.submitted_at).toLocaleDateString() : "",
      primary_metric: e.primary_metric,
      detailed_scores: e.detailed_scores,
      ci: (ciLow != null && ciHigh != null)
        ? `95% CI [${Number(ciLow).toFixed(3)}–${Number(ciHigh).toFixed(3)}]`
        : null,
    });
    return acc;
  }, {});
  return Object.values(grouped).map((d) => {
    const next = { ...d, models: [...d.models] };
    if (!next.submission_count) next.submission_count = next.models.length;
    next.models.sort((a, b) => {
      const ca =
        typeof a.composite_score === "number"
          ? a.composite_score
          : typeof a.score === "number" && a.score >= 0 && a.score <= 1
            ? a.score * 100
            : a.score;
      const cb =
        typeof b.composite_score === "number"
          ? b.composite_score
          : typeof b.score === "number" && b.score >= 0 && b.score <= 1
            ? b.score * 100
            : b.score;
      return Number(cb) - Number(ca);
    });
    next.models = next.models.map((m, i) => ({ rank: i + 1, ...m }));
    return next;
  });
}

const Leaderboard = () => {
  const [openIndex, setOpenIndex] = useState(null);
  const [expandedRankDepth, setExpandedRankDepth] = useState({});
  const [advancedMetrics, setAdvancedMetrics] = useState({});
  const [liveEntries, setLiveEntries] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [taskFilter, setTaskFilter] = useState("");
  const [domainFilter, setDomainFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [curatedDatasets, setCuratedDatasets] = useState([]);
  const [viewMode, setViewMode] = useState('live'); // 'live' | 'curated'
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [apiFailed, setApiFailed] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const API_BASE = process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001";

  const liveDatasets = useMemo(() => groupLeaderboardEntries(liveEntries), [liveEntries]);

  const refreshLeaderboard = () => {
    setApiFailed(false);
    setRefreshNonce((n) => n + 1);
  };

  useEffect(() => {
    let ignore = false;
    const run = async () => {
      setLoading(true);
      setError("");
      setApiFailed(false);
      setNextCursor(null);
      try {
        const url = new URL(`${API_BASE}/public/get_leaderboard`);
        url.searchParams.set("page_size", "40");
        const res = await fetch(url.toString());
        const data = await res.json();
        if (!res.ok || data.success !== true) throw new Error(data.error || "Failed to load leaderboard");
        const entries = Array.isArray(data.leaderboard) ? data.leaderboard : [];
        if (!ignore) {
          setLiveEntries(entries);
          setNextCursor(data.next_cursor || null);
        }
      } catch (e) {
        if (!ignore) {
          setError(e.message || "Error loading leaderboard");
          setApiFailed(true);
          setLiveEntries([]);
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    };
    run();
    return () => { ignore = true; };
  }, [API_BASE, refreshNonce]);

  const loadMoreLive = async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    setError("");
    try {
      const url = new URL(`${API_BASE}/public/get_leaderboard`);
      url.searchParams.set("page_size", "40");
      url.searchParams.set("cursor", nextCursor);
      const res = await fetch(url.toString());
      const data = await res.json();
      if (!res.ok || data.success !== true) throw new Error(data.error || "Failed to load more");
      const chunk = Array.isArray(data.leaderboard) ? data.leaderboard : [];
      setLiveEntries((prev) => [...prev, ...chunk]);
      setNextCursor(data.next_cursor || null);
    } catch (e) {
      setError(e.message || "Error loading more");
      setApiFailed(true);
    } finally {
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    let ignore = false;
    const run = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/leaderboard/list`);
        const data = await res.json();
        if (!res.ok || data.status !== 'success') throw new Error("Failed to load curated leaderboard");
        const groups = (data.datasets || []).map((d) => ({
          name: d.name,
          url: d.url,
          task_type: d.task_type,
          evaluation_metric: d.evaluation_metric || "",
          submission_count: Array.isArray(d.models) ? d.models.length : 0,
          models: (d.models || []).map((m) => ({
            rank: m.rank,
            model: m.model,
            score: m.score,
            updated: m.updated,
          })),
        }));
        if (!ignore) setCuratedDatasets(groups);
      } catch {
        if (!ignore) {
          setCuratedDatasets([]);
          setApiFailed(true);
        }
      }
    };
    run();
    return () => { ignore = true; };
  }, [API_BASE, refreshNonce]);

  useEffect(() => {
    if (!loading) {
      setIsDemoMode(liveDatasets.length === 0 && curatedDatasets.length === 0);
    }
  }, [loading, liveDatasets.length, curatedDatasets.length]);

  const handleClick = (index) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  const faqs = [
    {
      question: "Where can I find the evaluation datasets",
      answer:
        "You can access the evaluation set by following the dataset link listed with our submittoleaderboard component. If you have difficulty downloading them or need direct access, just send us an email at nvidra@anote.ai and we will provide the questions promptly.",
    },
    {
      question: "How many times can I submit?",
      answer:
        "There’s no strict limit on submissions. You’re welcome to submit multiple times, but for the most meaningful insights, we encourage you to submit only when there are substantial updates or improvements to your model.",
    },
    {
      question: "What am I expected to submit?",
      answer:
        "We only require the outputs your model generates for each query in the evaluation set. You do not need to share model weights, code, or other confidential information—simply the answers.",
    },
    {
      question: "When can I expect to receive the results for my submission?",
      answer:
        "We typically process and evaluate new submissions within a few business days. Once your results are ready, we will contact you via email with your score and ranking details.",
    },
    {
      question: "Do I need to give my LLM extra information to accurately run the tests?",
      answer:
        "We do not mandate any special pre-training or additional data, though you could use our fine tuning API. The goal is to see how your model performs under realistic conditions.",
    },
  ];


  const datasets = [
    {
      name: "FinanceBench - Retrieval Accuracy",
      task_type: "retrieval",
      evaluation_metric: "retrieval_accuracy",
      url: "https://github.com/patronus-ai/financebench",
      models: [
        {
          rank: 1,
          model: "GPT-4o Fine Tuned",
          score: 0.632,
          ci: "0.61 - 0.65",
          updated: "Oct 2024",
        },
        {
          rank: 2,
          model: "Mistral Fine Tuned",
          score: 0.612,
          ci: "0.59 - 0.63",
          updated: "Oct 2024",
        },
        {
          rank: 3,
          model: "LLaMA 3 Fine Tuned",
          score: 0.593,
          ci: "0.57 - 0.61",
          updated: "Oct 2024",
        },
        {
          rank: 4,
          model: "Re-ranking",
          score: 0.573,
          ci: "0.55 - 0.59",
          updated: "Oct 2024",
        },
        {
          rank: 5,
          model: "Query Expansiong",
          score: 0.256,
          ci: "0.24 - 0.27",
          updated: "Sep 2024",
        },
        {
          rank: 6,
          model: "Base Case RAG",
          score: 0.24,
          ci: "0.22 - 0.26",
          updated: "Sep 2024",
        },
      ],
    },
    {
      name: "Amazon Reviews - Classification Accuracy",
      task_type: "text_classification",
      evaluation_metric: "accuracy",
      url: "https://huggingface.co/datasets/m-ric/amazon_product_reviews_datafiniti",
      models: [
        {
          rank: 1,
          model: "GPT-4o",
          score: 0.94,
          ci: "0.92 - 0.96",
          updated: "Sep 2024",
        },
        {
          rank: 2,
          model: "GPT-3.5",
          score: 0.91,
          ci: "0.89 - 0.93",
          updated: "Sep 2024",
        },
        {
          rank: 3,
          model: "LLaMA 3",
          score: 0.9,
          ci: "0.88 - 0.92",
          updated: "Oct 2024",
        },
        {
          rank: 4,
          model: "BERT",
          score: 0.89,
          ci: "0.87 - 0.91",
          updated: "Sep 2024",
        },
        {
          rank: 5,
          model: "SetFit",
          score: 0.87,
          ci: "0.85 - 0.89",
          updated: "Sep 2024",
        },
        {
          rank: 6,
          model: "Claude 2",
          score: 0.86,
          ci: "0.83 - 0.87",
          updated: "Oct 2024",
        },
      ],
    },
    {
      name: "RAG Instruct - Answer Accuracy",
      task_type: "document_qa",
      evaluation_metric: "exact_match",
      url: "https://huggingface.co/datasets/llmware/rag_instruct_benchmark_tester",
      models: [
        {
          rank: 1,
          model: "GPT-4o",
          score: 0.89,
          ci: "0.87 - 0.91",
          updated: "Oct 2024",
        },
        {
          rank: 2,
          model: "GPT 3.5",
          score: 0.86,
          ci: "0.84 - 0.88",
          updated: "Oct 2024",
        },
        {
          rank: 3,
          model: "Llama3",
          score: 0.85,
          ci: "0.83 - 0.87",
          updated: "Oct 2024",
        },
        {
          rank: 4,
          model: "Claude 2",
          score: 0.83,
          ci: "0.81 - 0.85",
          updated: "Oct 2024",
        },
        {
          rank: 5,
          model: "GPT4ALL",
          score: 0.82,
          ci: "0.80 - 0.84",
          updated: "Oct 2024",
        },
        {
          rank: 6,
          model: "FLARE",
          score: 0.81,
          ci: "0.79 - 0.83",
          updated: "Oct 2024",
        },
      ],
    },
    {
      name: "Financial Phrasebank - Classify Accuracy",
      task_type: "text_classification",
      evaluation_metric: "f1",
      url: "https://huggingface.co/datasets/takala/financial_phrasebank",
      models: [
        {
          rank: 1,
          model: "Gemini",
          score: 0.95,
          ci: "0.93 - 0.97",
          updated: "Sep 2024",
        },
        {
          rank: 2,
          model: "GPT-4o",
          score: 0.93,
          ci: "0.91 - 0.95",
          updated: "Sep 2024",
        },
        {
          rank: 3,
          model: "Llama3",
          score: 0.92,
          ci: "0.90 - 0.94",
          updated: "Sep 2024",
        },
        {
          rank: 4,
          model: "BERT",
          score: 0.92,
          ci: "0.90 - 0.94",
          updated: "Sep 2024",
        },
        {
          rank: 5,
          model: "SetFit",
          score: 0.89,
          ci: "0.87 - 0.91",
          updated: "Sep 2024",
        },
        {
          rank: 6,
          model: "Claude 2",
          score: 0.87,
          ci: "0.85 - 0.88",
          updated: "Oct 2024",
        },
      ],
    },
    {
      name: "TREC - Hierarchical Classification Accuracy",
      task_type: "text_classification",
      evaluation_metric: "accuracy",
      url: "https://huggingface.co/datasets/CogComp/trec",
      models: [
        {
          rank: 1,
          model: "Claude 2",
          score: 0.85,
          ci: "0.83 - 0.87",
          updated: "Sep 2024",
        },
        {
          rank: 2,
          model: "GPT-4o",
          score: 0.82,
          ci: "0.80 - 0.84",
          updated: "Sep 2024",
        },
        {
          rank: 3,
          model: "Mistral",
          score: 0.81,
          ci: "0.79 - 0.83",
          updated: "Sep 2024",
        },
        {
          rank: 4,
          model: "BERT",
          score: 0.8,
          ci: "0.78 - 0.82",
          updated: "Sep 2024",
        },
        {
          rank: 5,
          model: "SetFit",
          score: 0.79,
          ci: "0.77 - 0.81",
          updated: "Sep 2024",
        },
      ],
    },
    {
      name: "Banking Dataset - Classification Accuracy",
      task_type: "text_classification",
      evaluation_metric: "accuracy",
      url: "https://huggingface.co/datasets/takala/financial_phrasebank",
      models: [
        {
          rank: 1,
          model: "GPT-4o",
          score: 0.93,
          ci: "0.91 - 0.95",
          updated: "Sep 2024",
        },
        {
          rank: 2,
          model: "Gemini",
          score: 0.91,
          ci: "0.89 - 0.93",
          updated: "Sep 2024",
        },
        {
          rank: 3,
          model: "Mistral",
          score: 0.9,
          ci: "0.88 - 0.92",
          updated: "Sep 2024",
        },
        {
          rank: 4,
          model: "BERT",
          score: 0.89,
          ci: "0.87 - 0.91",
          updated: "Sep 2024",
        },
        {
          rank: 5,
          model: "SetFit",
          score: 0.87,
          ci: "0.85 - 0.89",
          updated: "Sep 2024",
        },
      ],
    },
    {
      "name": "ARC-SMART",
      "task_type": "text_classification",
      "evaluation_metric": "accuracy",
      "url": "https://huggingface.co/datasets/vipulgupta/arc-smart",
      "models": [
        {
          "rank": 1,
          "model": "Qwen2-72B-Instruct",
          "score": 0.83,
          "updated": "Oct-2024"
        },
        {
          "rank": 2,
          "model": "Meta-Llama-3.1-70B-Instruct",
          "score": 0.819,
          "updated": "Oct-2024"
        },
        {
          "rank": 3,
          "model": "Meta-Llama-3-70B-Instruct",
          "score": 0.819,
          "updated": "Oct-2024"
        },
        {
          "rank": 4,
          "model": "Gemma-2-27b-it",
          "score": 0.788,
          "updated": "Oct-2024"
        },
        {
          "rank": 5,
          "model": "Phi-3.5-MoE-instruct",
          "score": 0.785,
          "updated": "Oct-2024"
        },
        {
          "rank": 6,
          "model": "Phi-3-medium-4k-instruct",
          "score": 0.781,
          "updated": "Oct-2024"
        },
        {
          "rank": 7,
          "model": "Mixtral-8x22B-Instruct-v0.1",
          "score": 0.762,
          "updated": "Oct-2024"
        },
        // {
        //   "rank": 8,
        //   "model": "Gemma-2-9b-it",
        //   "score": 0.757,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 9,
        //   "model": "Qwen1.5-32B-Chat",
        //   "score": 0.752,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 10,
        //   "model": "Yi-34B-Chat",
        //   "score": 0.745,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 11,
        //   "model": "Dbrx-instruct",
        //   "score": 0.732,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 12,
        //   "model": "Yi-1.5-9B-Chat",
        //   "score": 0.728,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 13,
        //   "model": "Yi-34B",
        //   "score": 0.724,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 14,
        //   "model": "Meta-Llama-3-8B-Instruct",
        //   "score": 0.721,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 15,
        //   "model": "Qwen2-7B-Instruct",
        //   "score": 0.697,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 16,
        //   "model": "Mixtral-8x7B-v0.1",
        //   "score": 0.688,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 17,
        //   "model": "Mixtral-8x7B-Instruct-v0.1",
        //   "score": 0.681,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 18,
        //   "model": "Internlm2_5-20b-chat",
        //   "score": 0.675,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 19,
        //   "model": "Internlm2_5-7b-chat",
        //   "score": 0.647,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 20,
        //   "model": "Llama-2-70b-hf",
        //   "score": 0.644,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 21,
        //   "model": "Gemma-7b",
        //   "score": 0.611,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 22,
        //   "model": "Mistral-7B-Instruct-v0.2",
        //   "score": 0.581,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 23,
        //   "model": "Mistral-7B-v0.3",
        //   "score": 0.563,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 24,
        //   "model": "Gemma-7b-it",
        //   "score": 0.531,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 25,
        //   "model": "Qwen-7B-Chat",
        //   "score": 0.518,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 26,
        //   "model": "Falcon-40b",
        //   "score": 0.51,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 27,
        //   "model": "Falcon-40b-instruct",
        //   "score": 0.507,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 28,
        //   "model": "Qwen-7B",
        //   "score": 0.476,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 29,
        //   "model": "OLMo-1.7-7B-hf",
        //   "score": 0.435,
        //   "updated": "Oct-2024"
        // }
      ]
    },
    {
      "name": "MMLU-SMART",
      "task_type": "text_classification",
      "evaluation_metric": "accuracy",
      "url": "https://huggingface.co/datasets/vipulgupta/mmlu-smart",
      "models": [
        {
          "rank": 1,
          "model": "Qwen2-72B-Instruct",
          "score": 0.743,
          "updated": "Oct-2024"
        },
        {
          "rank": 2,
          "model": "Meta-Llama-3.1-70B-Instruct",
          "score": 0.714,
          "updated": "Oct-2024"
        },
        {
          "rank": 3,
          "model": "Meta-Llama-3-70B-Instruct",
          "score": 0.692,
          "updated": "Oct-2024"
        },
        {
          "rank": 4,
          "model": "Phi-3.5-MoE-instruct",
          "score": 0.67,
          "updated": "Oct-2024"
        },
        {
          "rank": 5,
          "model": "Phi-3-medium-4k-instruct",
          "score": 0.656,
          "updated": "Oct-2024"
        },
        {
          "rank": 6,
          "model": "Mixtral-8x22B-Instruct-v0.1",
          "score": 0.653,
          "updated": "Oct-2024"
        },
        {
          "rank": 7,
          "model": "Gemma-2-27b-it",
          "score": 0.639,
          "updated": "Oct-2024"
        },
        // {
        //   "rank": 8,
        //   "model": "Yi-1.5-34B-Chat",
        //   "score": 0.634,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 9,
        //   "model": "Yi-34B",
        //   "score": 0.624,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 10,
        //   "model": "Qwen1.5-32B-Chat",
        //   "score": 0.615,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 11,
        //   "model": "Yi-34B-Chat",
        //   "score": 0.603,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 12,
        //   "model": "Dbrx-instruct",
        //   "score": 0.6,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 13,
        //   "model": "Gemma-2-9b-it",
        //   "score": 0.588,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 14,
        //   "model": "Internlm2_5-7b-chat",
        //   "score": 0.568,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 15,
        //   "model": "Mixtral-8x7B-v0.1",
        //   "score": 0.568,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 16,
        //   "model": "Internlm2_5-20b-chat",
        //   "score": 0.567,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 17,
        //   "model": "Mixtral-8x7B-Instruct-v0.1",
        //   "score": 0.565,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 18,
        //   "model": "Qwen2-7B-Instruct",
        //   "score": 0.564,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 19,
        //   "model": "Yi-1.5-9B-Chat",
        //   "score": 0.556,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 20,
        //   "model": "Llama-2-70b-hf",
        //   "score": 0.544,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 21,
        //   "model": "Meta-Llama-3-8B-Instruct",
        //   "score": 0.505,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 22,
        //   "model": "Gemma-7b",
        //   "score": 0.492,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 23,
        //   "model": "Mistral-7B-v0.3",
        //   "score": 0.468,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 24,
        //   "model": "Mistral-7B-Instruct-v0.2",
        //   "score": 0.441,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 25,
        //   "model": "Qwen-7B",
        //   "score": 0.426,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 26,
        //   "model": "Qwen-7B-Chat",
        //   "score": 0.415,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 27,
        //   "model": "Falcon-40b",
        //   "score": 0.412,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 28,
        //   "model": "Falcon-40b-instruct",
        //   "score": 0.402,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 29,
        //   "model": "Gemma-7b-it",
        //   "score": 0.389,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 30,
        //   "model": "OLMo-1.7-7B-hf",
        //   "score": 0.381,
        //   "updated": "Oct-2024"
        // }
      ]
    },
    {
      "name": "CommonsenseQA-SMART",
      "task_type": "text_classification",
      "evaluation_metric": "accuracy",
      "url": "https://huggingface.co/datasets/vipulgupta/commonsense_qa_smart",
      "models": [
        {
          "rank": 1,
          "model": "Qwen2-72B-Instruct",
          "score": 0.845,
          "updated": "Oct-2024"
        },
        {
          "rank": 2,
          "model": "Yi-1.5-34B-Chat",
          "score": 0.776,
          "updated": "Oct-2024"
        },
        {
          "rank": 3,
          "model": "Meta-Llama-3-70B-Instruct",
          "score": 0.771,
          "updated": "Oct-2024"
        },
        {
          "rank": 4,
          "model": "Qwen1.5-32B-Chat",
          "score": 0.767,
          "updated": "Oct-2024"
        },
        {
          "rank": 5,
          "model": "Meta-Llama-3.1-70B-Instruct",
          "score": 0.741,
          "updated": "Oct-2024"
        },
        {
          "rank": 6,
          "model": "Phi-3.5-MoE-instruct",
          "score": 0.739,
          "updated": "Oct-2024"
        },
        {
          "rank": 7,
          "model": "Gemma-2-9b-it",
          "score": 0.733,
          "updated": "Oct-2024"
        },
        // {
        //   "rank": 8,
        //   "model": "Qwen2-7B-Instruct",
        //   "score": 0.724,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 9,
        //   "model": "Phi-3-medium-4k-instruct",
        //   "score": 0.722,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 10,
        //   "model": "Gemma-2-27b-it",
        //   "score": 0.719,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 11,
        //   "model": "Yi-34B",
        //   "score": 0.718,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 12,
        //   "model": "Yi-1.5-9B-Chat",
        //   "score": 0.718,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 13,
        //   "model": "internlm2_5-7b-chat",
        //   "score": 0.714,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 14,
        //   "model": "Yi-34B-Chat",
        //   "score": 0.712,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 15,
        //   "model": "dbrx-instruct",
        //   "score": 0.704,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 16,
        //   "model": "internlm2_5-20b-chat",
        //   "score": 0.695,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 17,
        //   "model": "Meta-Llama-3-8B-Instruct",
        //   "score": 0.68,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 18,
        //   "model": "Mixtral-8x22B-Instruct-v0.1",
        //   "score": 0.672,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 19,
        //   "model": "OLMo-1.7-7B-hf",
        //   "score": 0.67,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 20,
        //   "model": "Mixtral-8x7B-Instruct-v0.1",
        //   "score": 0.6,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 21,
        //   "model": "gemma-7b-it",
        //   "score": 0.594,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 22,
        //   "model": "Mistral-7B-Instruct-v0.2",
        //   "score": 0.59,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 23,
        //   "model": "Qwen-7B",
        //   "score": 0.586,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 24,
        //   "model": "falcon-40b-instruct",
        //   "score": 0.579,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 25,
        //   "model": "Qwen-7B-Chat",
        //   "score": 0.557,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 26,
        //   "model": "gemma-7b",
        //   "score": 0.551,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 27,
        //   "model": "Mistral-7B-v0.3",
        //   "score": 0.499,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 28,
        //   "model": "Mixtral-8x7B-v0.1",
        //   "score": 0.468,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 29,
        //   "model": "Llama-2-70b-hf",
        //   "score": 0.465,
        //   "updated": "Oct-2024"
        // },
        // {
        //   "rank": 30,
        //   "model": "falcon-40b",
        //   "score": 0.446,
        //   "updated": "Oct-2024"
        // }
      ]
    },
    {
      "name": "Geolocation Inference - Median Distance Error",
      "task_type": "geolocation",
      "evaluation_metric": "median_distance_error",
      "url": "https://github.com/njspyx/location-inference",
      "models": [
          {
              "rank": 1,
              "model": "GPT-o1",
              "score": 182.73,
              "updated": "Feb 2025"
          },
          {
              "rank": 2,
              "model": "GPT-4o",
              "score": 216.13,
              "updated": "Feb 2025"
          },
          {
              "rank": 3,
              "model": "Gemini 1.5 Pro",
              "score": 287.27,
              "updated": "Feb 2025"
          },
          {
              "rank": 4,
              "model": "Gemini 1.5 Flash",
              "score": 298.86,
              "updated": "Feb 2025"
          },
          {
              "rank": 5,
              "model": "Gemini 1.5 Flash 8B",
              "score": 304.96,
              "updated": "Feb 2025"
          },
          {
              "rank": 6,
              "model": "GPT-4o Mini",
              "score": 380.85,
              "updated": "Feb 2025"
          },
          {
              "rank": 7,
              "model": "Claude 3.5 Sonnet",
              "score": 382.07,
              "updated": "Feb 2025"
          },
          {
              "rank": 8,
              "model": "Qwen2VL 7B Instruct",
              "score": 475.25,
              "updated": "Feb 2025"
          },
          // {
          //     "rank": 9,
          //     "model": "Llama3.2 90B Vision",
          //     "score": 712.41,
          //     "updated": "Feb 2025"
          // },
          // {
          //     "rank": 10,
          //     "model": "Claude 3 Haiku",
          //     "score": 744.08,
          //     "updated": "Feb 2025"
          // },
          // {
          //     "rank": 11,
          //     "model": "Claude 3 Opus",
          //     "score": 744.08,
          //     "updated": "Feb 2025"
          // },
          // {
          //     "rank": 12,
          //     "model": "Llama3.2 11B Vision",
          //     "score": 891.44,
          //     "updated": "Feb 2025"
          // },
          // {
          //     "rank": 13,
          //     "model": "Janus Pro 7B",
          //     "score": 1883.56,
          //     "updated": "Feb 2025"
          // },
          // {
          //     "rank": 14,
          //     "model": "Llava v1.6 Vicuna 13B",
          //     "score": 1580.76,
          //     "updated": "Feb 2025"
          // },
          // {
          //     "rank": 15,
          //     "model": "Llava v1.6 Yi 34B",
          //     "score": 2484.67,
          //     "updated": "Feb 2025"
          // },
          // {
          //     "rank": 16,
          //     "model": "Llava v1.6 Mistral 7B",
          //     "score": 3511.72,
          //     "updated": "Feb 2025"
          // }
      ]
  },

  // ── Information Extraction ──────────────────────────────────────────────
  {
    name: "CoNLL-2003 NER",
    task_type: "named_entity_recognition",
    evaluation_metric: "f1",
    url: "https://huggingface.co/datasets/conll2003",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.934, updated: "Jan 2025" },
      { rank: 2, model: "Claude 3.5 Sonnet", score: 0.928, updated: "Jan 2025" },
      { rank: 3, model: "Llama-3.1-70B", score: 0.921, updated: "Jan 2025" },
      { rank: 4, model: "Mistral-Large", score: 0.915, updated: "Jan 2025" },
      { rank: 5, model: "GPT-3.5 Turbo", score: 0.908, updated: "Jan 2025" },
    ],
  },

  // ── Medical & Pharma ────────────────────────────────────────────────────
  {
    name: "BC5CDR Chemical & Disease NER",
    task_type: "named_entity_recognition",
    evaluation_metric: "f1",
    url: "https://huggingface.co/datasets/bigbio/bc5cdr",
    models: [
      { rank: 1, model: "BioMedBERT-Large", score: 0.921, updated: "Dec 2024" },
      { rank: 2, model: "PubMedBERT", score: 0.914, updated: "Dec 2024" },
      { rank: 3, model: "GPT-4o", score: 0.897, updated: "Dec 2024" },
      { rank: 4, model: "BioBERT-v1.2", score: 0.893, updated: "Dec 2024" },
    ],
  },
  {
    name: "PubMedQA - Biomedical Q&A",
    task_type: "document_qa",
    evaluation_metric: "accuracy",
    url: "https://huggingface.co/datasets/qiaojin/PubMedQA",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.793, updated: "Jan 2025" },
      { rank: 2, model: "Claude 3.5 Sonnet", score: 0.781, updated: "Jan 2025" },
      { rank: 3, model: "MedPaLM-2", score: 0.768, updated: "Jan 2025" },
      { rank: 4, model: "Llama-3.1-70B", score: 0.752, updated: "Jan 2025" },
    ],
  },
  {
    name: "MedMCQA - Medical Multiple Choice",
    task_type: "multiple_choice_qa",
    evaluation_metric: "accuracy",
    url: "https://huggingface.co/datasets/medmcqa",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.732, updated: "Feb 2025" },
      { rank: 2, model: "Claude 3.5 Sonnet", score: 0.718, updated: "Feb 2025" },
      { rank: 3, model: "Gemini 1.5 Pro", score: 0.701, updated: "Feb 2025" },
      { rank: 4, model: "Llama-3.1-70B", score: 0.688, updated: "Feb 2025" },
    ],
  },

  // ── Legal ───────────────────────────────────────────────────────────────
  {
    name: "CUAD - Contract Understanding",
    task_type: "document_qa",
    evaluation_metric: "f1",
    url: "https://huggingface.co/datasets/theatticusproject/cuad",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.524, updated: "Jan 2025" },
      { rank: 2, model: "Claude 3.5 Sonnet", score: 0.512, updated: "Jan 2025" },
      { rank: 3, model: "DeBERTa-v3-Large", score: 0.487, updated: "Jan 2025" },
      { rank: 4, model: "GPT-3.5 Turbo", score: 0.461, updated: "Jan 2025" },
    ],
  },
  {
    name: "ECtHR - Legal Judgment Prediction",
    task_type: "text_classification",
    evaluation_metric: "accuracy",
    url: "https://huggingface.co/datasets/ecthr_cases",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.761, updated: "Dec 2024" },
      { rank: 2, model: "Legal-BERT", score: 0.748, updated: "Dec 2024" },
      { rank: 3, model: "Claude 3.5 Sonnet", score: 0.735, updated: "Dec 2024" },
      { rank: 4, model: "Llama-3.1-70B", score: 0.712, updated: "Dec 2024" },
    ],
  },

  // ── Code & Math ─────────────────────────────────────────────────────────
  {
    name: "HumanEval - Code Generation",
    task_type: "code_generation",
    evaluation_metric: "pass@1",
    url: "https://huggingface.co/datasets/openai/openai_humaneval",
    models: [
      { rank: 1, model: "Claude 3.5 Sonnet", score: 0.921, updated: "Mar 2025" },
      { rank: 2, model: "GPT-4o", score: 0.902, updated: "Mar 2025" },
      { rank: 3, model: "DeepSeek-Coder-33B", score: 0.879, updated: "Mar 2025" },
      { rank: 4, model: "Llama-3.1-70B", score: 0.721, updated: "Mar 2025" },
      { rank: 5, model: "CodeLlama-70B", score: 0.534, updated: "Mar 2025" },
    ],
  },
  {
    name: "GSM8K - Grade School Math",
    task_type: "math_reasoning",
    evaluation_metric: "accuracy",
    url: "https://huggingface.co/datasets/gsm8k",
    models: [
      { rank: 1, model: "GPT-o1", score: 0.972, updated: "Feb 2025" },
      { rank: 2, model: "Claude 3.5 Sonnet", score: 0.968, updated: "Feb 2025" },
      { rank: 3, model: "GPT-4o", score: 0.954, updated: "Feb 2025" },
      { rank: 4, model: "Gemini Ultra", score: 0.943, updated: "Feb 2025" },
      { rank: 5, model: "Llama-3.1-70B", score: 0.931, updated: "Feb 2025" },
    ],
  },

  // ── News & Journalism ───────────────────────────────────────────────────
  {
    name: "CNN/DailyMail - Summarization",
    task_type: "summarization",
    evaluation_metric: "rouge_l",
    url: "https://huggingface.co/datasets/cnn_dailymail",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.213, updated: "Jan 2025" },
      { rank: 2, model: "Claude 3.5 Sonnet", score: 0.209, updated: "Jan 2025" },
      { rank: 3, model: "Llama-3.1-70B", score: 0.198, updated: "Jan 2025" },
      { rank: 4, model: "Falcon-180B", score: 0.187, updated: "Jan 2025" },
    ],
  },
  {
    name: "FEVER - Fact Verification",
    task_type: "fact_verification",
    evaluation_metric: "accuracy",
    url: "https://huggingface.co/datasets/fever",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.891, updated: "Jan 2025" },
      { rank: 2, model: "Claude 3.5 Sonnet", score: 0.883, updated: "Jan 2025" },
      { rank: 3, model: "Llama-3.1-70B", score: 0.871, updated: "Jan 2025" },
      { rank: 4, model: "DeBERTa-v3-Large", score: 0.866, updated: "Jan 2025" },
    ],
  },

  // ── General NLP ─────────────────────────────────────────────────────────
  {
    name: "SNLI - Natural Language Inference",
    task_type: "natural_language_inference",
    evaluation_metric: "accuracy",
    url: "https://huggingface.co/datasets/snli",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.942, updated: "Dec 2024" },
      { rank: 2, model: "DeBERTa-v3-Large", score: 0.936, updated: "Dec 2024" },
      { rank: 3, model: "Claude 3.5 Sonnet", score: 0.929, updated: "Dec 2024" },
      { rank: 4, model: "Llama-3.1-70B", score: 0.918, updated: "Dec 2024" },
      { rank: 5, model: "RoBERTa-Large", score: 0.912, updated: "Dec 2024" },
    ],
  },
  {
    name: "STS-B - Semantic Textual Similarity",
    task_type: "semantic_similarity",
    evaluation_metric: "spearman",
    url: "https://huggingface.co/datasets/mteb/stsbenchmark-sts",
    models: [
      { rank: 1, model: "SimCSE-RoBERTa", score: 0.934, updated: "Dec 2024" },
      { rank: 2, model: "GPT-4o", score: 0.928, updated: "Dec 2024" },
      { rank: 3, model: "E5-Large-v2", score: 0.921, updated: "Dec 2024" },
      { rank: 4, model: "BGE-Large-EN", score: 0.918, updated: "Dec 2024" },
      { rank: 5, model: "sentence-t5-xxl", score: 0.912, updated: "Dec 2024" },
    ],
  },
  {
    name: "HellaSwag - Commonsense Text Completion",
    task_type: "text_generation",
    evaluation_metric: "accuracy",
    url: "https://huggingface.co/datasets/Rowan/hellaswag",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.962, updated: "Jan 2025" },
      { rank: 2, model: "Claude 3.5 Sonnet", score: 0.951, updated: "Jan 2025" },
      { rank: 3, model: "Llama-3.1-70B", score: 0.943, updated: "Jan 2025" },
      { rank: 4, model: "Mistral-Large", score: 0.934, updated: "Jan 2025" },
      { rank: 5, model: "Mistral-7B", score: 0.814, updated: "Jan 2025" },
    ],
  },

  // ── Social Media ────────────────────────────────────────────────────────
  {
    name: "TweetEval - Twitter Sentiment",
    task_type: "text_classification",
    evaluation_metric: "f1",
    url: "https://huggingface.co/datasets/tweet_eval",
    models: [
      { rank: 1, model: "RoBERTa-Twitter", score: 0.734, updated: "Nov 2024" },
      { rank: 2, model: "GPT-4o", score: 0.721, updated: "Nov 2024" },
      { rank: 3, model: "BERTweet-Large", score: 0.713, updated: "Nov 2024" },
      { rank: 4, model: "Claude 3.5 Sonnet", score: 0.698, updated: "Nov 2024" },
    ],
  },
  {
    name: "WNUT-17 - Emerging Entity NER",
    task_type: "named_entity_recognition",
    evaluation_metric: "f1",
    url: "https://huggingface.co/datasets/wnut_17",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.591, updated: "Nov 2024" },
      { rank: 2, model: "Claude 3.5 Sonnet", score: 0.582, updated: "Nov 2024" },
      { rank: 3, model: "BERTweet-Large", score: 0.571, updated: "Nov 2024" },
      { rank: 4, model: "RoBERTa-Large", score: 0.558, updated: "Nov 2024" },
    ],
  },

  // ── Customer Support ────────────────────────────────────────────────────
  {
    name: "MultiWOZ - Task-Oriented Dialogue",
    task_type: "dialogue",
    evaluation_metric: "inform_rate",
    url: "https://huggingface.co/datasets/multi_woz_v22",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.943, updated: "Jan 2025" },
      { rank: 2, model: "Claude 3.5 Sonnet", score: 0.931, updated: "Jan 2025" },
      { rank: 3, model: "Llama-3.1-70B", score: 0.918, updated: "Jan 2025" },
      { rank: 4, model: "SimpleTOD", score: 0.891, updated: "Jan 2025" },
    ],
  },

  // ── Retrieval / RAG ─────────────────────────────────────────────────────
  {
    name: "MS MARCO - Passage Retrieval",
    task_type: "retrieval",
    evaluation_metric: "mrr@10",
    url: "https://huggingface.co/datasets/ms_marco",
    models: [
      { rank: 1, model: "E5-Large-v2", score: 0.421, updated: "Dec 2024" },
      { rank: 2, model: "BGE-Large-EN", score: 0.418, updated: "Dec 2024" },
      { rank: 3, model: "Contriever-MSMARCO", score: 0.398, updated: "Dec 2024" },
      { rank: 4, model: "BM25", score: 0.371, updated: "Dec 2024" },
    ],
  },

  // ── Multilingual ────────────────────────────────────────────────────────
  {
    name: "XNLI - Cross-Lingual NLI",
    task_type: "natural_language_inference",
    evaluation_metric: "accuracy",
    url: "https://huggingface.co/datasets/xnli",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.873, updated: "Dec 2024" },
      { rank: 2, model: "mDeBERTa-v3-Base", score: 0.861, updated: "Dec 2024" },
      { rank: 3, model: "Claude 3.5 Sonnet", score: 0.849, updated: "Dec 2024" },
      { rank: 4, model: "XLM-RoBERTa-Large", score: 0.834, updated: "Dec 2024" },
      { rank: 5, model: "mBERT", score: 0.812, updated: "Dec 2024" },
    ],
  },

  // ── Education ───────────────────────────────────────────────────────────
  {
    name: "SciQ - Science Multiple Choice",
    task_type: "multiple_choice_qa",
    evaluation_metric: "accuracy",
    url: "https://huggingface.co/datasets/allenai/sciq",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.971, updated: "Nov 2024" },
      { rank: 2, model: "Claude 3.5 Sonnet", score: 0.963, updated: "Nov 2024" },
      { rank: 3, model: "Llama-3.1-70B", score: 0.948, updated: "Nov 2024" },
      { rank: 4, model: "GPT-3.5 Turbo", score: 0.921, updated: "Nov 2024" },
    ],
  },

  // ── Cybersecurity ───────────────────────────────────────────────────────
  {
    name: "CyberThreat - Malware Classification",
    task_type: "text_classification",
    evaluation_metric: "accuracy",
    url: "https://huggingface.co/datasets/kasrahabib/cyber_threat_intelligence",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.891, updated: "Jan 2025" },
      { rank: 2, model: "Claude 3.5 Sonnet", score: 0.874, updated: "Jan 2025" },
      { rank: 3, model: "SecBERT", score: 0.862, updated: "Jan 2025" },
      { rank: 4, model: "Llama-3.1-70B", score: 0.843, updated: "Jan 2025" },
    ],
  },

  // ── Finance (Summarization) ─────────────────────────────────────────────
  {
    name: "ECTSum - Earnings Call Summarization",
    task_type: "summarization",
    evaluation_metric: "rouge_l",
    url: "https://huggingface.co/datasets/mrSoul7766/ECTSum",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.318, updated: "Jan 2025" },
      { rank: 2, model: "Claude 3.5 Sonnet", score: 0.311, updated: "Jan 2025" },
      { rank: 3, model: "Llama-3.1-70B", score: 0.298, updated: "Jan 2025" },
      { rank: 4, model: "BART-Large-CNN", score: 0.287, updated: "Jan 2025" },
    ],
  },

  // ── HR & Recruiting ─────────────────────────────────────────────────────
  {
    name: "Resume NER - Skills & Entities",
    task_type: "named_entity_recognition",
    evaluation_metric: "f1",
    url: "https://huggingface.co/datasets/dataminr/resume-ner",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.923, updated: "Nov 2024" },
      { rank: 2, model: "RoBERTa-Large", score: 0.912, updated: "Nov 2024" },
      { rank: 3, model: "Claude 3.5 Sonnet", score: 0.904, updated: "Nov 2024" },
      { rank: 4, model: "BERT-Large", score: 0.891, updated: "Nov 2024" },
    ],
  },

  // ── Climate & Energy ────────────────────────────────────────────────────
  {
    name: "ClimaText - Climate Claim Detection",
    task_type: "text_classification",
    evaluation_metric: "f1",
    url: "https://huggingface.co/datasets/climatebert/climate_detection",
    models: [
      { rank: 1, model: "GPT-4o", score: 0.878, updated: "Dec 2024" },
      { rank: 2, model: "ClimateBERT", score: 0.861, updated: "Dec 2024" },
      { rank: 3, model: "Claude 3.5 Sonnet", score: 0.854, updated: "Dec 2024" },
      { rank: 4, model: "RoBERTa-Large", score: 0.839, updated: "Dec 2024" },
    ],
  },
  ];
  const navigate = useNavigate();

  // Always show static datasets merged with live data; live DB entries take precedence for matching names
  const mergeWithStatic = (live) => {
    const liveNames = new Set(live.map((d) => d.name));
    const staticOnly = datasets.filter((d) => !liveNames.has(d.name));
    return [...live, ...staticOnly];
  };

  const displayDatasets = viewMode === 'curated'
    ? (curatedDatasets.length ? mergeWithStatic(curatedDatasets) : datasets)
    : mergeWithStatic(liveDatasets);

  const TASK_PILLS = [
    { value: "", label: "All" },
    { value: "text_classification", label: "Classification" },
    { value: "named_entity_recognition", label: "NER" },
    { value: "document_qa", label: "Q&A" },
    { value: "multiple_choice_qa", label: "Multiple Choice" },
    { value: "retrieval", label: "Retrieval" },
    { value: "summarization", label: "Summarization" },
    { value: "translation", label: "Translation" },
    { value: "natural_language_inference", label: "NLI" },
    { value: "semantic_similarity", label: "Similarity" },
    { value: "code_generation", label: "Code" },
    { value: "math_reasoning", label: "Math" },
    { value: "text_generation", label: "Generation" },
    { value: "fact_verification", label: "Fact Check" },
    { value: "dialogue", label: "Dialogue" },
  ];

  const availableDomains = useMemo(() => {
    const seen = new Set();
    for (const d of displayDatasets) {
      seen.add(domainMeta(d.name, d.task_type).label);
    }
    return Array.from(seen).sort();
  }, [displayDatasets]);

  const filteredDatasets = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return displayDatasets.filter((d) => {
      if (taskFilter) {
        const tt = (d.task_type || "").toLowerCase();
        const match = tt === taskFilter || (taskFilter === "named_entity_recognition" && tt === "ner");
        if (!match) return false;
      }
      if (domainFilter && domainMeta(d.name, d.task_type).label !== domainFilter) return false;
      if (q && !(d.name || "").toLowerCase().includes(q)) return false;
      return true;
    });
  }, [displayDatasets, taskFilter, domainFilter, searchQuery]);

  const rankBadge = (rank) => {
    if (rank === 1) return <span title="1st place" className="mr-1">🥇</span>;
    if (rank === 2) return <span title="2nd place" className="mr-1">🥈</span>;
    if (rank === 3) return <span title="3rd place" className="mr-1">🥉</span>;
    return null;
  };

  return (
    <div className="flex flex-col items-center justify-start min-h-screen bg-[#111827] pb-24 px-4 text-gray-100">

      {/* ── Hero ── */}
      <header className="w-full max-w-4xl mt-10 pt-4 text-center relative">
        {/* Subtle glow behind headline */}
        <div className="absolute inset-0 -top-10 flex items-center justify-center pointer-events-none">
          <div className="w-96 h-40 rounded-full bg-[#defe47]/[0.04] blur-3xl" />
        </div>
        <div className="relative">
          {/* <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#28b2fb]/[0.08] border border-[#28b2fb]/20 text-xs uppercase tracking-[0.18em] text-[#28b2fb] mb-4 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-[#28b2fb] animate-pulse" />
            Anote Evaluations
          </div> */}
          <div className="flex items-center justify-center gap-2">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold tracking-tight bg-white bg-clip-text text-transparent leading-tight">
              Model Leaderboard
            </h1>
            <IconButton
              aria-label="Refresh leaderboard"
              title="Refresh leaderboard"
              onClick={refreshLeaderboard}
              size="small"
              sx={{
                color: "#d1d5db",
                border: "1px solid rgba(75,85,99,0.7)",
                width: 34,
                height: 34,
                "&:hover": { color: "#defe47", borderColor: "rgba(222,254,71,0.5)", backgroundColor: "rgba(222,254,71,0.08)" },
              }}
            >
              ⟳
            </IconButton>
          </div>
          <p className="mt-4 text-gray-400 text-sm md:text-base max-w-lg mx-auto leading-relaxed">
            Submit results, compare models, and track performance.
          </p>
          <div className="mt-5 flex items-center justify-center gap-3 flex-wrap">
            <button
              type="button"
              onClick={() => navigate(submittoleaderboardPath)}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#defe47] text-black text-sm font-semibold hover:bg-[#e8ff70] transition-colors"
            >
              Submit a model
            </button>
            <button
              type="button"
              onClick={() => navigate(compareModelsPath)}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-[#28b2fb]/50 text-[#28b2fb] text-sm font-semibold hover:bg-[#28b2fb]/10 transition-colors"
            >
              ⇄ Compare models
            </button>
          </div>
        </div>
      </header>

      {/* ── Filters ── */}
      <div className="w-full max-w-7xl mt-6 px-2 flex flex-col gap-3">
        {/* Task type pills */}
        <div className="flex flex-wrap gap-2">
          {TASK_PILLS.map((pill) => (
            <button
              key={pill.value}
              type="button"
              onClick={() => setTaskFilter(pill.value)}
              className={[
                "px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-colors",
                taskFilter === pill.value
                  ? "bg-[#defe47]/10 border-[#defe47]/50 text-[#defe47]"
                  : "bg-transparent border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-300",
              ].join(" ")}
            >
              {pill.label}
            </button>
          ))}
        </div>
        {/* Search + domain row */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search datasets…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="rounded-lg bg-[#0d1421] border border-gray-700 text-white text-xs pl-8 pr-3 py-1.5 w-48 focus:outline-none focus:border-gray-500 placeholder-gray-600"
            />
          </div>
          {/* Domain dropdown */}
          {availableDomains.length > 0 && (
            <>
              <span className="text-xs text-gray-500 shrink-0">Domain</span>
              <select
                value={domainFilter}
                onChange={(e) => setDomainFilter(e.target.value)}
                className="rounded-lg bg-[#0d1421] border border-gray-700 text-white text-xs px-3 py-1.5"
              >
                <option value="">All domains</option>
                {availableDomains.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </>
          )}
          {(taskFilter || domainFilter || searchQuery) && (
            <button
              type="button"
              onClick={() => { setTaskFilter(""); setDomainFilter(""); setSearchQuery(""); }}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {apiFailed && (
        <div className="mt-8 w-full max-w-7xl rounded-xl border border-yellow-500/40 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-100 flex items-center justify-between gap-3">
          <span>Could not reach the leaderboard API. Showing demo data.</span>
          <button
            type="button"
            className="shrink-0 rounded-lg border border-yellow-400/40 px-2.5 py-1 text-xs font-semibold text-yellow-100 hover:bg-yellow-400/10"
            onClick={() => setApiFailed(false)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* ── Loading / error ── */}
      {error && (
        <div className="mt-10 text-red-400 text-sm bg-red-900/20 border border-red-800/40 rounded-lg px-4 py-2.5">
          {error}
        </div>
      )}

      {/* ── Dataset cards ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 md:gap-6 mt-10 w-full max-w-7xl">
        {loading
          ? Array.from({ length: 3 }).map((_, index) => (
              <Skeleton
                key={`leaderboard-skeleton-${index}`}
                variant="rectangular"
                height={200}
                animation="pulse"
                sx={{ bgcolor: "rgba(75,85,99,0.28)", borderRadius: "1rem" }}
              />
            ))
          : isDemoMode && !apiFailed
            ? (
              <div className="md:col-span-2 rounded-2xl border border-gray-800 bg-[#0d1421] px-6 py-12 text-center">
                <div className="text-lg font-semibold text-white">No benchmark results yet.</div>
                <p className="mt-2 text-sm text-gray-400">Be the first to submit a model!</p>
                <button
                  type="button"
                  onClick={() => navigate(submittoleaderboardPath)}
                  className="mt-5 inline-flex items-center justify-center rounded-lg bg-[#defe47] px-4 py-2 text-sm font-semibold text-black hover:bg-[#e8ff70] transition-colors"
                >
                  Submit a model
                </button>
              </div>
            )
          : filteredDatasets.length === 0 && displayDatasets.length > 0
            ? (
              <div className="md:col-span-2 rounded-2xl border border-gray-800 bg-[#0d1421] px-6 py-12 text-center">
                <div className="text-base font-semibold text-white">No datasets match these filters.</div>
                <button
                  type="button"
                  onClick={() => { setTaskFilter(""); setDomainFilter(""); setSearchQuery(""); }}
                  className="mt-4 text-sm text-[#defe47] hover:underline"
                >
                  Clear filters
                </button>
              </div>
            )
          : filteredDatasets.map((dataset, index) => {
          const dkey = dataset.name || `idx-${index}`;
          const showAdv = !!advancedMetrics[dkey];
          const showAllRanks = !!expandedRankDepth[dkey];
          const extras = showAdv ? extraMetricKeys(dataset.models, dataset.evaluation_metric) : [];
          const taskBadge = taskBadgeMeta(dataset.task_type);
          const submissionCount = typeof dataset.submission_count === "number" ? dataset.submission_count : dataset.models.length;
          const visibleModels = showAllRanks ? dataset.models : dataset.models.slice(0, 3);
          const moreCount = Math.max(0, dataset.models.length - 3);
          const domainLabel = domainMeta(dataset.name, dataset.task_type);
          return (
          <div
            key={dataset.name || index}
            className="flex flex-col w-full bg-[#0d1421] rounded-2xl border border-gray-800/80 hover:border-gray-600 transition-colors duration-150 shadow-xl shadow-black/20 overflow-hidden group"
          >
            {/* Card header */}
            <div className="flex items-start justify-between gap-3 px-5 pt-5 pb-4 border-b border-gray-800/60">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2 min-w-0">
                  <h2 className="text-base font-bold text-white leading-snug truncate" title={dataset.name}>
                    {dataset.name}
                  </h2>
                  {dataset.url && (
                    <a
                      href={dataset.url}
                      className="text-xs text-gray-500 hover:text-[#defe47] transition-colors shrink-0"
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={`Open source for ${dataset.name}`}
                    >
                      ↗ Source
                    </a>
                  )}
                  {isDemoMode && (
                    <span className="bg-gray-700 text-gray-300 text-xs px-2 py-0.5 rounded-full ml-2 shrink-0">
                      Demo
                    </span>
                  )}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {dataset.task_type && (
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${taskBadge.className}`}>
                      {taskBadge.label}
                    </span>
                  )}
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${domainLabel.className}`}>
                    {domainLabel.label}
                  </span>
                  {dataset.evaluation_metric && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-gray-800/80 text-[11px] text-gray-400 font-medium border border-gray-700/50">
                      {humanizeMetricKey(dataset.evaluation_metric)}
                    </span>
                  )}
                </div>
                {typeof submissionCount === "number" && (
                  <div className="mt-1.5 text-xs text-gray-500">
                    {submissionCount} {submissionCount === 1 ? "submission" : "submissions"}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  type="button"
                  className={`text-[11px] px-2.5 py-1.5 rounded-lg border transition-colors ${showAdv ? "border-[#28b2fb]/50 text-[#28b2fb] bg-[#28b2fb]/10" : "border-gray-700/60 text-gray-500 hover:text-[#28b2fb] hover:border-[#28b2fb]/30"}`}
                  onClick={() => setAdvancedMetrics((prev) => ({ ...prev, [dkey]: !prev[dkey] }))}
                >
                  {showAdv ? "Hide metrics" : "Advanced metrics"}
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-gray-700/60 text-gray-500 hover:text-[#28b2fb] hover:border-[#28b2fb]/30 transition-colors"
                  onClick={() => navigate(`/dataset/${encodeURIComponent(dataset.name)}`, {
                    state: {
                      name: dataset.name,
                      task_type: dataset.task_type,
                      evaluation_metric: dataset.evaluation_metric,
                      url: dataset.url,
                      description: dataset.description,
                      models: dataset.models,
                    }
                  })}
                >
                  Details
                </button>
              </div>
            </div>

            {/* Rankings table */}
            <div className="flex-1 overflow-x-auto min-w-0">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-gray-800/40">
                    <th className="text-[10px] font-semibold uppercase tracking-widest text-gray-600 text-left px-5 py-2.5 w-12">Rank</th>
                    <th className="text-[10px] font-semibold uppercase tracking-widest text-gray-600 text-left px-2 py-2.5">Model</th>
                    <th
                      className="text-[10px] font-semibold uppercase tracking-widest text-gray-600 text-right px-5 py-2.5 w-28"
                      title="Weighted aggregate (0–100) over reported metrics; hover a row for the breakdown."
                    >
                      Score
                    </th>
                    {extras.map((ek) => (
                      <th key={ek} className="text-[10px] font-semibold uppercase tracking-widest text-gray-600 text-right px-2 py-2.5 w-22 max-w-[5.5rem]" title={ek}>
                        <span className="block truncate">{humanizeMetricKey(ek)}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/30">
                  {visibleModels.map((model, modelIndex) => {
                    const isTop = model.rank === 1;
                    const agg = formatAggregateScore(model);
                    return (
                      <tr
                        key={modelIndex}
                        className={[
                          "text-sm transition-colors",
                          isTop
                            ? "bg-[#defe47]/[0.04] hover:bg-[#defe47]/[0.08]"
                            : "hover:bg-white/[0.03]",
                        ].join(" ")}
                      >
                        <td className="px-5 py-2.5 font-semibold text-gray-400">
                          <div className="flex items-center gap-1">
                            {rankBadge(model.rank)}
                            {model.rank > 3 && (
                              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-gray-800 text-[11px] text-gray-500 tabular-nums font-mono">
                                {model.rank}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-2 py-2.5 min-w-[9rem] max-w-xs">
                          <div
                            className={["font-medium truncate", isTop ? "text-white" : "text-gray-300"].join(" ")}
                            title={model.model}
                          >
                            {model.model}
                          </div>
                        </td>
                        <td className="px-5 py-2.5 text-right">
                          <span
                            className={[
                              "tabular-nums font-semibold",
                              isTop ? "text-[#defe47]" : model.rank === 2 ? "text-gray-100" : "text-gray-400",
                            ].join(" ")}
                            title={compositeTooltip(model) || undefined}
                          >
                            {agg}
                          </span>
                          {model.primary_metric && (
                            <div className="text-[10px] text-gray-600 leading-none mt-0.5">{model.primary_metric}</div>
                          )}
                          {model.ci && (
                            <div className="text-[10px] text-gray-600 leading-none mt-0.5">{model.ci}</div>
                          )}
                        </td>
                        {extras.map((ek) => (
                          <td key={ek} className="px-2 py-2.5 text-right tabular-nums text-[11px] text-gray-400 w-22">
                            {formatMetricCell(model.detailed_scores?.[ek])}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {moreCount > 0 && (
                <div className="flex justify-center py-2.5 border-t border-gray-800/30">
                  <button
                    type="button"
                    className="flex items-center gap-1.5 text-[11px] text-gray-500 hover:text-[#defe47] transition-colors px-3 py-1 rounded-lg hover:bg-[#defe47]/5"
                    onClick={() => setExpandedRankDepth((prev) => ({ ...prev, [dkey]: !prev[dkey] }))}
                    aria-label={showAllRanks ? "Collapse rankings" : `Show ${moreCount} more models`}
                  >
                    {!showAllRanks && <span>{moreCount} more</span>}
                    <svg
                      className={`w-3.5 h-3.5 transition-transform duration-200 ${showAllRanks ? "rotate-180" : ""}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2.5}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                </div>
              )}
            </div>

          </div>
          );
        })}
      </div>

      {viewMode === "live" && nextCursor && !loading && (
        <div className="mt-10 flex flex-col items-center gap-2 w-full max-w-7xl">
          <button
            type="button"
            onClick={loadMoreLive}
            disabled={loadingMore}
            className="px-5 py-2.5 rounded-xl text-sm font-semibold border border-[#defe47]/50 text-[#defe47] hover:bg-[#defe47]/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loadingMore ? "Loading…" : "Load more results"}
          </button>
          <p className="text-xs text-gray-500">Uses keyset pagination from the API.</p>
        </div>
      )}

      {/* ── FAQs ── */}
      <div className="w-full max-w-3xl mx-auto mt-24 px-2">
        <div className="mb-8 text-center">
          <span className="inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-[#28b2fb] font-medium">
            <span className="w-4 h-px bg-[#28b2fb]/50" />
            Help
            <span className="w-4 h-px bg-[#28b2fb]/50" />
          </span>
          <h2 className="text-2xl md:text-3xl font-bold text-white mt-2">Frequently Asked Questions</h2>
        </div>
        <div className="space-y-2">
          {faqs.map((faq, index) => (
            <div
              key={index}
              className="bg-[#0d1421] rounded-xl border border-gray-800/80 hover:border-gray-700/80 transition-colors overflow-hidden"
            >
              <button
                className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left cursor-pointer"
                onClick={() => handleClick(index)}
              >
                <span className="text-sm md:text-base font-semibold text-gray-100">
                  {faq.question}
                </span>
                <span className={["text-gray-500 transition-transform duration-200 shrink-0", openIndex === index ? "rotate-180" : ""].join(' ')}>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </span>
              </button>
              {openIndex === index && (
                <div className="px-5 pb-5 text-sm text-gray-400 leading-relaxed border-t border-gray-800/40 pt-3.5">
                  {faq.answer}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};

export default Leaderboard;
