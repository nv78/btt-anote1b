# Dataset ingestion pipeline
# Provides pluggable ingestors for HuggingFace and HTTP API sources.

from .base import DatasetRecord, IngestorBase
from .huggingface import HuggingFaceIngestor
from .http_api import HttpApiIngestor

__all__ = [
    "DatasetRecord",
    "IngestorBase",
    "HuggingFaceIngestor",
    "HttpApiIngestor",
]
