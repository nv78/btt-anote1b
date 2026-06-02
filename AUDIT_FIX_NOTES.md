# Leaderboard Audit Fix Notes

Working list for the Claude + Codex audit consolidation. Keep this file updated as fixes land.

## Already fixed before this pass

- [x] Constant-time comparison in `shared.require_api_key`.
- [x] Constant-time comparison in `submission_detail`.
- [x] Explicit JWT `verify_exp` in JWKS path.
- [x] Production `FLASK_SECRET_KEY` must be configured.
- [x] JSON error handlers for 404/405/500.
- [x] `idx_model_submissions_submitted_by` schema index.

## Open work

- [x] Replace remaining `supplied in configured` API-key checks in submission owner paths.
- [x] Stop returning successful in-memory submissions when a DB write fails.
- [x] Return JSON 400 for malformed numeric query/body parameters.
- [x] Resolve `MySubmissions` frontend/backend auth contract mismatch.
- [x] Replace remaining route-level `print()` calls with structured logging.
- [x] Document missing backend env vars in `.env.example`.
- [x] Add regression tests for the fixes above.
- [x] Fix JSON/CSV upload submission UX so parsed files populate predictions, set a model name, show ready state, and enable submission.
- [x] Include auth/API headers when polling async evaluation jobs from manual uploads and LLM submissions.
- [x] Expose and render discrete dataset labels/options on the submit screen, including manual dropdowns, JSON samples, copied prompts, and public multiple-choice options without leaking answers.
- [x] Back daily submission quotas and per-minute rate limits with DB counters so limits are shared across Gunicorn workers.

## Deferred / documented

- [ ] Handoff note: the `Run with LLM` workflow is wired, but the deployed backend image/environment must include whichever provider package is enabled (`openai`, `anthropic`, or `google-generativeai`) and either accept the user's UI-provided key or provide a server-side API key env var. This is a deployment packaging/config item, not a frontend blocker.
- [ ] App-level load balancing is not implemented in Flask; production load balancing should be provided by Railway/hosting infrastructure in front of Gunicorn.
