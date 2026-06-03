import Papa from "papaparse";

export const SAMPLE_OUTPUTS = {
  text_classification: ["positive", "negative", "positive"],
  named_entity_recognition: ["Barack Obama; United States", "Apple Inc.; Cupertino", ""],
  document_qa: ["1955", "Evelyn Lincoln", "the Oval Office"],
  line_qa: ["Paris", "H2O", "photosynthesis"],
  multiple_choice_qa: ["A", "C", "B"],
  natural_language_inference: ["entailment", "contradiction", "neutral"],
  math_reasoning: ["42", "17.5", "100"],
  summarization: [
    "Scientists discover water on Mars.",
    "Stock markets fall sharply.",
    "New study links diet to longevity.",
  ],
  translation: ["Bonjour le monde", "Gracias por su ayuda", "Wie geht es Ihnen"],
  text_generation: ["Once upon a time in a land far away...", "The quick brown fox jumps over...", "In conclusion, the results show..."],
  code_generation: ["def add(a, b):\n    return a + b", "SELECT * FROM users WHERE id = 1;", "console.log('hello world');"],
  fact_verification: ["supported", "refuted", "not enough info"],
  retrieval: ["The mitochondria is the powerhouse of the cell.", "Water boils at 100C at sea level.", ""],
  semantic_similarity: ["0.92", "0.14", "0.78"],
};

export const buildSampleJson = (taskType, sentenceIds, allowedOutputs = []) => {
  const tt = (taskType || "text_classification").toLowerCase().replace(/-/g, "_");
  const outputs = SAMPLE_OUTPUTS[tt] || SAMPLE_OUTPUTS.text_classification;
  const ids = sentenceIds && sentenceIds.length ? sentenceIds : [0, 1, 2];
  const sample = ids.slice(0, 3).map((id, i) => ({
    id,
    output: allowedOutputs[i % allowedOutputs.length] || outputs[i] || outputs[0],
  }));
  return JSON.stringify(sample, null, 2);
};

export const buildQuestionsExport = ({
  sourceSentences = [],
  sentenceIds = [],
  questionOptions = [],
  allowedOutputs = [],
  format = "text",
}) => {
  if (format === "json") {
    return JSON.stringify(
      sourceSentences.map((question, i) => ({
        id: sentenceIds[i],
        question,
        ...(questionOptions[i]?.length ? { options: questionOptions[i] } : {}),
        ...(allowedOutputs.length ? { allowed_outputs: allowedOutputs } : {}),
      })),
      null,
      2
    );
  }

  let text = sourceSentences.map((question, i) => {
    const options = questionOptions[i]?.length
      ? `\nOptions:\n${questionOptions[i].map((o) => `${o.label}) ${o.text}`).join("\n")}`
      : "";
    return `#${sentenceIds[i]}: ${question}${options}`;
  }).join("\n\n");
  if (allowedOutputs.length) {
    text = `Allowed labels: ${allowedOutputs.join(", ")}\n\n${text}`;
  }
  return text;
};

export const normalizeParsedSubmissionJson = (parsed) => {
  let modelResults = [];
  let ids = [];

  if (Array.isArray(parsed)) {
    parsed.forEach((item, idx) => {
      const output = item.output ?? item.prediction ?? item.translation ?? item.answer ?? item.result ?? "";
      const rawId = item.id ?? item.sentence_id ?? idx;
      const numId = Number(rawId);
      modelResults.push(String(output));
      ids.push(Number.isNaN(numId) ? idx : numId);
    });
  } else if (Array.isArray(parsed?.modelResults) && Array.isArray(parsed?.sentence_ids)) {
    modelResults = parsed.modelResults;
    ids = parsed.sentence_ids;
  } else {
    throw new Error("Unrecognized JSON format. Expected array of {id, output} or {modelResults, sentence_ids}.");
  }

  return { modelResults, sentenceIds: ids };
};

export const parseSubmissionCsvText = (csvText) => {
  const results = Papa.parse(csvText, { header: true, skipEmptyLines: false });
  const nonFatalCodes = new Set(["UndetectableDelimiter", "TooFewFields"]);
  const fatalError = (results.errors || []).find((error) => !nonFatalCodes.has(error.code));
  if (fatalError) {
    throw new Error(fatalError.message || "Invalid CSV file");
  }
  const rows = (results.data || []).filter((row) => (
    row && Object.values(row).some((value) => String(value ?? "").trim())
  ));
  const modelResults = [];
  const ids = [];
  rows.forEach((row, idx) => {
    const text = row.translation || row.Translations || row.output || row.Output || row.prediction || row.Prediction || row.answer || row.Answer || "";
    const rawId = row.sentence_id != null ? row.sentence_id : (row.id != null ? row.id : (row.index != null ? row.index : idx));
    const numId = Number(rawId);
    modelResults.push(String(text));
    ids.push(Number.isNaN(numId) ? idx : numId);
  });
  return { modelResults, sentenceIds: ids };
};
