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
- `ALLOWED_ORIGINS`: comma-separated CORS origins. Defaults to `*` for local development.
- `REACT_APP_API_BASE`: frontend API base URL.

## Remaining Known Gaps

- Hugging Face imports are synchronous and bounded by `limit`.
- Imported label names are generic for datasets that expose numeric labels without feature metadata.
- The in-memory store is for development only.
- MySQL schema migrations are not yet versioned.
