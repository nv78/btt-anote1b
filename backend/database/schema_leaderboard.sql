-- Leaderboard benchmark tables. SQLite is the zero-config default used by app.py.
-- JSON payloads are stored as TEXT and decoded by the Flask routes.

CREATE TABLE IF NOT EXISTS benchmark_datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    task_type TEXT NOT NULL,
    evaluation_metric TEXT NOT NULL,
    reference_data TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_benchmark_datasets_active
    ON benchmark_datasets (active);

CREATE TABLE IF NOT EXISTS model_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_dataset_id INTEGER NOT NULL,
    model_name TEXT NOT NULL,
    submitted_by TEXT NOT NULL,
    submitter_id TEXT,
    model_results TEXT NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (benchmark_dataset_id) REFERENCES benchmark_datasets(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_model_submissions_dataset
    ON model_submissions (benchmark_dataset_id);

CREATE INDEX IF NOT EXISTS idx_model_submissions_submitter
    ON model_submissions (submitter_id);

CREATE INDEX IF NOT EXISTS idx_model_submissions_created
    ON model_submissions (created);

CREATE TABLE IF NOT EXISTS evaluation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_submission_id INTEGER NOT NULL,
    score REAL NOT NULL,
    evaluation_details TEXT NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_submission_id) REFERENCES model_submissions(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_evaluation_submission
    ON evaluation_results (model_submission_id);

CREATE TABLE IF NOT EXISTS dataset_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_name TEXT NOT NULL,
    task_type TEXT NOT NULL,
    description TEXT NOT NULL,
    url TEXT,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    admin_notes TEXT,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dataset_requests_status
    ON dataset_requests (status);

CREATE INDEX IF NOT EXISTS idx_dataset_requests_created
    ON dataset_requests (created);
