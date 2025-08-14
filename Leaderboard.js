import React, { useState } from "react";
import { submittoleaderboardPath } from "../../constants/RouteConstants";
import { useNavigate } from "react-router-dom";

const Leaderboard = () => {
  const [openIndex, setOpenIndex] = useState(null);

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
      name: "Financial Phrasebank - Classification Accuracy",
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
              "model": "O1",
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
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 pb-20 mx-3">
      <h1 className="text-4xl font-bold text-white mb-4 mt-8">LLM Leaderboards</h1>
      <button
        className="btn-black px-6 py-2 mb-8 rounded-md text-lg font-semibold transition-colors"
        // onClick={() => {navigate(submittoleaderboardPath);}}
        // href="mailto:nvidra@anote.ai"
        onClick={() => window.open("      https://docs.google.com/forms/d/e/1FAIpQLSdydF_8sfJQP0ub6VLs9uced32kfHxrvlQzyFRf0IhR1MlMRg/viewform?usp=dialog", "_blank")}

      >
        Submit Model to Leaderboard
      </button>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {datasets.map((dataset, index) => (
          <div
            key={index}
            className="w-full max-w-3xl p-4 bg-gray-950 rounded-lg shadow-lg"
          >
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-white">{dataset.name}</h2>
              <a
                href={dataset.url}
                className="text-blue-400 hover:text-blue-500 text-sm underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                View Dataset
              </a>
            </div>
            <div className="grid grid-cols-4 text-white font-bold text-center bg-gray-900 p-4 rounded-t-lg">
              <div>Rank</div>
              <div>Model</div>
              <div>Score</div>
              <div>Last Updated</div>
            </div>
            <div>
              {dataset.models
                // .sort((a, b) => b.score - a.score) Sort from highest to lowest score
                .map((model, modelIndex) => (
                  <div
                    key={modelIndex}
                    className={`grid grid-cols-4 text-center p-4 ${
                      modelIndex % 2 === 0
                        ? "bg-gray-700 text-white"
                        : "bg-gray-800 text-white"
                    }`}
                  >
                    <div>{model.rank}</div>
                    <div>{model.model}</div>
                    <div>{model.score}</div>
                    <div>{model.updated}</div>
                  </div>
                ))}
            </div>
          </div>
        ))}
      </div>

      {/* FAQs Section */}
      <div className="w-full md:w-3/4 mx-auto mt-20">
        <div className="bg-gray-900 rounded-xl p-10">
          <div className="text-yellow-500 text-3xl font-semibold mb-8">FAQs</div>
          {faqs.map((faq, index) => (
            <div
              className="bg-gray-800 px-5 py-4 my-4 rounded-xl cursor-pointer"
              onClick={() => handleClick(index)}
              key={index}
            >
              <div className="faq-header">
                <h2 className="text-xl font-medium bg-clip-text text-transparent bg-gradient-to-r from-turquoise-500 to-blue-400">
                  {faq.question}
                </h2>
              </div>
              {openIndex === index && (
                <div className="faq-answer mt-2 text-white">
                  <p>{faq.answer}</p>
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