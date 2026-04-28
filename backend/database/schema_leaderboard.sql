-- Leaderboard benchmark tables (used by backend/app.py). Apply to MySQL 8+.
-- Keep separate from legacy monolith schema.sql unless you intentionally share one database.

CREATE TABLE IF NOT EXISTS benchmark_datasets (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    task_type VARCHAR(100) NOT NULL,
    evaluation_metric VARCHAR(100) NOT NULL,
    reference_data JSON NOT NULL,
    active TINYINT(1) NOT NULL DEFAULT 1,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_benchmark_datasets_name (name),
    KEY idx_benchmark_datasets_active (active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS model_submissions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    benchmark_dataset_id BIGINT NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    submitted_by VARCHAR(255) NOT NULL,
    submitter_id VARCHAR(255) NULL,
    model_results JSON NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_model_submissions_dataset
        FOREIGN KEY (benchmark_dataset_id) REFERENCES benchmark_datasets(id)
        ON DELETE CASCADE,
    KEY idx_model_submissions_dataset (benchmark_dataset_id),
    KEY idx_model_submissions_submitter (submitter_id),
    KEY idx_model_submissions_created (created)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluation_results (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    model_submission_id BIGINT NOT NULL,
    score DOUBLE NOT NULL,
    evaluation_details JSON NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_evaluation_submission
        FOREIGN KEY (model_submission_id) REFERENCES model_submissions(id)
        ON DELETE CASCADE,
    KEY idx_evaluation_submission (model_submission_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- If you created model_submissions before submitter_id existed:
-- ALTER TABLE model_submissions ADD COLUMN submitter_id VARCHAR(255) NULL AFTER submitted_by;
-- CREATE INDEX idx_model_submissions_submitter ON model_submissions (submitter_id);
