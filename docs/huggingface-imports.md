# Hugging Face Imports

Install the optional dependency first:

```bash
pip install datasets
```

Preview a conversion:

```bash
curl -X POST http://localhost:5001/public/import_hf_dataset \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name": "ag_news",
    "split": "test",
    "limit": 25,
    "task_type": "text_classification",
    "preview_only": true
  }'
```

Persist the imported dataset:

```bash
curl -X POST http://localhost:5001/public/import_hf_dataset \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name": "ag_news",
    "split": "test",
    "limit": 100,
    "task_type": "text_classification",
    "display_name": "AG News Test Sample"
  }'
```

When MySQL is configured, imported datasets are written to `benchmark_datasets`. Without MySQL, they live in the Flask in-memory store until the process restarts.

## Supported Conversion Defaults

- `text_classification`: stores `source_texts` and `labels`; default metric is `accuracy`.
- `document_qa` and `line_qa`: stores `source_texts` and `answers`; default metric is `exact`.
- `translation`: stores `source_texts` and `answers`; default metric is `bleu`.
