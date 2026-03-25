import React, { useState } from "react";
import {
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
  Alert,
  CircularProgress,
  Paper,
  Divider,
} from "@mui/material";

const API_BASE =
  process.env.REACT_APP_API_BASE ||
  process.env.REACT_APP_API_ENDPOINT ||
  "http://localhost:5001";

const TASK_TYPES = [
  { value: "classification", label: "Classification" },
  { value: "translation", label: "Translation" },
  { value: "qa", label: "Q&A" },
  { value: "ner", label: "NER" },
];

const EVALUATION_METRICS = [
  { value: "BLEU", label: "BLEU" },
  { value: "BERTScore", label: "BERTScore" },
  { value: "F1", label: "F1" },
  { value: "Accuracy", label: "Accuracy" },
];

const SOURCE_TYPES = [
  { value: "HuggingFace", label: "HuggingFace" },
  { value: "HTTP API", label: "HTTP API" },
  { value: "CSV", label: "CSV" },
  { value: "Synthetic", label: "Synthetic" },
];

function HuggingFaceSubForm({ values, onChange }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
      <TextField
        label="Dataset ID"
        placeholder="e.g. facebook/flores"
        value={values.dataset_id || ""}
        onChange={(e) => onChange("dataset_id", e.target.value)}
        fullWidth
        size="small"
        required
      />
      <TextField
        label="Config Name"
        placeholder="e.g. spa_Latn"
        value={values.config_name || ""}
        onChange={(e) => onChange("config_name", e.target.value)}
        fullWidth
        size="small"
      />
      <TextField
        label="Split"
        placeholder="e.g. devtest"
        value={values.split || ""}
        onChange={(e) => onChange("split", e.target.value)}
        fullWidth
        size="small"
      />
      <TextField
        label="Max Samples"
        type="number"
        placeholder="e.g. 100"
        value={values.max_samples || ""}
        onChange={(e) => onChange("max_samples", e.target.value)}
        fullWidth
        size="small"
        inputProps={{ min: 1 }}
      />
    </Box>
  );
}

function HttpApiSubForm({ values, onChange }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
      <TextField
        label="URL"
        placeholder="https://example.com/api/data"
        value={values.url || ""}
        onChange={(e) => onChange("url", e.target.value)}
        fullWidth
        size="small"
        required
      />
      <TextField
        label="Auth Header"
        placeholder="Bearer <token>"
        value={values.auth_header || ""}
        onChange={(e) => onChange("auth_header", e.target.value)}
        fullWidth
        size="small"
      />
      <TextField
        label="Input Field"
        placeholder="Field name for input text"
        value={values.input_field || ""}
        onChange={(e) => onChange("input_field", e.target.value)}
        fullWidth
        size="small"
      />
      <TextField
        label="Reference Field"
        placeholder="Field name for reference/ground truth"
        value={values.reference_field || ""}
        onChange={(e) => onChange("reference_field", e.target.value)}
        fullWidth
        size="small"
      />
    </Box>
  );
}

