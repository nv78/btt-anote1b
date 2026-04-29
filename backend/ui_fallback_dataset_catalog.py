"""
Static metadata for datasets that appear only in the Leaderboard SPA fallback grid.

When /public/get_leaderboard is empty, the frontend shows demo cards; dataset_details must
still resolve those names so Details navigation works offline without DB rows.
"""

# Keys MUST be lowercased dataset display names (same strings as Leaderboard.js fallback).
UI_FALLBACK_DATASETS_BY_LOWER_NAME = {
    "financebench - retrieval accuracy": {
        "name": "FinanceBench - Retrieval Accuracy",
        "task_type": "retrieval",
        "evaluation_metric": "retrieval_accuracy",
        "url": "https://github.com/patronus-ai/financebench",
        "description": "Retrieval-quality benchmark over financial documents; leaderboard ranks by retrieval accuracy.",
    },
    "amazon reviews - classification accuracy": {
        "name": "Amazon Reviews - Classification Accuracy",
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "url": "https://huggingface.co/datasets/m-ric/amazon_product_reviews_datafiniti",
        "description": "Product review sentiment / classification; primary metric is accuracy.",
    },
    "rag instruct - answer accuracy": {
        "name": "RAG Instruct - Answer Accuracy",
        "task_type": "document_qa",
        "evaluation_metric": "exact_match",
        "url": "https://huggingface.co/datasets/llmware/rag_instruct_benchmark_tester",
        "description": "RAG-style QA; rankings use exact match unless otherwise noted for a run.",
    },
    "financial phrasebank - classify accuracy": {
        "name": "Financial Phrasebank - Classify Accuracy",
        "task_type": "text_classification",
        "evaluation_metric": "f1",
        "url": "https://huggingface.co/datasets/takala/financial_phrasebank",
        "description": "Financial sentiment classification; macro-F1 is a standard primary score.",
    },
    "trec - hierarchical classification accuracy": {
        "name": "TREC - Hierarchical Classification Accuracy",
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "url": "https://huggingface.co/datasets/CogComp/trec",
        "description": "Hierarchical text classification (TREC-style); primary metric is accuracy.",
    },
    "banking dataset - classification accuracy": {
        "name": "Banking Dataset - Classification Accuracy",
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "url": "https://huggingface.co/datasets/takala/financial_phrasebank",
        "description": "Banking intent / classification benchmark; primary metric is accuracy.",
    },
    "arc-smart": {
        "name": "ARC-SMART",
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "url": "https://huggingface.co/datasets/vipulgupta/arc-smart",
        "description": "ARC-style multiple-choice reasoning; scores reported as accuracy.",
    },
    "mmlu-smart": {
        "name": "MMLU-SMART",
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "url": "https://huggingface.co/datasets/vipulgupta/mmlu-smart",
        "description": "MMLU-style knowledge subset; scores reported as accuracy.",
    },
    "commonsenseqa-smart": {
        "name": "CommonsenseQA-SMART",
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "url": "https://huggingface.co/datasets/vipulgupta/commonsense_qa_smart",
        "description": "Commonsense QA multiple choice; scores reported as accuracy.",
    },
    "geolocation inference - median distance error": {
        "name": "Geolocation Inference - Median Distance Error",
        "task_type": "geolocation",
        "evaluation_metric": "median_distance_error",
        "url": "https://github.com/njspyx/location-inference",
        "description": "Predict coordinates from images/text; lower median great-circle distance (km) is better.",
    },
}
