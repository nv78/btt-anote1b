"""HuggingFace dataset ingestor."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import DatasetRecord, IngestorBase

logger = logging.getLogger(__name__)

# Optional dependency — the rest of the platform must work without it.
try:
    import datasets as _hf_datasets  # type: ignore
    HF_DATASETS_AVAILABLE = True
except ImportError:
    _hf_datasets = None  # type: ignore
    HF_DATASETS_AVAILABLE = False
    logger.warning(
        "huggingface 'datasets' library not installed; HuggingFaceIngestor will "
        "raise ImportError at ingest time. Install with: pip install datasets"
    )


class HuggingFaceIngestor(IngestorBase):
    """Ingest a dataset from the HuggingFace Hub.

    Config keys
    -----------
    dataset_id : str
        HuggingFace dataset identifier, e.g. ``"facebook/flores"``.
    config_name : str, optional
        Dataset configuration / subset name (e.g. ``"eng_Latn"``).
        Passed as the second positional argument to
        ``datasets.load_dataset``.
    split : str, optional
        Which split to load.  Defaults to ``"test"``.
    max_samples : int, optional
        Maximum number of samples to include.  Defaults to ``500``.
    input_field : str
        Name of the column to use as the model input.
    reference_field : str
        Name of the column to use as the ground-truth reference.
    task_type : str, optional
        Task category to embed in the returned :class:`DatasetRecord`.
        Defaults to ``"translation"``.
    """

    def ingest(self, config: dict) -> DatasetRecord:
        if not HF_DATASETS_AVAILABLE:
            raise ImportError(
                "The 'datasets' library is required for HuggingFaceIngestor. "
                "Install it with: pip install datasets"
            )

        dataset_id: str = config["dataset_id"]
        config_name: Optional[str] = config.get("config_name")
        split: str = config.get("split", "test")
        max_samples: int = int(config.get("max_samples", 500))
        input_field: str = config["input_field"]
        reference_field: str = config["reference_field"]
        task_type: str = config.get("task_type", "translation")

        logger.info(
            "Loading HuggingFace dataset",
            extra={
                "event": "hf_ingest_start",
                "dataset_id": dataset_id,
                "config_name": config_name,
                "split": split,
            },
        )

        load_kwargs: Dict[str, Any] = {"split": split}
        if config_name:
            hf_dataset = _hf_datasets.load_dataset(
                dataset_id, config_name, **load_kwargs
            )
        else:
            hf_dataset = _hf_datasets.load_dataset(dataset_id, **load_kwargs)

        # Honour max_samples
        if max_samples and len(hf_dataset) > max_samples:
            hf_dataset = hf_dataset.select(range(max_samples))

        samples: List[Dict[str, Any]] = []
        for row in hf_dataset:
            samples.append(
                {
                    "input": row[input_field],
                    "reference": row[reference_field],
                }
            )

        source_url = f"https://huggingface.co/datasets/{dataset_id}"
        dataset_name = config.get(
            "name",
            (
                f"{dataset_id.replace('/', '_')}_{config_name}_{split}"
                if config_name
                else f"{dataset_id.replace('/', '_')}_{split}"
            ),
        )

        metadata: Dict[str, Any] = {
            "dataset_id": dataset_id,
            "split": split,
            "input_field": input_field,
            "reference_field": reference_field,
            "sample_count": len(samples),
        }
        if config_name:
            metadata["config_name"] = config_name

        logger.info(
            "HuggingFace dataset ingested",
            extra={
                "event": "hf_ingest_complete",
                "dataset_id": dataset_id,
                "sample_count": len(samples),
            },
        )

        return DatasetRecord(
            name=dataset_name,
            task_type=task_type,
            split=split,
            samples=samples,
            source_url=source_url,
            metadata=metadata,
        )
