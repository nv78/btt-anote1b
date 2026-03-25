"""Base types for the dataset ingestion pipeline."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DatasetRecord:
    """A normalised, in-memory representation of an ingested dataset.

    Attributes
    ----------
    name:
        Human-readable dataset name (used as the ``benchmark_datasets.name``
        value when persisted).
    task_type:
        Task category, e.g. ``"translation"``, ``"text_classification"``,
        ``"ner"``, ``"qa"``.
    split:
        Dataset split that was ingested, e.g. ``"test"``, ``"validation"``.
    samples:
        List of dicts, each with at minimum an ``"input"`` key and a
        ``"reference"`` key holding the ground-truth output.
    source_url:
        Original data source URL (HuggingFace hub URL, API endpoint, etc.).
        ``None`` when unavailable.
    metadata:
        Arbitrary extra information (language codes, licence, ingestor
        parameters, etc.).
    """

    name: str
    task_type: str
    split: str
    samples: List[Dict[str, Any]]
    source_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class IngestorBase(abc.ABC):
    """Abstract base class for all dataset ingestors.

    Subclasses must implement :meth:`ingest` which accepts a plain ``dict``
    of source-specific configuration and returns a :class:`DatasetRecord`.
    """

    @abc.abstractmethod
    def ingest(self, config: dict) -> DatasetRecord:
        """Ingest a dataset according to *config* and return a
        :class:`DatasetRecord`.

        Parameters
        ----------
        config:
            Source-specific configuration dictionary.  The accepted keys are
            defined by each concrete subclass.

        Returns
        -------
        DatasetRecord
            A fully-populated record ready to be persisted or evaluated.
        """
