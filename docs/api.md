# API Usage

## Dataset Discovery

```bash
curl http://localhost:5001/public/datasets
curl "http://localhost:5001/public/dataset_details?name=flores_spanish_translation"
```

## Authentication

Read endpoints are public. Write and evaluation endpoints can be protected by setting:

```bash
export LEADERBOARD_API_KEYS=secret-key-1,secret-key-2
```

When keys are configured, send one with each write request:

```bash
curl -H "X-API-Key: secret-key-1" ...
```

## Metric Metadata

```bash
curl http://localhost:5001/api/metrics
curl http://localhost:5001/api/metrics/task/text_classification
```

## Add a Dataset

```bash
curl -X POST http://localhost:5001/public/add_dataset \
  -H "Content-Type: application/json" \
  -d '{
    "name": "demo_classification",
    "task_type": "text_classification",
    "evaluation_metric": "accuracy",
    "reference_data": {
      "source_texts": ["good", "bad"],
      "labels": ["positive", "negative"]
    }
  }'
```

## Submit Model Outputs

```bash
curl -X POST http://localhost:5001/public/submit_model \
  -H "Content-Type: application/json" \
  -d '{
    "benchmarkDatasetName": "demo_classification",
    "modelName": "my-model",
    "modelResults": ["positive", "negative"],
    "sentence_ids": [0, 1],
    "metadata": {
      "model_version": "1.0",
      "paper_url": "https://example.com/paper"
    }
  }'
```

## View Leaderboard

```bash
curl "http://localhost:5001/public/get_leaderboard?page=1&page_size=25"
curl "http://localhost:5001/public/get_leaderboard?dataset=demo_classification&page=1&page_size=25"
```

The response includes `page`, `page_size`, and `total`.

## Export Leaderboard

```bash
curl "http://localhost:5001/public/export/leaderboard?format=json"
curl "http://localhost:5001/public/export/leaderboard?dataset=demo_classification&format=csv"
```
