# Anote Leaderboard

The leaderboard benchmarks model submissions against public or curated datasets. This repo runs a Flask API, a React frontend, optional MySQL persistence, CSV benchmark runners, and a lightweight Hugging Face dataset import path.

## What You Can Do

- Add benchmark datasets.
- Fetch source questions or sentences for a dataset.
- Submit model outputs for scoring.
- View ranked leaderboard entries.
- Inspect metric definitions by task type.
- Import bounded Hugging Face splits for local or persisted evaluation.

The frontend keeps the existing Anote dark UI. The imported Personal repo functionality is integrated at the API layer instead of replacing the current app structure.
