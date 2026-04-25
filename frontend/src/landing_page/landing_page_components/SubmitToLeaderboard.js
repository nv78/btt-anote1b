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
  const [count, setCount] = useState(3);
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
      url.searchParams.set("count", String(count));
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
      const res = await fetch(`${API_BASE}/public/submit_model`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || data.success !== true) {
        throw new Error(data.error || "Submission failed");
      }
      setSubmitResult({ score: data.score });
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
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
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
              if (String(text).trim().length) {
                modelResults.push(String(text));
                ids.push(sid);
              }
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
    <div className="w-full bg-[#0a0f1a] text-white min-h-screen flex justify-center px-4">
      <div className="w-full max-w-4xl mx-auto mt-12 mb-20 rounded-2xl bg-[#0d1421] border border-gray-800/80 p-6 md:p-10 space-y-6">
        {/* Header + Close */}
        <div className="flex flex-row items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-[#defe47] mb-3">
              Model Submission
            </div>
            <div className="font-extrabold text-2xl md:text-3xl bg-clip-text text-transparent bg-gradient-to-r from-[#defe47] to-[#28b2fb]">
              Submit to the Leaderboard
            </div>
            <p className="text-sm text-gray-300/90 mt-1">Share your model’s results and we’ll evaluate and publish the ranking.</p>
          </div>
          {/* <div
            className="hover:cursor-pointer"
            onClick={() => {
              if (flowType !== FlowType.PREDICT) {
                backHome && backHome();
              } else {
                setPageNumber && setPageNumber(FlowPage.FLOW_OPTIONS);
              }
            }}
          >
            <FontAwesomeIcon className="text-xs" icon={faX} />
          </div> */}
        </div>

        {/* 1) Name to Give (from snippet) */}
        {/* <TextInput
          className="mt-2"
          value={nameToGive}
          onChange={(e) => setNameToGive(e.target.value)}
          type="text"
          placeholder={placeHolderName}
        /> */}

        {/* 2) Task Selector */}
        {/* {!showLockedTaskType && taskSelectorComponent}
        {showChooseTrainingFlow && (
          <div>
            <div>Choose Training Flow</div>
            <div className="w-1/2 flex flex-row items-center bg-gray-800 rounded-full py-0 mt-2">
              <div
                className={`py-2 w-1/2 text-center cursor-pointer ${
                  trainingFlow === 1
                    ? "bg-gray-900 border border-blue-300 rounded-full"
                    : ""
                }`}
                onClick={() => setTrainingFlow(1)}
              >
                Supervised
              </div>
              <div
                className={`py-2 w-1/2 text-center cursor-pointer relative select-none ${
                  trainingFlow === 2
                    ? "bg-gray-900 border border-blue-300 rounded-full"
                    : ""
                }`}
                onClick={() => {
                  // Currently mocked
                  alert("Unsupervised is Coming Soon!");
                }}
              >
                Unsupervised
              </div>
            </div>
          </div>
        )} */}

        {/* 3) Toggle "Per Line" or "Per Document" if classification or prompting */}
        {/* {showDocumentNameOrRawTextToggle && (
          <div className="flex items-center space-x-4">
            <label className="text-white font-semibold" htmlFor="document-name-toggle">
              Per Line or Per Document
            </label>
            <div
              className={`relative inline-flex items-center h-6 rounded-full w-11 cursor-pointer ${
                inputTextColContainsDocumentNames ? "bg-blue-500" : "bg-gray-700"
              }`}
              onClick={() =>
                setInputTextColContainsDocumentNames((prev) => !prev)
              }
            >
              <span
                className={`inline-block w-4 h-4 transform rounded-full bg-white transition-transform duration-200 ease-in-out ${
                  inputTextColContainsDocumentNames
                    ? "translate-x-6"
                    : "translate-x-1"
                }`}
              />
            </div>
            <span className="text-sm text-gray-400">
              {inputTextColContainsDocumentNames ? "Per Document" : "Per Line"}
            </span>
          </div>
        )} */}

        {/* 4) If chatbot or "Per Document," show Document Bank upload */}
        {/* {(showUploadDocumentBank || inputTextColContainsDocumentNames) && (
          <div
            onDragOver={handleDragOver}
            onDragEnter={handleDragEnterDocumentBanks}
            onDragLeave={handleDragLeaveDocumentBanks}
            onDrop={handleDropDocumentBanks}
            onClick={() => fileInputRefDocumentBanks.current?.click()}
            className={`w-full rounded bg-gray-800 h-[30vh] flex flex-col items-center justify-center py-4 cursor-pointer ${
              isDocBankDragActive ? "bg-blue-500" : ""
            }`}
          >
            <img src="/icons/cloud_arrow_icon.svg" alt="upload icon" />
            <div className="font-semibold">
              {inputTextColContainsDocumentNames
                ? "Upload Documents"
                : "Upload Testing Data"}
            </div>
            <div className="text-xs text-gray-400">
              Files Supported: pdf, docx, jpeg, csv, etc.
            </div>
            <div className="text-white text-sm mt-2">or</div>
            <button className="border border-[#40C6FF] text-[#40C6FF] px-4 py-1 rounded-lg mt-2">
              Browse Files
            </button>
            {renderFileNames()}
            <input
              type="file"
              className="hidden"
              multiple
              ref={fileInputRefDocumentBanks}
              onChange={handleDocumentBankFileUpload}
            />
          </div>
        )} */}

        {/* 5) Drag-and-Drop CSV */}
        {/* <div
          onDragOver={handleDragOver}
          onDragEnter={handleDragEnterCsv}
          onDragLeave={handleDragLeaveCsv}
          onDrop={handleDropCsv}
          onClick={() => fileInputRefCsv.current?.click()}
          className={`w-full rounded bg-gray-800 h-[30vh] flex flex-col items-center justify-center py-4 cursor-pointer ${
            isCsvDragActive ? "bg-blue-500" : ""
          }`}
        >
          <img src="/icons/cloud_arrow_icon.svg" alt="upload icon" />
          <div className="font-semibold">
            Drag and drop your Training CSV File here
          </div>
          <div className="text-xs text-gray-400">
            Files Supported: A single CSV file
          </div>
          <div className="text-white text-sm mt-2">or</div>
          <button className="border border-[#40C6FF] text-[#40C6FF] px-4 py-1 rounded-lg mt-2">
            Browse Files
          </button>
          <div className="text-white mt-2">
            {csvFileName ? `Selected File: ${csvFileName.name}` : "No file selected"}
          </div>
          <input
            type="file"
            accept=".csv"
            className="hidden"
            ref={fileInputRefCsv}
            onChange={handleCsvFileUpload}
          />
        </div>

        {flowType === FlowType.PREDICT && (
          <a
            href="#"
            className="underline text-sm text-yellow-500"
            onClick={handleOpenModal}
          >
            Select Benchmark Dataset
          </a>
        )}
        <a
          href="#"
          className="underline text-sm text-yellow-500 ml-6"
          onClick={handleDownloadExampleCsv}
        >
          Download Example CSV
        </a> */}
        {/* Submit to Leaderboard (API-connected UI) */}
        <div className="w-full max-w-3xl mx-auto bg-[#0a0f1a]/60 border border-gray-800/60 rounded-xl p-4 md:p-6 mb-8 relative">
          <button
            aria-label="Close"
            className="absolute right-3 top-3 px-2 py-1 rounded-md border border-gray-700 text-gray-300 hover:border-[#defe47]/60 hover:text-[#defe47]"
            onClick={() => navigate('/')}
          >
            ×
          </button>
          <div className="text-lg font-semibold text-[#defe47] mb-3">Submit to Model Leaderboard</div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-2">
            <div className="md:col-span-2">
              <label className="block text-sm text-gray-300 mb-1">Benchmark</label>
              <select
                className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white focus:outline-none focus:border-[#defe47]/70"
                value={datasetKey}
                onChange={(e) => {
                  const val = e.target.value;
                  setDatasetKey(val);
                  const found = datasetOptions.find(o => o.value === val);
                  if (found) setSelectedDatasetMeta({ task_type: found.task_type, evaluation_metric: found.evaluation_metric, size: found.size });
                }}
              >
                {datasetOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <div className="text-xs text-gray-400 mt-1">Task: {selectedDatasetMeta.task_type} | Metric: {selectedDatasetMeta.evaluation_metric} {selectedDatasetMeta.size ? `| Size: ${selectedDatasetMeta.size}` : ''}</div>
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1"># Sentences</label>
              <input
                type="number"
                min={1}
                max={5}
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white focus:outline-none focus:border-[#defe47]/70"
              />
            </div>
          </div>
          <div className="mb-4">
            <button type="button" onClick={()=>setProposeOpen(v=>!v)} className="text-xs text-yellow-400 underline">
              {proposeOpen ? 'Hide dataset proposal' : "Can't find your dataset? Propose one"}
            </button>
            {proposeOpen && (
              <form onSubmit={proposeDataset} className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
                <input placeholder="Dataset name" value={proposeForm.name} onChange={e=>setProposeForm(f=>({...f,name:e.target.value}))} className="px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white focus:outline-none focus:border-[#defe47]/70" required />
                <input placeholder="Task type (e.g., translation)" value={proposeForm.task_type} onChange={e=>setProposeForm(f=>({...f,task_type:e.target.value}))} className="px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white focus:outline-none focus:border-[#defe47]/70" required />
                <input placeholder="Evaluation metric (e.g., bleu)" value={proposeForm.evaluation_metric} onChange={e=>setProposeForm(f=>({...f,evaluation_metric:e.target.value}))} className="px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white focus:outline-none focus:border-[#defe47]/70" required />
                <input placeholder="URL (optional)" value={proposeForm.url} onChange={e=>setProposeForm(f=>({...f,url:e.target.value}))} className="px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white focus:outline-none focus:border-[#defe47]/70" />
                <input placeholder="Description (optional)" value={proposeForm.description} onChange={e=>setProposeForm(f=>({...f,description:e.target.value}))} className="px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white focus:outline-none focus:border-[#defe47]/70" />
                <div className="md:col-span-2">
                  <button type="submit" disabled={proposeSubmitting} className="px-3 py-2 rounded-md border border-[#defe47]/60 text-[#defe47] hover:bg-[#defe47]/10 disabled:opacity-50">
                    {proposeSubmitting ? 'Submitting...' : 'Propose Dataset'}
                  </button>
                </div>
              </form>
            )}
          </div>

          <div className="flex items-center gap-3 mb-4">
            <button
              type="button"
              onClick={fetchSentences}
              disabled={loadingFetch}
              className="px-4 py-2 rounded-md border border-[#defe47] bg-[#defe47] text-black font-semibold hover:bg-[#28b2fb] disabled:opacity-50"
            >
              {loadingFetch ? "Fetching…" : "Get Test Sentences"}
            </button>
            <button
              type="button"
              onClick={() => {
                // Build CSV template according to task type
                const tt = (selectedDatasetMeta.task_type || 'translation').toLowerCase();
                let headers = 'sentence_id,';
                if (tt === 'text_classification') headers += 'prediction\n0,\n1,\n2,\n';
                else if (tt === 'ner') headers += 'entities\n0,ORG;PERSON\n1,ORG\n2,\n';
                else headers += 'translation\n0,\n1,\n2,\n'; // default translation/qa
                const blob = new Blob([headers], { type: 'text/csv' });
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = `${datasetKey || 'dataset'}_${tt}_template.csv`;
                link.click();
                URL.revokeObjectURL(link.href);
              }}
              className="px-4 py-2 rounded-md border border-[#defe47]/60 text-[#defe47] hover:bg-[#defe47]/10"
            >
              Download CSV Template
            </button>
            <div className="text-sm text-gray-300">
              Use these sentences to generate your translations below.
            </div>
          </div>

          {errorMsg ? (
            <div className="text-sm text-red-400 mb-3">{errorMsg}</div>
          ) : null}

          {/* Toggle manual vs CSV */}
          <div className="flex items-center gap-3 mb-3">
            <label className="text-sm text-gray-300">Use CSV upload</label>
            <input type="checkbox" checked={useCsv} onChange={(e)=>setUseCsv(e.target.checked)} />
          </div>

          {/* CSV mode */}
          {useCsv && (
            <div className="space-y-3 mb-4">
              <input
                type="file"
                accept=".csv"
                className="w-full text-sm text-gray-300"
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  try {
                    const { modelResults, sentenceIds } = await parseSubmissionCsv(f);
                    setTranslations(modelResults);
                    setSentenceIds(sentenceIds);
                    setSourceSentences([]);
                    setErrorMsg("");
                  } catch (err) {
                    setErrorMsg('Failed to parse CSV');
                  }
                }}
              />
              <div className="text-xs text-gray-400">CSV headers supported: translation, sentence_id (optional)</div>
            </div>
          )}

          {/* Manual mode */}
          {!useCsv && sourceSentences.length > 0 && (
            <div className="space-y-3 mb-4">
              {sourceSentences.map((src, idx) => (
                <div key={idx} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
                  <div className="text-sm text-gray-300 mb-1">Source #{sentenceIds[idx]}</div>
                  <div className="text-white mb-2">{src}</div>
                  <textarea
                    className="w-full min-h-[60px] px-3 py-2 rounded-md bg-[#111827] border border-gray-700 text-white focus:outline-none focus:border-[#defe47]/70"
                    placeholder="Enter your translation here"
                    value={translations[idx] || ""}
                    onChange={(e) => {
                      const next = [...translations];
                      next[idx] = e.target.value;
                      setTranslations(next);
                    }}
                  />
                </div>
              ))}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 items-end">
            <div>
              <label className="block text-sm text-gray-300 mb-1">Model Name</label>
              <input
                type="text"
                placeholder="e.g. my-model-v1"
                value={modelNameInput}
                onChange={(e) => setModelNameInput(e.target.value)}
                className="w-full px-3 py-2 rounded-md bg-gray-900 border border-gray-700 text-white focus:outline-none focus:border-[#defe47]/70"
              />
            </div>
            <div className="flex gap-3 md:justify-end">
              <button
                type="button"
                onClick={submitToLeaderboard}
                disabled={loadingSubmit || !sentenceIds.length}
                className="px-4 py-2 rounded-md border border-[#defe47] bg-[#defe47] text-black font-semibold hover:bg-[#28b2fb] disabled:opacity-50"
              >
                {loadingSubmit ? "Submitting…" : "Submit to Leaderboard"}
              </button>
            </div>
          </div>

          {submitResult && (
            <div className="mt-4 text-sm text-[#defe47]">
              Success! Score: <span className="font-semibold">{submitResult.score?.toFixed(3)}</span>
            </div>
          )}
        </div>

{/* <div className="w-screen bg-gray-900 text-white min-h-screen flex items-center justify-center">
      <div className="bg-gray-800 p-8 rounded-lg shadow-lg w-full max-w-2xl"> */}
        {/* <h2 className="text-3xl font-bold mb-6 text-center">Submit to Model Leaderboard</h2> */}
        {/* Legacy Google Form submission UI removed in favor of API-connected workflow above */}
      {/* </div>
    </div> */}
        {/* <div>
          <form className="mt-4" onSubmit={handleSubmit}>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm mb-1">Submission Name</label>
                <input
                  type="text"
                  // We tie this to nameToGive to match "Predict Report Name"
                  value={nameToGive}
                  onChange={(e) => setNameToGive(e.target.value)}
                  className="w-full px-4 py-2 rounded-md bg-gray-700 text-white focus:ring-2 focus:ring-blue-400"
                  required
                />
              </div>

              <div>
                <label className="block text-sm mb-1">Benchmark Dataset</label>
                <Select
                  styles={SelectStyles}
                  options={connectorOptionsForSelect}
                  placeholder="Select a Benchmark..."
                  onChange={onBenchmarkSelectChange}
                />
              </div>

              <div>
                <label className="block text-sm mb-1">First Name</label>
                <input
                  type="text"
                  name="first_name"
                  value={formData.first_name}
                  onChange={handleUserFormChange}
                  className="w-full px-4 py-2 rounded-md bg-gray-700 text-white focus:ring-2 focus:ring-blue-400"
                  required
                />
              </div>

              <div>
                <label className="block text-sm mb-1">Last Name</label>
                <input
                  type="text"
                  name="last_name"
                  value={formData.last_name}
                  onChange={handleUserFormChange}
                  className="w-full px-4 py-2 rounded-md bg-gray-700 text-white focus:ring-2 focus:ring-blue-400"
                  required
                />
              </div>

              <div>
                <label className="block text-sm mb-1">Email Address</label>
                <input
                  type="email"
                  name="email_address"
                  value={formData.email_address}
                  onChange={handleUserFormChange}
                  className="w-full px-4 py-2 rounded-md bg-gray-700 text-white focus:ring-2 focus:ring-blue-400"
                  required
                />
              </div>

              <div>
                <label className="block text-sm mb-1">Company Name</label>
                <input
                  type="text"
                  name="company_name"
                  value={formData.company_name}
                  onChange={handleUserFormChange}
                  className="w-full px-4 py-2 rounded-md bg-gray-700 text-white focus:ring-2 focus:ring-blue-400"
                  required
                />
              </div>

              <div>
                <label className="block text-sm mb-1">Job Title</label>
                <input
                  type="text"
                  name="job_title"
                  value={formData.job_title}
                  onChange={handleUserFormChange}
                  className="w-full px-4 py-2 rounded-md bg-gray-700 text-white focus:ring-2 focus:ring-blue-400"
                  required
                />
              </div>

              <div>
                <label className="block text-sm mb-1">LinkedIn URL</label>
                <input
                  type="url"
                  name="linkedin_url"
                  value={formData.linkedin_url}
                  onChange={handleUserFormChange}
                  className="w-full px-4 py-2 rounded-md bg-gray-700 text-white focus:ring-2 focus:ring-blue-400"
                />
              </div>
            </div> */}

            {/* <div
          onDragOver={handleDragOver}
          onDragEnter={handleDragEnterCsv}
          onDragLeave={handleDragLeaveCsv}
          onDrop={handleDropCsv}
          onClick={() => fileInputRefCsv.current?.click()}
          className={`w-full rounded bg-gray-800 h-[30vh] flex flex-col items-center justify-center py-4 mt-4 cursor-pointer ${
            isCsvDragActive ? "bg-blue-500" : ""
          }`}
        >
          <img src="/icons/cloud_arrow_icon.svg" alt="upload icon" />
          <div className="font-semibold">
            Drag and drop your Training CSV File here
          </div>
          <div className="text-xs text-gray-400">
            Files Supported: A single CSV file
          </div>
          <div className="text-white text-sm mt-2">or</div>
          <button className="border border-[#40C6FF] text-[#40C6FF] px-4 py-1 rounded-lg mt-2">
            Browse Files
          </button>
          <div className="text-white mt-2">
            {csvFileName ? `Selected File: ${csvFileName.name}` : "No file selected"}
          </div>
          <input
            type="file"
            accept=".csv"
            className="hidden"
            ref={fileInputRefCsv}
            onChange={handleCsvFileUpload}
          />
        </div> */}

        {/* 6) Modal link + Example CSV link */}
        {/* <a
          href="#"
          className="underline text-sm text-yellow-500 ml-6"
          onClick={handleDownloadExampleCsv}
        >
          Download Example CSV
        </a> */}


            {/* Submit Button */}
            {/* <button
              type="submit"
              className="mt-6 bg-blue-500 hover:bg-[#28b8fb] text-white font-bold py-2 px-4 rounded-md focus:ring-4 focus:ring-blue-300"
              href="mailto:nvidra@anote.ai"
            >
              Submit to Leaderboard
            </button>
          </form> */}
        </div>
{/*
        {submissionStatus && (
          <p className="mt-4 text-center text-sm text-green-400">
            {submissionStatus}
          </p>
        )} */}

        {/* 8) Cancel / Next Buttons from snippet (optional) */}
        {/* <div className="w-full flex flex-row items-center justify-between mt-4">
          <button
            onClick={() => {
              // If we have a flow separation, you can do different logic
              if (flowType !== FlowType.PREDICT) {
                backHome && backHome();
              } else {
                setPageNumber && setPageNumber(FlowPage.FLOW_OPTIONS);
              }
            }}
            className="py-1.5 px-8 rounded-full border border-white"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              setPageNumber && setPageNumber(FlowPage.CSV_SELECTOR);
            }}
            disabled={!enableNextButton}
            className="py-1.5 px-8 rounded-full border border-white flex flex-row items-center space-x-4 disabled:cursor-not-allowed disabled:border-gray-500 disabled:text-gray-500"
          >
            <span>Next</span>
            <FontAwesomeIcon icon={faArrowRight} />
          </button>
        </div> */}

      {/* Benchmark Datasets Modal */}
      {isModalOpen && (
        <Modal
          size="3xl"
          show={isModalOpen}
          onClose={handleCloseModal}
          theme={{
            root: {
              show: {
                on: "flex bg-gray-900 bg-opacity-50 dark:bg-opacity-80",
              },
            },
            content: {
              base: "relative h-full w-full p-4 md:h-auto",
              inner: "relative rounded-lg shadow bg-gray-800 flex flex-col max-h-[90vh] text-white",
            },
          }}
        >
          <Modal.Header className="border-b border-gray-600 pb-1 text-center">
            <div className="flex justify-center items-center w-full text-center">
              <h2 className="font-bold text-xl text-center text-white">
                Benchmark Datasets
              </h2>
            </div>
          </Modal.Header>
          <Modal.Body className="w-full overflow-y-auto">
            <div className="text-center mb-4 text-sm">
              Supported benchmark test datasets include various task types like
              Classification, Chatbot, NER, and Prompting.
            </div>

            {/* Buttons to filter dataset cards by type */}
            <div className="flex justify-center space-x-4 mb-6">
              <button
                className={`px-4 py-2 rounded-lg transition-all duration-300 transform hover:scale-105 ${
                  selectedTaskType === "Classification"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-600 text-gray-200 hover:bg-gray-500"
                }`}
                onClick={() => setSelectedTaskType("Classification")}
              >
                Classification
              </button>
              <button
                className={`px-4 py-2 rounded-lg transition-all duration-300 transform hover:scale-105 ${
                  selectedTaskType === "Chatbot"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-600 text-gray-200 hover:bg-gray-500"
                }`}
                onClick={() => setSelectedTaskType("Chatbot")}
              >
                Chatbot
              </button>
              <button
                className={`px-4 py-2 rounded-lg transition-all duration-300 transform hover:scale-105 ${
                  selectedTaskType === "NER"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-600 text-gray-200 hover:bg-gray-500"
                }`}
                onClick={() => setSelectedTaskType("NER")}
              >
                NER
              </button>
              <button
                className={`px-4 py-2 rounded-lg transition-all duration-300 transform hover:scale-105 ${
                  selectedTaskType === "Prompting"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-600 text-gray-200 hover:bg-gray-500"
                }`}
                onClick={() => setSelectedTaskType("Prompting")}
              >
                Prompting
              </button>
              <button
                className={`px-4 py-2 rounded-lg transition-all duration-300 transform hover:scale-105 ${
                  selectedTaskType === ""
                    ? "bg-blue-600 text-white"
                    : "bg-gray-600 text-gray-200 hover:bg-gray-500"
                }`}
                onClick={() => setSelectedTaskType("")}
              >
                All
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
              {filteredOptions.map((option, index) => (
                <div
                  key={index}
                  className={`p-4 border rounded-lg shadow-md cursor-pointer transition-all duration-300 hover:shadow-xl ${
                    selectedDatasetId === option.value
                      ? "bg-blue-600 text-white"
                      : "bg-gray-700 text-gray-200 hover:bg-gray-600"
                  }`}
                  onClick={() => onConnectorCardClick(option.value)}
                >
                  <div className="flex flex-col items-center text-center">
                    <FaDatabase className="mb-2" size={20} />
                    <div className="text-sm font-semibold mb-1">
                      {option.label}
                    </div>
                    <div className="text-xs text-gray-300">
                      {option.taskType}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Modal.Body>
        </Modal>
      )}
    </div>
  );
};


export default SubmitToLeaderboard;
