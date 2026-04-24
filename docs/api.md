# API Usage

## Dataset Discovery

```bash
curl http://localhost:5001/public/datasets
curl "http://localhost:5001/public/dataset_details?name=flores_spanish_translation"
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
    "sentence_ids": [0, 1]
  }'
```

## View Leaderboard

```bash
curl http://localhost:5001/public/get_leaderboard
```