export default function AddDataset() {
  const [name, setName] = useState("");
  const [taskType, setTaskType] = useState("classification");
  const [evaluationMetric, setEvaluationMetric] = useState("Accuracy");
  const [sourceType, setSourceType] = useState("HuggingFace");
  const [description, setDescription] = useState("");
  const [sourceConfig, setSourceConfig] = useState({});
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  function handleSourceConfigChange(key, value) {
    setSourceConfig((prev) => ({ ...prev, [key]: value }));
  }

  function handleSourceTypeChange(val) {
    setSourceType(val);
    setSourceConfig({});
    setSuccessMsg("");
    setErrorMsg("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSuccessMsg("");
    setErrorMsg("");

    if (!name.trim()) {
      setErrorMsg("Dataset name is required.");
      return;
    }

    setLoading(true);

    try {
      let endpoint;
      let payload;

      if (sourceType === "HuggingFace" || sourceType === "HTTP API") {
        endpoint = `${API_BASE}/api/datasets/ingest`;
        payload = {
          name: name.trim(),
          task_type: taskType,
          evaluation_metric: evaluationMetric,
          source_type: sourceType,
          description: description.trim(),
          source_config: sourceConfig,
        };
      } else {
        // CSV: use add_dataset endpoint
        endpoint = `${API_BASE}/api/leaderboard/add_dataset`;
        payload = {
          name: name.trim(),
          task_type: taskType,
          evaluation_metric: evaluationMetric,
          description: description.trim(),
        };
      }

      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        setSuccessMsg(
          data.message ||
            `Dataset "${name.trim()}" created successfully.`
        );
        setName("");
        setDescription("");
        setSourceConfig({});
      } else {
        setErrorMsg(
          data.error ||
            data.message ||
            `Request failed with status ${res.status}.`
        );
      }
    } catch (err) {
      setErrorMsg(err.message || "Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box
      sx={{
        maxWidth: 640,
        mx: "auto",
        mt: 4,
        mb: 6,
        px: { xs: 2, sm: 0 },
      }}
    >
      <Typography variant="h5" fontWeight={700} gutterBottom>
        Add Dataset
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>
        Register a new benchmark dataset. Choose a source type to configure
        where the data comes from.
      </Typography>

      <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
        <Box
          component="form"
          onSubmit={handleSubmit}
          sx={{ display: "flex", flexDirection: "column", gap: 3 }}
        >
          {/* Dataset Name */}
          <TextField
            label="Dataset Name"
            placeholder="e.g. my_translation_benchmark"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            fullWidth
            size="small"
          />

          {/* Task Type */}
          <FormControl fullWidth size="small" required>
            <InputLabel id="task-type-label">Task Type</InputLabel>
            <Select
              labelId="task-type-label"
              value={taskType}
              label="Task Type"
              onChange={(e) => setTaskType(e.target.value)}
            >
              {TASK_TYPES.map((t) => (
                <MenuItem key={t.value} value={t.value}>
                  {t.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Evaluation Metric */}
          <FormControl fullWidth size="small" required>
            <InputLabel id="eval-metric-label">Evaluation Metric</InputLabel>
            <Select
              labelId="eval-metric-label"
              value={evaluationMetric}
              label="Evaluation Metric"
              onChange={(e) => setEvaluationMetric(e.target.value)}
            >
              {EVALUATION_METRICS.map((m) => (
                <MenuItem key={m.value} value={m.value}>
                  {m.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Source Type */}
          <FormControl fullWidth size="small" required>
            <InputLabel id="source-type-label">Source Type</InputLabel>
            <Select
              labelId="source-type-label"
              value={sourceType}
              label="Source Type"
              onChange={(e) => handleSourceTypeChange(e.target.value)}
            >
              {SOURCE_TYPES.map((s) => (
                <MenuItem key={s.value} value={s.value}>
                  {s.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Dynamic sub-form */}
          {sourceType !== "CSV" && sourceType !== "Synthetic" && (
            <>
              <Divider />
              <Typography variant="subtitle2" color="text.secondary">
                {sourceType} Configuration
              </Typography>
              {sourceType === "HuggingFace" && (
                <HuggingFaceSubForm
                  values={sourceConfig}
                  onChange={handleSourceConfigChange}
                />
              )}
              {sourceType === "HTTP API" && (
                <HttpApiSubForm
                  values={sourceConfig}
                  onChange={handleSourceConfigChange}
                />
              )}
            </>
          )}

          {sourceType === "CSV" && (
            <Alert severity="info">
              To add a CSV-based dataset, please use the{" "}
              <strong>CSV Benchmarks</strong> tab to upload your file.
            </Alert>
          )}

          {sourceType === "Synthetic" && (
            <Alert severity="info">
              Synthetic dataset generation is <strong>coming soon</strong>.
            </Alert>
          )}

          {/* Description */}
          <TextField
            label="Description (optional)"
            placeholder="Brief description of this dataset..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            fullWidth
            size="small"
            multiline
            minRows={3}
          />

          {/* Feedback */}
          {successMsg && <Alert severity="success">{successMsg}</Alert>}
          {errorMsg && <Alert severity="error">{errorMsg}</Alert>}

          {/* Submit */}
          <Button
            type="submit"
            variant="contained"
            disabled={loading || sourceType === "Synthetic"}
            sx={{ alignSelf: "flex-start", px: 4 }}
          >
            {loading ? (
              <CircularProgress size={20} color="inherit" sx={{ mr: 1 }} />
            ) : null}
            {loading ? "Submitting…" : "Create Dataset"}
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}
