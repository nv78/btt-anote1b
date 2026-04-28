import React, { useEffect, useMemo, useState } from "react";
import { addDatasetPath, csvBenchmarksPath, evaluationsPath, submittoleaderboardPath } from "../../constants/RouteConstants";
import { useNavigate } from "react-router-dom";
import { formatMetricsSummary } from "../../utils/formatMetricsSummary";

function groupLeaderboardEntries(entries) {
  if (!Array.isArray(entries) || !entries.length) return [];
  const grouped = entries.reduce((acc, e) => {
    const key = e.dataset_name || "Unknown Dataset";
    if (!acc[key]) {
      acc[key] = { name: key, evaluation_metric: e.evaluation_metric, task_type: e.task_type, models: [] };
    } else if (e.task_type && !acc[key].task_type) {
      acc[key].task_type = e.task_type;
    }
    acc[key].models.push({
      model: e.model_name,
      score: typeof e.score === "number" ? e.score : Number(e.score) || 0,
      updated: e.submitted_at ? new Date(e.submitted_at).toLocaleDateString() : "",
      primary_metric: e.primary_metric,
      detailed_scores: e.detailed_scores,
    });
    return acc;
  }, {});
  return Object.values(grouped).map((d) => {
    const next = { ...d, models: [...d.models] };
    next.models.sort((a, b) => b.score - a.score);
    next.models = next.models.map((m, i) => ({ rank: i + 1, ...m }));
    return next;
  });
}

