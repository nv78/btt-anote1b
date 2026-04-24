# Operations

## Persistence

Local development works without a database. The API stores custom datasets, imported datasets, submissions, and evaluations in memory.

For persistence, configure MySQL environment variables and load `backend/database/schema.sql`:

```bash
export DB_HOST=localhost
export DB_USER=root
export DB_PASSWORD=
export DB_NAME=agents
export DB_PORT=3306
```

## Configuration

- `PORT`: Flask port. Use `5001` for the current frontend default.
- `ALLOWED_ORIGINS`: comma-separated CORS origins. Development defaults to local React origins. Non-development environments must set this explicitly.
- `REACT_APP_API_BASE`: frontend API base URL.
- `REACT_APP_GA_ID`: optional Google Analytics measurement id. Leave unset in local development.
- `LEADERBOARD_API_KEYS`: comma-separated API keys for write endpoints. If unset, writes stay open for local development.
- `REQUIRE_API_KEY`: set to `true` to require `X-API-Key` even if keys are injected later by deployment config.
- `SUBMIT_MODEL_RATE_LIMIT`, `ADD_DATASET_RATE_LIMIT`, `IMPORT_DATASET_RATE_LIMIT`, `RUN_CSV_RATE_LIMIT`: per-IP limits such as `10/minute`.
- `DISABLE_RATE_LIMIT`: set to `1` for trusted local test runs.
- `TRUSTED_REMOTE_CODE_MODELS`: comma-separated Hugging Face model ids allowed to use `trust_remote_code`.

## Remaining Known Gaps

- Hugging Face imports are synchronous and bounded by `limit`.
- Imported label names are generic for datasets that expose numeric labels without feature metadata.
- The in-memory store is for development only.
- MySQL schema migrations are not yet versioned.
