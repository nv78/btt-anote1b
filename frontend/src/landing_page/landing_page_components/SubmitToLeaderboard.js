import React, { useRef, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Papa from "papaparse";
import { Modal } from "flowbite-react";
import { FaDatabase } from "react-icons/fa";

// import { loadDatasets, useDatasets } from "../../redux/DatasetSlice";
// import { SelectStyles } from "../../styles/SelectStyles";

import {
  FlowPage,
  NLPTask,
  NLPTaskMap,
  FlowType,
  NLPTaskFileName,
  FlowTypeFileName,
} from "../../constants/DbEnums";
import { formatMetricsSummary } from "../../utils/formatMetricsSummary";
import { getLeaderboardJwt } from "../../utils/leaderboardAuth";

// Simple API base for dev
const API_BASE = process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001";

const SubmitToLeaderboard = ({
  flowType = FlowType.PREDICT,
  // Hooks to navigate out or set page states
  setPageNumber,
  backHome,

  // Hooks related to CSV data
  setLocalCsvData,
  setHasMoreRows,

  // Hooks related to dataset info
  nameToGive,
  setNameToGive,
  trainingFlow,
  setTrainingFlow,
  csvFileName,
  setCsvFileName,
  documentBankFileNames,
  setDocumentBankFileNames,
  assignedTaskType,
  setAssignedTaskType,
  selectedDatasetId,
  setSelectedDatasetId,
}) => {
  const navigate = useNavigate();
  // ---------- Leaderboard submission state ----------
  const [datasetKey, setDatasetKey] = useState("flores_spanish_translation");
  const [loadingFetch, setLoadingFetch] = useState(false);
  const [loadingSubmit, setLoadingSubmit] = useState(false);
  const [sentenceIds, setSentenceIds] = useState([]);
  const [sourceSentences, setSourceSentences] = useState([]);
  const [translations, setTranslations] = useState([]);
  const [modelNameInput, setModelNameInput] = useState("");
  const [submitResult, setSubmitResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [proposeOpen, setProposeOpen] = useState(false);
  const [proposeSubmitting, setProposeSubmitting] = useState(false);
  const [proposeForm, setProposeForm] = useState({ name: '', task_type: 'translation', evaluation_metric: 'bleu', url: '', description: '' });

  const [datasetOptions, setDatasetOptions] = useState([
    { value: "flores_spanish_translation", label: "Spanish (BLEU)", task_type: 'translation', evaluation_metric: 'bleu', size: undefined },
    { value: "flores_spanish_translation_bertscore", label: "Spanish (BERTScore)", task_type: 'translation', evaluation_metric: 'bertscore', size: undefined },
  ]);
  const [selectedDatasetMeta, setSelectedDatasetMeta] = useState({ task_type: 'translation', evaluation_metric: 'bleu', size: undefined });
  const [apiKey, setApiKey] = useState(() => localStorage.getItem("leaderboard_api_key") || "");
  const [submitterId, setSubmitterId] = useState(() => localStorage.getItem("leaderboard_submitter_id") || "");
  const [submissionFormat, setSubmissionFormat] = useState(null);
  const [submissionFormatOpen, setSubmissionFormatOpen] = useState(false);
  const [copiedFormat, setCopiedFormat] = useState(false);
  const [dsSearch, setDsSearch] = useState("");
  const [submitMode, setSubmitMode] = useState("manual"); // 'manual' | 'csv' | 'json'
  const [copiedQuestions, setCopiedQuestions] = useState(""); // '' | 'text' | 'json'

  useEffect(() => {
    localStorage.setItem("leaderboard_api_key", apiKey);
  }, [apiKey]);
  useEffect(() => {
    localStorage.setItem("leaderboard_submitter_id", submitterId);
  }, [submitterId]);

  const buildHeaders = (json = true) => {
    const h = {};
    if (json) h["Content-Type"] = "application/json";
    if (apiKey.trim()) h["X-API-Key"] = apiKey.trim();
    const jwt = getLeaderboardJwt();
    if (jwt) h["Authorization"] = `Bearer ${jwt}`;
    return h;
  };

  const loadSubmissionFormat = async (name) => {
    try {
      const enc = encodeURIComponent(name);
      const res = await fetch(`${API_BASE}/public/submission_format?dataset=${enc}`);
      const data = await res.json();
      if (res.ok && data.task_type_normalized) {
        setSubmissionFormat(data);
      } else {
        setSubmissionFormat(null);
      }
    } catch {
      setSubmissionFormat(null);
    }
  };

  useEffect(() => {
    if (datasetKey) loadSubmissionFormat(datasetKey);
  }, [datasetKey]);

  const fieldExplanations = [
    ["benchmarkDatasetName", "The exact dataset name selected above."],
    ["modelName", "A readable model or run identifier for the leaderboard row."],
    ["submittedBy", "Optional contact or owner label shown with your submission."],
    ["sentence_ids", "Dataset item ids being answered; length must match modelResults."],
    ["modelResults", "Your model outputs, in the same order as sentence_ids."],
    ["metadata", "Optional JSON object for version, prompt, or run notes."],
  ];

  const copySubmissionFormat = async () => {
    if (!submissionFormat?.submit_model_body) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(submissionFormat.submit_model_body, null, 2));
      setCopiedFormat(true);
      setTimeout(() => setCopiedFormat(false), 1500);
    } catch {
      setCopiedFormat(false);
    }
  };

  // Load available datasets from backend
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/public/datasets`);
        const data = await res.json();
        if (res.ok && data.success && Array.isArray(data.datasets)) {
          const opts = data.datasets.map(d => ({ value: d.name, label: `${d.name} (${d.task_type}/${d.evaluation_metric}${d.size?`, ${d.size} items`:''})`, task_type: d.task_type, evaluation_metric: d.evaluation_metric, size: d.size }));
          if (opts.length) {
            setDatasetOptions(opts);
            setDatasetKey(opts[0].value);
            setSelectedDatasetMeta({ task_type: opts[0].task_type, evaluation_metric: opts[0].evaluation_metric, size: opts[0].size });
          }
        }
      } catch {}
    })();
  }, []);

  const fetchSentences = async () => {
    setErrorMsg("");
    setSubmitResult(null);
    setLoadingFetch(true);
    try {
      const url = new URL(`${API_BASE}/public/get_source_sentences`);
      url.searchParams.set("dataset_name", datasetKey);
      url.searchParams.set("count", String(selectedDatasetMeta.size || 1000));
      url.searchParams.set("start_idx", "0");
      const res = await fetch(url.toString());
      const data = await res.json();
      if (!res.ok || data.success !== true) {
        throw new Error(data.error || "Failed to fetch sentences");
      }
      setSentenceIds(data.sentence_ids || []);
      setSourceSentences(data.source_sentences || []);
      setTranslations(new Array((data.source_sentences || []).length).fill(""));
    } catch (e) {
      setErrorMsg(e.message || "Error fetching sentences");
    } finally {
      setLoadingFetch(false);
    }
  };

  const submitToLeaderboard = async () => {
    setErrorMsg("");
    setLoadingSubmit(true);
    setSubmitResult(null);
    try {
      if (!modelNameInput.trim()) {
        throw new Error("Please enter a model name");
      }
      if (translations.length === 0 || translations.some((t) => !t.trim())) {
        throw new Error("Please provide outputs for all items");
      }
      const payload = {
        benchmarkDatasetName: datasetKey,
        modelName: modelNameInput.trim(),
        modelResults: translations,
        sentence_ids: sentenceIds,
      };
      if (submitterId.trim()) payload.submitterId = submitterId.trim();
      const res = await fetch(`${API_BASE}/public/submit_model`, {
        method: "POST",
        headers: buildHeaders(),
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.status === 202 && data.job_id) {
        let polled = data;
        for (let i = 0; i < 120; i++) {
          await new Promise((r) => setTimeout(r, 400));
          const pr = await fetch(`${API_BASE}/public/eval_jobs/${data.job_id}`);
          polled = await pr.json();
          if (polled.status === "completed" && polled.success) {
            setSubmitResult({
              score: polled.score,
              metric: polled.metric,
              detailed_scores: polled.detailed_scores,
              submission_id: polled.submission_id,
            });
            return;
          }
          if (polled.status === "failed") {
            throw new Error(polled.error || "Evaluation failed");
          }
        }
        throw new Error("Timed out waiting for async evaluation");
      }
      if (!res.ok || data.success !== true) {
        throw new Error(data.error || "Submission failed");
      }
      setSubmitResult({
        score: data.score,
        metric: data.metric,
        detailed_scores: data.detailed_scores,
        submission_id: data.submission_id,
      });
    } catch (e) {
      setErrorMsg(e.message || "Error submitting model");
    } finally {
      setLoadingSubmit(false);
    }
  };

  const proposeDataset = async (e) => {
    e.preventDefault();
    setErrorMsg("");
    setProposeSubmitting(true);
    try {
      const payload = {
        name: proposeForm.name.trim(),
        task_type: proposeForm.task_type,
        evaluation_metric: proposeForm.evaluation_metric,
        reference_data: { url: proposeForm.url || undefined, description: proposeForm.description || undefined }
      };
      const res = await fetch(`${API_BASE}/public/add_dataset`, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || data.success !== true) throw new Error(data.error || 'Failed to add dataset');
      // refresh list
      const lres = await fetch(`${API_BASE}/public/datasets`);
      const ldata = await lres.json();
      if (lres.ok && ldata.success && Array.isArray(ldata.datasets)) {
        const opts = ldata.datasets.map(d => ({ value: d.name, label: `${d.name} (${d.evaluation_metric})` }));
            setDatasetOptions(opts);
            setDatasetKey(payload.name);
            setSelectedDatasetMeta({ task_type: payload.task_type, evaluation_metric: payload.evaluation_metric, size: undefined });
            setProposeOpen(false);
        setProposeForm({ name: '', task_type: 'translation', evaluation_metric: 'bleu', url: '', description: '' });
      }
    } catch (e) {
      setErrorMsg(e.message || 'Error adding dataset');
    } finally {
      setProposeSubmitting(false);
    }
  };

  const filteredDatasetOptions = datasetOptions.filter((o) =>
    !dsSearch.trim() || o.value.toLowerCase().includes(dsSearch.trim().toLowerCase())
  );

  const TASK_EXAMPLES = {
    translation: {
      label: "Translation",
      input: "The annual report shows a significant increase in revenue across all business segments.",
      output: "El informe anual muestra un aumento significativo en los ingresos en todos los segmentos comerciales.",
      outputLabel: "Your translation",
    },
    text_classification: {
      label: "Text Classification",
      input: "The product quality exceeded my expectations and shipping was incredibly fast.",
      output: "positive",
      outputLabel: "Your label (e.g. positive / negative / neutral)",
    },
    named_entity_recognition: {
      label: "Named Entity Recognition",
      input: "Apple CEO Tim Cook announced a new partnership with Microsoft in Seattle.",
      output: '[{"text":"Apple","label":"ORG"},{"text":"Tim Cook","label":"PER"},{"text":"Microsoft","label":"ORG"},{"text":"Seattle","label":"LOC"}]',
      outputLabel: "Your entities as JSON array",
    },
    ner: {
      label: "NER",
      input: "Apple CEO Tim Cook announced a new partnership with Microsoft in Seattle.",
      output: '[{"text":"Apple","label":"ORG"},{"text":"Tim Cook","label":"PER"},{"text":"Microsoft","label":"ORG"},{"text":"Seattle","label":"LOC"}]',
      outputLabel: "Your entities as JSON array",
    },
    document_qa: {
      label: "Document Q&A",
      input: "Q: What was the company's total revenue in Q3? (Document: FinanceBench 2023 Annual Report)",
      output: "$4.2 billion",
      outputLabel: "Your answer (concise, from the document)",
    },
    multiple_choice_qa: {
      label: "Multiple Choice Q&A",
      input: "Which of the following best describes photosynthesis?\nA) Cellular respiration\nB) Conversion of sunlight to glucose\nC) DNA replication\nD) Protein synthesis",
      output: "B",
      outputLabel: "Your answer (A / B / C / D)",
    },
    retrieval: {
      label: "Retrieval",
      input: "Query: What are the tax implications of a Section 1031 exchange?",
      output: "doc_id_4821",
      outputLabel: "Your retrieved document id or passage",
    },
    summarization: {
      label: "Summarization",
      input: "Article: The Federal Reserve raised interest rates by 25 basis points on Wednesday, citing persistent inflation concerns. The decision was unanimous among the 12-member committee. Markets reacted positively, with the S&P 500 rising 1.2%...",
      output: "The Fed raised rates 25bps unanimously amid inflation concerns; markets rose 1.2%.",
      outputLabel: "Your summary (concise)",
    },
    code_generation: {
      label: "Code Generation",
      input: "Write a Python function that returns the nth Fibonacci number.",
      output: "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a",
      outputLabel: "Your code solution",
    },
    math_reasoning: {
      label: "Math & Reasoning",
      input: "A train travels 120 miles in 2 hours. What is its average speed in miles per hour?",
      output: "60",
      outputLabel: "Your numeric answer",
    },
    natural_language_inference: {
      label: "Natural Language Inference",
      input: "Premise: All dogs are mammals.\nHypothesis: Some mammals are dogs.",
      output: "entailment",
      outputLabel: "Your label (entailment / neutral / contradiction)",
    },
    semantic_similarity: {
      label: "Semantic Similarity",
      input: "Sentence 1: The car is parked outside.\nSentence 2: A vehicle is located outdoors.",
      output: "0.91",
      outputLabel: "Your similarity score (0.0 – 1.0)",
    },
    fact_verification: {
      label: "Fact Verification",
      input: "Claim: The Eiffel Tower was built in 1889 and is located in Paris, France.",
      output: "SUPPORTED",
      outputLabel: "Your verdict (SUPPORTED / REFUTED / NOT ENOUGH INFO)",
    },
    dialogue: {
      label: "Dialogue",
      input: "User: I'd like to book a table for two at 7pm tonight.\nSystem: Of course! May I have your name and preferred restaurant?",
      output: "My name is Smith. I'd like to book at La Maison, please.",
      outputLabel: "Your next system or user turn",
    },
  };

  const taskExample = TASK_EXAMPLES[
    (submissionFormat?.task_type_normalized || selectedDatasetMeta.task_type || "").toLowerCase()
  ] || null;

  const copyAllQuestions = async (format) => {
    if (!sourceSentences.length) return;
    let text;
    if (format === "json") {
      text = JSON.stringify(
        sourceSentences.map((s, i) => ({ id: sentenceIds[i], question: s })),
        null, 2
      );
    } else {
      text = sourceSentences.map((s, i) => `#${sentenceIds[i]}: ${s}`).join("\n\n");
    }
    try {
      await navigator.clipboard.writeText(text);
      setCopiedQuestions(format);
      setTimeout(() => setCopiedQuestions(""), 1500);
    } catch {}
  };

  const parseSubmissionJson = async (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const parsed = JSON.parse(e.target.result);
          let modelResults = [], ids = [];
          if (Array.isArray(parsed)) {
            parsed.forEach((item, idx) => {
              const output = item.output ?? item.prediction ?? item.translation ?? item.answer ?? item.result ?? "";
              const rawId = item.id ?? item.sentence_id ?? idx;
              const numId = Number(rawId);
              modelResults.push(String(output));
              ids.push(isNaN(numId) ? idx : numId);
            });
          } else if (parsed.modelResults && parsed.sentence_ids) {
            modelResults = parsed.modelResults;
            ids = parsed.sentence_ids;
          } else {
            reject(new Error("Unrecognized JSON format. Expected array of {id, output} or {modelResults, sentence_ids}."));
            return;
          }
          resolve({ modelResults, sentenceIds: ids });
        } catch (err) {
          reject(new Error("Invalid JSON file"));
        }
      };
      reader.onerror = () => reject(new Error("Failed to read file"));
      reader.readAsText(file);
    });
  };

  // CSV upload flow (optional): supports translation or classification
  const [useCsv, setUseCsv] = useState(false);
  const parseSubmissionCsv = async (file) => {
    return new Promise((resolve, reject) => {
      Papa.parse(file, {
        header: true,
        complete: (results) => {
          try {
            const rows = (results.data || []).filter(Boolean);
            const modelResults = [];
            const ids = [];
            rows.forEach((r, idx) => {
              const text = r.translation || r.Translations || r.output || r.prediction || r.Prediction || '';
              const sid = r.sentence_id != null ? Number(r.sentence_id) : (r.id != null ? Number(r.id) : (r.index != null ? Number(r.index) : idx));
              modelResults.push(String(text));
              ids.push(sid);
            });
            resolve({ modelResults, sentenceIds: ids });
          } catch (e) { reject(e); }
        },
        error: reject,
      })
    });
  };

  // ---------- Existing local states ----------
  const fileInputRefCsv = useRef(null);
  const fileInputRefDocumentBanks = useRef(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTaskType, setSelectedTaskType] = useState("");

  // Toggling whether input text col is doc name
  const [inputTextColContainsDocumentNames, setInputTextColContainsDocumentNames] =
    useState(false);

  // Drag state
  const [isCsvDragActive, setIsCsvDragActive] = useState(false);
  const [isDocBankDragActive, setIsDocBankDragActive] = useState(false);

  // Some conditions from your existing snippet
  useEffect(() => {
    // If we’re in PREDICT flow, load known datasets from the Redux store
    if (flowType === FlowType.PREDICT) {
      // dispatch(loadDatasets());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // const datasets = useDatasets();
  const datasets = [];

  // ---------- SHOW/HIDE Conditionals (ported from snippet) ----------
  let showDocumentNameOrRawTextToggle = false;
  if (
    flowType === FlowType.TRAIN ||
    flowType === FlowType.PREDICT
  ) {
    if (
      assignedTaskType === NLPTask.TEXT_CLASSIFICATION ||
      assignedTaskType === NLPTask.PROMPTING
    ) {
      showDocumentNameOrRawTextToggle = true;
    }
  }

  const showLockedTaskType = flowType === FlowType.PREDICT;
  const showChooseTrainingFlow = flowType === FlowType.TRAIN;
  const showChooseDataset = flowType === FlowType.PREDICT;
  const showUploadDocumentBank =
    assignedTaskType === NLPTask.CHATBOT && flowType !== FlowType.EVALUATE;

  // (From snippet: Next button enabling logic)
  let enableNextButton = false;
  if (flowType === FlowType.PREDICT) {
    if (
      selectedDatasetId &&
      assignedTaskType !== -1 &&
      csvFileName &&
      nameToGive
    ) {
      if (
        assignedTaskType === NLPTask.CHATBOT ||
        (inputTextColContainsDocumentNames &&
          showDocumentNameOrRawTextToggle)
      ) {
        if (documentBankFileNames.length > 0) {
          enableNextButton = true;
        }
      } else {
        enableNextButton = true;
      }
    }
  }

  // ---------- Title and placeholders (Train/Predict/Evaluate) ----------
  let placeHolderName = "";
  let titleName = "";
  if (flowType === FlowType.TRAIN) {
    placeHolderName = "Enter Dataset Name";
    titleName = "Train";
  } else if (flowType === FlowType.PREDICT) {
    placeHolderName = "Enter Predict Report Name";
    titleName = "Predict";
  } else if (flowType === FlowType.EVALUATE) {
    placeHolderName = "Enter Evaluation Report Name";
    titleName = "Evaluate";
  }

  // Legacy user form handlers removed (Google Form flow deprecated)

  // ---------- CSV & Document Bank Upload Handlers ----------
  const handleCsvFileUpload = async (event) => {
    if (event.target.files.length > 0) {
      const file = event.target.files[0];
      if (file) {
        setCsvFileName(file);
        Papa.parse(file, {
          header: true,
          complete: function (results) {
            const maxRows = 100;
            const limitedRows = results.data.slice(0, maxRows);
            const moreRowsFlag = results.data.length > maxRows;
            setHasMoreRows(moreRowsFlag);
            setLocalCsvData({
              headers: Object.keys(results.data[0]),
              rows: limitedRows,
            });
          },
        });
      }
    }
  };

  const handleDropCsv = async (event) => {
    event.preventDefault();
    const file = event.dataTransfer.files[0];
    if (file) {
      setCsvFileName(file);
      Papa.parse(file, {
        header: true,
        complete: function (results) {
          const maxRows = 100;
          const limitedRows = results.data.slice(0, maxRows);
          const moreRowsFlag = results.data.length > maxRows;
          setHasMoreRows(moreRowsFlag);
          setLocalCsvData({
            headers: Object.keys(results.data[0]),
            rows: limitedRows,
          });
        },
      });
    }
  };

  const handleDocumentBankFileUpload = (event) => {
    const files = Array.from(event.target.files);
    if (files.length > 0) {
      setDocumentBankFileNames(files);
    }
  };

  const handleDropDocumentBanks = (event) => {
    event.preventDefault();
    const files = Array.from(event.dataTransfer.files);
    setDocumentBankFileNames(files);
  };

  // ---------- Drag Over/Enter/Leave for CSV and Document bank ----------
  const handleDragOver = (event) => {
    event.preventDefault();
  };
  const handleDragEnterCsv = (event) => {
    event.preventDefault();
    setIsCsvDragActive(true);
  };
  const handleDragLeaveCsv = (event) => {
    event.preventDefault();
    setIsCsvDragActive(false);
  };
  const handleDragEnterDocumentBanks = (event) => {
    event.preventDefault();
    setIsDocBankDragActive(true);
  };
  const handleDragLeaveDocumentBanks = (event) => {
    event.preventDefault();
    setIsDocBankDragActive(false);
  };

  // ---------- Download Example CSV (if task type selected) ----------
  const handleDownloadExampleCsv = () => {
    if (assignedTaskType == null) {
      alert("Please select a task type before downloading the example CSV.");
      return;
    }
    const fileName = `${FlowTypeFileName[flowType]}_${NLPTaskFileName[assignedTaskType]}.csv`;
    const filePath = `/example_csvs/${fileName}`;
    const link = document.createElement("a");
    link.href = filePath;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // ---------- Benchmark Dataset Modal & Options ----------
  const connectorOptions = [
    { value: "Bizbench", label: "Bizbench", taskType: "Chatbot" },
    { value: "Financebench", label: "Financebench", taskType: "Chatbot" },
    { value: "Emotion", label: "Emotion", taskType: "Classification" },
    { value: "Finance", label: "Finance", taskType: "Classification" },
    { value: "MedQuAD", label: "MedQuAD", taskType: "Chatbot" },
    { value: "PubMed", label: "PubMed", taskType: "Classification" },
    { value: "QuoraQuAD", label: "QuoraQuAD", taskType: "Chatbot" },
    { value: "RagInstruct", label: "RagInstruct", taskType: "Chatbot" },
    { value: "ArcChallenge", label: "ArcChallenge", taskType: "Miscellaneous" },
    { value: "MMLU", label: "MMLU", taskType: "Miscellaneous" },
    { value: "Commonsense", label: "Commonsense", taskType: "Miscellaneous" },
    { value: "Geolocation", label: "Geolocation", taskType: "Miscellaneous" },
  ];

  const filteredOptions = connectorOptions.filter(
    (option) => selectedTaskType === "" || option.taskType === selectedTaskType
  );

  // For the <Select> dropdown, we’ll just use the same list (ignoring taskType filtering):
  const connectorOptionsForSelect = connectorOptions.map((o) => ({
    value: o.value,
    label: o.label,
  }));

  const handleOpenModal = () => setIsModalOpen(true);
  const handleCloseModal = () => setIsModalOpen(false);

  const handleDatasetSelect = async (datasetName) => {
    // Simulate a dataset CSV download
    const fileName = `${datasetName}.csv`;
    const filePath = `/benchmark_csvs/${datasetName}.csv`;
    const link = document.createElement("a");
    link.href = filePath;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    handleCloseModal();
  };

  const onConnectorCardClick = (value) => {
    handleDatasetSelect(value);
  };

  // For the <Select> onChange
  const onBenchmarkSelectChange = (selectedOption) => {
    // Store the dataset ID in local or global state
    setSelectedDatasetId(selectedOption.value);
    // Also set assignedTaskType based on match
    const found = connectorOptions.find((o) => o.value === selectedOption.value);
    if (found) {
      setSelectedTaskType(found.taskType);
    }
  };

  // ---------- Task Selector Component (if needed) ----------
  const taskSelectorComponent = (
    <div>
      <div>{showLockedTaskType ? "Task Type" : "Choose a Task Type"}</div>
      <div className="w-full flex flex-row items-center bg-gray-800 rounded-full py-0 mt-2">
        {Object.entries(NLPTask).map(([key, value]) => (
          <div
            key={value}
            className={`py-2 w-1/4 text-center cursor-pointer ${
              assignedTaskType === value
                ? "bg-gray-900 border border-blue-300 rounded-full"
                : ""
            }`}
            onClick={() => {
              // Only allow changing if not locked
              if (!showLockedTaskType) {
                setAssignedTaskType(value);
              }
            }}
          >
            {NLPTaskMap[value]}
          </div>
        ))}
      </div>
    </div>
  );

  // ---------- Render Document Bank File Names ----------
  const renderFileNames = () => {
    if (documentBankFileNames.length > 0) {
      return (
        <div className="text-white mt-2 max-h-32 overflow-y-auto">
          {documentBankFileNames.map((file, index) => (
            <div key={index}>{file.name}</div>
          ))}
        </div>
      );
    } else {
      return <div className="text-white mt-2">No file selected</div>;
    }
  };

  // ---------- Form Submission (final) ----------
  // const handleSubmit = async (e) => {
  //   e.preventDefault();

  //   // Basic validation
  //   if (!csvFileName) {
  //     alert("Please upload a CSV before submitting.");
  //     return;
  //   }
  //   if (!formData.first_name || !formData.last_name || !formData.email_address) {
  //     alert("Please fill out your user details before submitting.");
  //     return;
  //   }

  //   // Example final object
  //   const submissionData = {
  //     userFormData: { ...formData },
  //     csvName: csvFileName?.name || "",
  //     selectedDatasetId,
  //     assignedTaskType,
  //     // The "Submission Name" is the same as nameToGive
  //     nameToGive,
  //   };

  //   console.log("Submitting to Leaderboard:", submissionData);

  //   // Here you can do an API call, e.g.:
  //   // try {
  //   //   await axios.post("/api/submit-leaderboard", submissionData);
  //   //   alert("Submission successful!");
  //   //   ...
  //   // } catch (error) {
  //   //   console.error(error);
  //   //   ...
  //   // }

  //   setSubmissionStatus("Success! Your submission was received.");
  //   // Possibly reset form or navigate away
  //   // backHome();
  // };


  return (
    <div className="min-h-screen bg-[#111827] text-white px-4 py-10">
      <div className="max-w-4xl mx-auto space-y-8">

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <div className="text-xs uppercase tracking-widest text-[#defe47] mb-2">Model Submission</div>
            <h1 className="text-3xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-[#defe47] to-[#28b2fb]">
              Submit to the Leaderboard
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              Share your model's predictions — we'll score and publish the ranking.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate("/")}
            className="text-gray-500 hover:text-white text-2xl leading-none mt-1"
          >
            ×
          </button>
        </div>

        {/* ── Step 1: Select Benchmark ── */}
        <section className="bg-[#0d1421] border border-gray-800 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xs font-bold bg-[#defe47] text-black rounded-full w-5 h-5 flex items-center justify-center shrink-0">1</span>
            <h2 className="text-base font-semibold text-white">Select a Benchmark</h2>
          </div>
          <input
            type="text"
            placeholder="Search benchmarks…"
            value={dsSearch}
            onChange={(e) => setDsSearch(e.target.value)}
            className="w-full mb-4 px-4 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:outline-none focus:border-[#defe47]/50"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 max-h-80 overflow-y-auto pr-1">
            {filteredDatasetOptions.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  setDatasetKey(opt.value);
                  setSelectedDatasetMeta({ task_type: opt.task_type, evaluation_metric: opt.evaluation_metric, size: opt.size });
                  setSentenceIds([]);
                  setSourceSentences([]);
                  setTranslations([]);
                  setSubmitResult(null);
                }}
                className={`text-left rounded-xl border p-3 transition-colors ${
                  datasetKey === opt.value
                    ? "border-[#defe47] bg-[#defe47]/5"
                    : "border-gray-800 hover:border-gray-600 bg-gray-900/50"
                }`}
              >
                <div className="font-semibold text-white text-sm truncate" title={opt.value}>{opt.value}</div>
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {opt.task_type && (
                    <span className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded-full">{opt.task_type}</span>
                  )}
                  {opt.evaluation_metric && (
                    <span className="text-xs bg-[#defe47]/10 text-[#defe47] px-2 py-0.5 rounded-full">{opt.evaluation_metric}</span>
                  )}
                </div>
                {opt.size && <div className="text-xs text-gray-500 mt-1">{opt.size} items</div>}
              </button>
            ))}
            {filteredDatasetOptions.length === 0 && (
              <div className="col-span-3 text-sm text-gray-500 py-4">No benchmarks match your search.</div>
            )}
          </div>
          {/* Propose dataset */}
          <div className="mt-4 pt-4 border-t border-gray-800">
            <button
              type="button"
              onClick={() => setProposeOpen((v) => !v)}
              className="text-xs text-yellow-400 hover:underline"
            >
              {proposeOpen ? "Hide" : "Can't find your dataset? Propose one →"}
            </button>
            {proposeOpen && (
              <form onSubmit={proposeDataset} className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
                <input required placeholder="Dataset name" value={proposeForm.name} onChange={(e) => setProposeForm((f) => ({ ...f, name: e.target.value }))} className="px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:outline-none focus:border-[#defe47]/50" />
                <input required placeholder="Task type (e.g. translation)" value={proposeForm.task_type} onChange={(e) => setProposeForm((f) => ({ ...f, task_type: e.target.value }))} className="px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:outline-none focus:border-[#defe47]/50" />
                <input required placeholder="Metric (e.g. bleu, accuracy)" value={proposeForm.evaluation_metric} onChange={(e) => setProposeForm((f) => ({ ...f, evaluation_metric: e.target.value }))} className="px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:outline-none focus:border-[#defe47]/50" />
                <input placeholder="URL (optional)" value={proposeForm.url} onChange={(e) => setProposeForm((f) => ({ ...f, url: e.target.value }))} className="px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:outline-none focus:border-[#defe47]/50" />
                <input placeholder="Description (optional)" value={proposeForm.description} onChange={(e) => setProposeForm((f) => ({ ...f, description: e.target.value }))} className="sm:col-span-2 px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:outline-none focus:border-[#defe47]/50" />
                <div className="sm:col-span-2">
                  <button type="submit" disabled={proposeSubmitting} className="px-4 py-2 rounded-lg border border-[#defe47]/60 text-[#defe47] text-sm hover:bg-[#defe47]/10 disabled:opacity-50">
                    {proposeSubmitting ? "Submitting…" : "Propose Dataset"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </section>

        {/* ── Step 2: Get Test Questions ── */}
        <section className="bg-[#0d1421] border border-gray-800 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xs font-bold bg-[#defe47] text-black rounded-full w-5 h-5 flex items-center justify-center shrink-0">2</span>
            <h2 className="text-base font-semibold text-white">Get Test Questions</h2>
          </div>
          {/* Example answer format */}
          {taskExample && (
            <div className="mb-5 rounded-xl border border-gray-700 bg-gray-900/60 overflow-hidden">
              <div className="px-4 py-2 border-b border-gray-700 bg-gray-950/60 flex items-center gap-2">
                <span className="text-xs font-semibold text-[#defe47]">Example</span>
                <span className="text-xs text-gray-500">— not from the eval set, shows expected answer format</span>
              </div>
              <div className="px-4 py-3 space-y-3">
                <div>
                  <div className="text-xs text-gray-500 mb-1">Input question</div>
                  <pre className="text-sm text-gray-200 whitespace-pre-wrap font-sans leading-relaxed">{taskExample.input}</pre>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">{taskExample.outputLabel}</div>
                  <pre className="text-sm text-[#defe47] whitespace-pre-wrap font-mono bg-black/20 rounded-lg px-3 py-2">{taskExample.output}</pre>
                </div>
              </div>
            </div>
          )}

          <div className="flex items-center gap-3 mb-4">
            <button
              type="button"
              onClick={fetchSentences}
              disabled={loadingFetch}
              className="px-4 py-2 rounded-lg bg-[#defe47] text-black text-sm font-semibold hover:bg-[#e8ff70] disabled:opacity-50"
            >
              {loadingFetch ? "Fetching…" : "Fetch All Questions"}
            </button>
            {selectedDatasetMeta.size && (
              <span className="text-xs text-gray-500">{selectedDatasetMeta.size} items in this benchmark</span>
            )}
          </div>

          {sourceSentences.length > 0 && (
            <>
              <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden mb-3">
                <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-gray-950/60">
                  <span className="text-xs text-gray-400">{sourceSentences.length} questions — {datasetKey}</span>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => copyAllQuestions("text")}
                      className="text-xs px-3 py-1 rounded-md border border-gray-700 text-gray-300 hover:border-[#defe47]/50 hover:text-[#defe47] transition-colors"
                    >
                      {copiedQuestions === "text" ? "Copied!" : "Copy as text"}
                    </button>
                    <button
                      type="button"
                      onClick={() => copyAllQuestions("json")}
                      className="text-xs px-3 py-1 rounded-md border border-gray-700 text-gray-300 hover:border-[#defe47]/50 hover:text-[#defe47] transition-colors"
                    >
                      {copiedQuestions === "json" ? "Copied!" : "Copy as JSON"}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const blob = new Blob([JSON.stringify(
                          sourceSentences.map((s, i) => ({ id: sentenceIds[i], question: s, output: "" })),
                          null, 2
                        )], { type: "application/json" });
                        const a = document.createElement("a");
                        a.href = URL.createObjectURL(blob);
                        a.download = `${datasetKey}_questions.json`;
                        a.click();
                        URL.revokeObjectURL(a.href);
                      }}
                      className="text-xs px-3 py-1 rounded-md border border-gray-700 text-gray-300 hover:border-[#defe47]/50 hover:text-[#defe47] transition-colors"
                    >
                      Download .json
                    </button>
                  </div>
                </div>
                <div className="divide-y divide-gray-800/60 max-h-64 overflow-y-auto">
                  {sourceSentences.map((src, idx) => (
                    <div key={idx} className="flex gap-3 px-4 py-3">
                      <span className="text-xs text-gray-500 font-mono w-8 shrink-0 pt-0.5">#{sentenceIds[idx]}</span>
                      <p className="text-sm text-gray-200 leading-relaxed">{src}</p>
                    </div>
                  ))}
                </div>
              </div>
              <p className="text-xs text-gray-500">
                Fill in your model's answers below, then submit. The <code className="text-gray-400">output</code> field maps to your prediction for each question id.
              </p>
            </>
          )}

          {/* Submission format accordion */}
          {submissionFormat && (
            <div className="mt-4 rounded-xl border border-gray-800 overflow-hidden">
              <button
                type="button"
                onClick={() => setSubmissionFormatOpen((v) => !v)}
                className="w-full flex items-center justify-between px-4 py-3 text-sm text-gray-300 hover:bg-white/[0.02]"
              >
                <span>
                  Expected JSON format
                  <span className="ml-2 text-xs text-gray-500">{submissionFormat.task_type_normalized} / {submissionFormat.evaluation_metric_normalized}</span>
                </span>
                <span className="text-[#defe47] text-xs">{submissionFormatOpen ? "Hide" : "Show"}</span>
              </button>
              {submissionFormatOpen && (
                <div className="border-t border-gray-800 p-4 space-y-3">
                  <div className="flex justify-end">
                    <button type="button" onClick={copySubmissionFormat} className="text-xs px-3 py-1 rounded-md border border-[#defe47]/40 text-[#defe47] hover:bg-[#defe47]/10">
                      {copiedFormat ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <pre className="text-xs text-gray-300 bg-[#111827] border border-gray-800 rounded-lg p-3 overflow-auto max-h-60">
                    {JSON.stringify(submissionFormat.submit_model_body, null, 2)}
                  </pre>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {fieldExplanations.map(([field, explanation]) => (
                      <div key={field} className="text-xs text-gray-400">
                        <span className="font-mono text-gray-200">{field}</span>: {explanation}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {/* ── Step 3: Submit Answers ── */}
        <section className="bg-[#0d1421] border border-gray-800 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xs font-bold bg-[#defe47] text-black rounded-full w-5 h-5 flex items-center justify-center shrink-0">3</span>
            <h2 className="text-base font-semibold text-white">Submit Your Answers</h2>
          </div>

          {/* Model name */}
          <div className="mb-4">
            <label className="block text-sm text-gray-400 mb-1.5">Model name</label>
            <input
              type="text"
              placeholder="e.g. my-model-v2"
              value={modelNameInput}
              onChange={(e) => setModelNameInput(e.target.value)}
              className="w-full sm:w-72 px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:outline-none focus:border-[#defe47]/50"
            />
          </div>

          {/* Mode tabs */}
          <div className="flex gap-1 mb-4 bg-gray-900 rounded-lg p-1 w-fit">
            {[["manual", "Manual"], ["csv", "Upload CSV"], ["json", "Upload JSON"]].map(([mode, label]) => (
              <button
                key={mode}
                type="button"
                onClick={() => setSubmitMode(mode)}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  submitMode === mode ? "bg-[#defe47] text-black" : "text-gray-400 hover:text-white"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Manual mode */}
          {submitMode === "manual" && (
            <div className="space-y-3">
              {sourceSentences.length === 0 && (
                <p className="text-sm text-gray-500">Fetch questions in Step 2 first, then enter your answers here.</p>
              )}
              {sourceSentences.map((src, idx) => (
                <div key={idx} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                  <div className="flex gap-3 mb-2">
                    <span className="text-xs text-gray-500 font-mono w-8 shrink-0 pt-0.5">#{sentenceIds[idx]}</span>
                    <p className="text-sm text-gray-300 leading-relaxed">{src}</p>
                  </div>
                  <textarea
                    rows={2}
                    placeholder="Your model's output…"
                    value={translations[idx] || ""}
                    onChange={(e) => {
                      const next = [...translations];
                      next[idx] = e.target.value;
                      setTranslations(next);
                    }}
                    className="w-full px-3 py-2 rounded-lg bg-[#111827] border border-gray-700 text-white text-sm focus:outline-none focus:border-[#defe47]/50 resize-none"
                  />
                </div>
              ))}
            </div>
          )}

          {/* CSV upload mode */}
          {submitMode === "csv" && (
            <div className="space-y-3">
              <div
                className="border-2 border-dashed border-gray-700 rounded-xl p-8 flex flex-col items-center justify-center gap-3 cursor-pointer hover:border-[#defe47]/40 transition-colors"
                onClick={() => document.getElementById("csv-upload-input").click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={async (e) => {
                  e.preventDefault();
                  const f = e.dataTransfer.files?.[0];
                  if (!f) return;
                  try {
                    const { modelResults, sentenceIds: ids } = await parseSubmissionCsv(f);
                    setTranslations(modelResults);
                    setSentenceIds(ids);
                    setSourceSentences([]);
                    setErrorMsg("");
                  } catch { setErrorMsg("Failed to parse CSV"); }
                }}
              >
                <svg className="w-10 h-10 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <div className="text-center">
                  <p className="text-sm text-gray-300 font-medium">Drop your CSV here or click to browse</p>
                  <p className="text-xs text-gray-500 mt-1">Required columns: <code className="text-gray-400">sentence_id</code>, <code className="text-gray-400">output</code> (or <code className="text-gray-400">translation</code> / <code className="text-gray-400">prediction</code>)</p>
                </div>
                <input
                  id="csv-upload-input"
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={async (e) => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    try {
                      const { modelResults, sentenceIds: ids } = await parseSubmissionCsv(f);
                      setTranslations(modelResults);
                      setSentenceIds(ids);
                      setSourceSentences([]);
                      setErrorMsg("");
                    } catch { setErrorMsg("Failed to parse CSV"); }
                  }}
                />
              </div>
              <button
                type="button"
                onClick={() => {
                  const tt = (selectedDatasetMeta.task_type || "translation").toLowerCase();
                  let csv = "sentence_id,output\n";
                  (sentenceIds.length ? sentenceIds : [0, 1, 2]).forEach((id) => { csv += `${id},\n`; });
                  const blob = new Blob([csv], { type: "text/csv" });
                  const a = document.createElement("a");
                  a.href = URL.createObjectURL(blob);
                  a.download = `${datasetKey || "dataset"}_${tt}_template.csv`;
                  a.click();
                  URL.revokeObjectURL(a.href);
                }}
                className="text-xs text-[#defe47] hover:underline"
              >
                Download CSV template
              </button>
              {translations.length > 0 && (
                <p className="text-xs text-green-400">{translations.length} rows loaded from CSV.</p>
              )}
            </div>
          )}

          {/* JSON upload mode */}
          {submitMode === "json" && (
            <div className="space-y-3">
              <div
                className="border-2 border-dashed border-gray-700 rounded-xl p-8 flex flex-col items-center justify-center gap-3 cursor-pointer hover:border-[#defe47]/40 transition-colors"
                onClick={() => document.getElementById("json-upload-input").click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={async (e) => {
                  e.preventDefault();
                  const f = e.dataTransfer.files?.[0];
                  if (!f) return;
                  try {
                    const { modelResults, sentenceIds: ids } = await parseSubmissionJson(f);
                    setTranslations(modelResults);
                    setSentenceIds(ids);
                    setSourceSentences([]);
                    setErrorMsg("");
                  } catch (err) { setErrorMsg(err.message || "Failed to parse JSON"); }
                }}
              >
                <svg className="w-10 h-10 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <div className="text-center">
                  <p className="text-sm text-gray-300 font-medium">Drop your JSON here or click to browse</p>
                  <p className="text-xs text-gray-500 mt-1">
                    Format: <code className="text-gray-400">{"[{id, output}, …]"}</code> or <code className="text-gray-400">{"[{id, prediction}, …]"}</code>
                  </p>
                </div>
                <input
                  id="json-upload-input"
                  type="file"
                  accept=".json"
                  className="hidden"
                  onChange={async (e) => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    try {
                      const { modelResults, sentenceIds: ids } = await parseSubmissionJson(f);
                      setTranslations(modelResults);
                      setSentenceIds(ids);
                      setSourceSentences([]);
                      setErrorMsg("");
                    } catch (err) { setErrorMsg(err.message || "Failed to parse JSON"); }
                  }}
                />
              </div>
              {translations.length > 0 && (
                <p className="text-xs text-green-400">{translations.length} answers loaded from JSON.</p>
              )}
            </div>
          )}

          {errorMsg && (
            <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {errorMsg}
            </div>
          )}

          {/* Submit button */}
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <button
              type="button"
              onClick={submitToLeaderboard}
              disabled={loadingSubmit || !sentenceIds.length || !modelNameInput.trim()}
              className="px-6 py-2.5 rounded-lg bg-[#defe47] text-black text-sm font-semibold hover:bg-[#e8ff70] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {loadingSubmit ? "Submitting…" : "Submit to Leaderboard"}
            </button>
            {!sentenceIds.length && (
              <p className="text-xs text-gray-500">Fetch questions or upload a file first.</p>
            )}
          </div>

          {submitResult && (
            <div className="mt-5 rounded-xl border border-[#defe47]/20 bg-[#defe47]/5 px-5 py-4 space-y-1">
              <div className="text-[#defe47] font-semibold">
                Submitted! Score:{" "}
                <span>{typeof submitResult.score === "number" ? submitResult.score.toFixed(4) : submitResult.score}</span>
                {submitResult.metric && <span className="text-gray-400 font-normal ml-1">({submitResult.metric})</span>}
              </div>
              {submitResult.submission_id != null && (
                <div className="text-xs text-gray-500">Submission id: {submitResult.submission_id}</div>
              )}
              {submitResult.detailed_scores && (
                <div className="text-xs font-mono text-gray-400 break-all pt-1">
                  {formatMetricsSummary(submitResult.detailed_scores)}
                </div>
              )}
            </div>
          )}
        </section>

        {/* ── Advanced: API key / submitter id ── */}
        <details className="group">
          <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-300 list-none flex items-center gap-1">
            <span className="group-open:rotate-90 transition-transform inline-block">▶</span>
            Advanced options (API key, submitter id)
          </summary>
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3 bg-[#0d1421] border border-gray-800 rounded-xl p-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1">API key (if server requires)</label>
              <input
                type="password"
                autoComplete="off"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="X-API-Key value"
                className="w-full px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:outline-none focus:border-[#defe47]/50"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Submitter id (optional)</label>
              <input
                type="text"
                value={submitterId}
                onChange={(e) => setSubmitterId(e.target.value)}
                placeholder="email or opaque id"
                className="w-full px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:outline-none focus:border-[#defe47]/50"
              />
            </div>
          </div>
        </details>

      </div>
    </div>
  );
};


export default SubmitToLeaderboard;