const Leaderboard = () => {
  const [openIndex, setOpenIndex] = useState(null);
  const [liveEntries, setLiveEntries] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [liveDatasetFilter, setLiveDatasetFilter] = useState("");
  const [datasetOptions, setDatasetOptions] = useState([]);
  const [curatedDatasets, setCuratedDatasets] = useState([]);
  const [viewMode, setViewMode] = useState('live'); // 'live' | 'curated'
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const API_BASE = process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001";

  const liveDatasets = useMemo(() => groupLeaderboardEntries(liveEntries), [liveEntries]);

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/public/datasets`);
        const data = await res.json();
        if (!ignore && data.success && Array.isArray(data.datasets)) {
          setDatasetOptions(
            data.datasets.map((d) => ({ name: d.name, label: `${d.name} (${d.task_type || "task"})` }))
          );
        }
      } catch {
        if (!ignore) setDatasetOptions([]);
      }
    })();
    return () => { ignore = true; };
  }, [API_BASE]);

  useEffect(() => {
    let ignore = false;
    const run = async () => {
      setLoading(true);
      setError("");
      setNextCursor(null);
      try {
        const url = new URL(`${API_BASE}/public/get_leaderboard`);
        url.searchParams.set("page_size", "40");
        if (liveDatasetFilter) url.searchParams.set("dataset", liveDatasetFilter);
        const res = await fetch(url.toString());
        const data = await res.json();
        if (!res.ok || data.success !== true) throw new Error(data.error || "Failed to load leaderboard");
        const entries = Array.isArray(data.leaderboard) ? data.leaderboard : [];
        if (!ignore) {
          setLiveEntries(entries);
          setNextCursor(data.next_cursor || null);
        }
      } catch (e) {
        if (!ignore) setError(e.message || "Error loading leaderboard");
      } finally {
        if (!ignore) setLoading(false);
      }
    };
    run();
    return () => { ignore = true; };
  }, [API_BASE, liveDatasetFilter]);

  const loadMoreLive = async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    setError("");
    try {
      const url = new URL(`${API_BASE}/public/get_leaderboard`);
      url.searchParams.set("page_size", "40");
      if (liveDatasetFilter) url.searchParams.set("dataset", liveDatasetFilter);
      url.searchParams.set("cursor", nextCursor);
      const res = await fetch(url.toString());
      const data = await res.json();
      if (!res.ok || data.success !== true) throw new Error(data.error || "Failed to load more");
      const chunk = Array.isArray(data.leaderboard) ? data.leaderboard : [];
      setLiveEntries((prev) => [...prev, ...chunk]);
      setNextCursor(data.next_cursor || null);
    } catch (e) {
      setError(e.message || "Error loading more");
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
        if (!res.ok || data.status !== 'success') return;
        const groups = (data.datasets || []).map(d => ({ name: d.name, url: d.url, evaluation_metric: '', models: (d.models||[]).map(m => ({ rank: m.rank, model: m.model, score: m.score, updated: m.updated })) }));
        if (!ignore) setCuratedDatasets(groups);
      } catch {}
    };
    run();
    return () => { ignore = true; };
  }, [API_BASE]);

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
  }
  ];
  const navigate = useNavigate();

  const displayDatasets = viewMode === 'curated'
    ? (curatedDatasets.length ? curatedDatasets : datasets)
    : (liveDatasets.length ? liveDatasets : datasets);

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
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold tracking-tight bg-white bg-clip-text text-transparent leading-tight">
            Model Leaderboard
          </h1>
          <p className="mt-4 text-gray-400 text-sm md:text-base max-w-lg mx-auto leading-relaxed">
            Compare models, submit results, and track model performance.
          </p>
        </div>
      </header>

      <div className="w-full max-w-7xl mt-6 flex flex-col sm:flex-row items-stretch sm:items-center justify-center gap-3 px-2">
        <label className="text-sm text-gray-400 flex flex-col sm:flex-row sm:items-center gap-2">
          <span className="shrink-0">Live dataset</span>
          <select
            value={liveDatasetFilter}
            onChange={(e) => setLiveDatasetFilter(e.target.value)}
            className="rounded-lg bg-[#0d1421] border border-gray-700 text-white text-sm px-3 py-2 min-w-[220px]"
          >
            <option value="">All datasets</option>
            {datasetOptions.map((o) => (
              <option key={o.name} value={o.name}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <p className="text-xs text-gray-500 sm:max-w-md">
          Uses <code className="text-gray-400">GET /public/get_leaderboard?dataset=</code>. Resets pagination when changed.
        </p>
      </div>

      {/* ── Loading / error ── */}
      {loading && (
        <div className="mt-16 text-gray-400 flex items-center gap-2.5 text-sm">
          <svg className="animate-spin w-4 h-4 text-[#28b2fb]" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          Loading leaderboard…
        </div>
      )}
      {error && (
        <div className="mt-10 text-red-400 text-sm bg-red-900/20 border border-red-800/40 rounded-lg px-4 py-2.5">
          {error}
        </div>
      )}

      {/* ── Dataset cards ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 md:gap-6 mt-10 w-full max-w-7xl">
        {displayDatasets.map((dataset, index) => (
          <div
            key={dataset.name || index}
            className="flex flex-col w-full bg-[#0d1421] rounded-2xl border border-gray-800/80 hover:border-[#defe47]/30 transition-all duration-200 shadow-xl shadow-black/20 overflow-hidden group"
          >
            {/* Card header */}
            <div className="flex items-start justify-between gap-3 px-5 pt-5 pb-4 border-b border-gray-800/60">
              <div className="flex-1 min-w-0">
                <h2 className="text-base font-bold text-white leading-snug truncate" title={dataset.name}>
                  {dataset.name}
                </h2>
                {(dataset.task_type || dataset.evaluation_metric) && (
                  <span className="mt-1.5 inline-flex items-center px-2 py-0.5 rounded-full bg-gray-800/80 text-[11px] text-gray-400 font-medium border border-gray-700/50">
                    {[dataset.task_type, dataset.evaluation_metric].filter(Boolean).join(" · ")}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                {dataset.url && (
                  <a
                    href={dataset.url}
                    className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-gray-700/60 text-gray-500 hover:text-[#defe47] hover:border-[#defe47]/30 transition-colors"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`Open dataset ${dataset.name}`}
                  >
                    Dataset ↗
                  </a>
                )}
                <button
                  className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-gray-700/60 text-gray-500 hover:text-[#28b2fb] hover:border-[#28b2fb]/30 transition-colors"
                  onClick={() => navigate(`/dataset/${encodeURIComponent(dataset.name)}`)}
                >
                  Details
                </button>
              </div>
            </div>

            {/* Rankings table */}
            <div className="flex-1">
              <div className="grid grid-cols-[3rem_1fr_6rem] text-[10px] font-semibold uppercase tracking-widest text-gray-600 px-5 py-2.5 border-b border-gray-800/40">
                <div>Rank</div>
                <div>Model</div>
                <div className="text-right">Score</div>
              </div>

              <div className="divide-y divide-gray-800/30">
                {dataset.models.map((model, modelIndex) => {
                  const isTop = model.rank === 1;
                  const score = typeof model.score === 'number'
                    ? model.score.toFixed(model.score < 1 ? 3 : 2)
                    : model.score;
                  const metricsLine = formatMetricsSummary(model.detailed_scores);
                  return (
                    <div
                      key={modelIndex}
                      className={[
                        "grid grid-cols-[3rem_1fr_6rem] items-center px-5 py-2.5 text-sm transition-colors",
                        isTop
                          ? "bg-[#defe47]/[0.04] hover:bg-[#defe47]/[0.08]"
                          : "hover:bg-white/[0.03]"
                      ].join(' ')}
                    >
                      <div className="font-semibold text-gray-400 flex items-center gap-1">
                        {rankBadge(model.rank)}
                        {model.rank > 3 && (
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-gray-800 text-[11px] text-gray-500 tabular-nums font-mono">
                            {model.rank}
                          </span>
                        )}
                      </div>
                      <div className="min-w-0">
                        <div
                          className={["font-medium truncate", isTop ? "text-white" : "text-gray-300"].join(' ')}
                          title={model.model}
                        >
                          {model.model}
                        </div>
                        {metricsLine && (
                          <div
                            className="text-[10px] text-gray-500 mt-0.5 truncate font-mono"
                            title={metricsLine}
                          >
                            {metricsLine}
                          </div>
                        )}
                      </div>
                      <div className="text-right">
                        <span className={[
                          "tabular-nums font-semibold",
                          isTop ? "text-[#defe47]" : model.rank === 2 ? "text-gray-100" : "text-gray-400"
                        ].join(' ')}>
                          {score}
                        </span>
                        {model.primary_metric && (
                          <div className="text-[10px] text-gray-600 leading-none mt-0.5">{model.primary_metric}</div>
                        )}
                        {model.ci && (
                          <div className="text-[10px] text-gray-600 leading-none mt-0.5">{model.ci}</div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ))}
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
