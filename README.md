> [!NOTE]
> **Mirror of [anote-ai/btt-anote1b](https://github.com/anote-ai/btt-anote1b).** Built at [Anote](https://github.com/anote-ai), which I founded, together with the contributors in this repository's commit history.
> The original is the maintained version. Please open issues and PRs there.

# Anote monorepo

**Ship this:** [`Personal/`](Personal/) — FastAPI leaderboard (rigorous eval, anti-gaming levers, metrics API, submissions, history), Vite frontend, `uvicorn main:app`. Deploy and develop here.

**Reference only:** [`Company/`](Company/) — older Flask API + CRA marketing shell. Not the product direction; kept for historical assets (e.g. CSV demos, copy) if you need them. Do not invest in extending Company unless something must be lifted into Personal.

Local dev: `cd Personal`, install `requirements.txt`, run API + optional `frontend/`.
