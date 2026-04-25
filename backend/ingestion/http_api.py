"""HTTP API dataset ingestor."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import DatasetRecord, IngestorBase

logger = logging.getLogger(__name__)


class HttpApiIngestor(IngestorBase):
    """Ingest a dataset from an arbitrary HTTP JSON API.

    The ingestor issues a single HTTP GET request to *url*, parses the JSON
    response, and maps two fields from each record into the normalised
    ``{"input": ..., "reference": ...}`` sample format.

    The response body may be either:

    * A JSON **array** of objects — each object is treated as a sample.
    * A JSON **object** with a key that holds the array — in this case pass
      ``data_key`` in the config to indicate which top-level key contains the
      list.

    Config keys
    -----------
    url : str
        Full URL to request, e.g.
        ``"https://example.com/api/v1/dataset?lang=es"``.
    auth_header : str, optional
        Value for the ``Authorization`` header (e.g. ``"Bearer <token>"``).
    input_field : str
        Name of the JSON field to use as model input.
    reference_field : str
        Name of the JSON field to use as the ground-truth reference.
    max_samples : int, optional
        Maximum number of samples to include.  Defaults to ``500``.
    data_key : str, optional
        If the response is a JSON object, the key whose value is the list of
        samples.  Ignored when the top-level response is already a list.
    task_type : str, optional
        Task category for the :class:`DatasetRecord`.  Defaults to
        ``"translation"``.
    name : str, optional
        Override the dataset name in the returned record.  Defaults to the
        *url* value.
    """

    def ingest(self, config: dict) -> DatasetRecord:
        try:
            import urllib.request as _urllib_request
            import json as _json
        except ImportError as exc:
            raise ImportError(
                "Standard library modules urllib and json are required."
            ) from exc

        url: str = config["url"]
        auth_header: Optional[str] = config.get("auth_header")
        input_field: str = config["input_field"]
        reference_field: str = config["reference_field"]
        max_samples: int = int(config.get("max_samples", 500))
        data_key: Optional[str] = config.get("data_key")
        task_type: str = config.get("task_type", "translation")
        split: str = config.get("split", "test")
        dataset_name: str = config.get("name", url)

        logger.info(
            "Fetching dataset from HTTP API",
            extra={"event": "http_ingest_start", "url": url},
        )

        req = _urllib_request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        if auth_header:
            req.add_header("Authorization", auth_header)

        try:
            with _urllib_request.urlopen(req, timeout=30) as resp:
                raw_bytes = resp.read()
        except Exception as exc:
            logger.error(
                "HTTP request failed during ingestion",
                extra={"event": "http_ingest_error", "url": url, "error": str(exc)},
            )
            raise RuntimeError(
                f"Failed to fetch dataset from '{url}': {exc}"
            ) from exc

        try:
            body: Any = _json.loads(raw_bytes)
        except _json.JSONDecodeError as exc:
            raise ValueError(
                f"Response from '{url}' is not valid JSON: {exc}"
            ) from exc

        # Unwrap envelope if needed
        if isinstance(body, dict):
            if data_key:
                records = body[data_key]
            else:
                # Best-effort: look for the first list value
                records = next(
                    (v for v in body.values() if isinstance(v, list)), []
                )
        elif isinstance(body, list):
            records = body
        else:
            raise ValueError(
                f"Unexpected JSON response type '{type(body).__name__}' from '{url}'. "
                "Expected a list or an object."
            )

        if max_samples:
            records = records[:max_samples]

        samples: List[Dict[str, Any]] = []
        for i, record in enumerate(records):
            if not isinstance(record, dict):
                logger.warning(
                    "Skipping non-dict record at index %d from '%s'", i, url
                )
                continue
            samples.append(
                {
                    "input": record.get(input_field, ""),
                    "reference": record.get(reference_field, ""),
                }
            )

        metadata: Dict[str, Any] = {
            "url": url,
            "input_field": input_field,
            "reference_field": reference_field,
            "sample_count": len(samples),
        }

        logger.info(
            "HTTP API dataset ingested",
            extra={
                "event": "http_ingest_complete",
                "url": url,
                "sample_count": len(samples),
            },
        )

        return DatasetRecord(
            name=dataset_name,
            task_type=task_type,
            split=split,
            samples=samples,
            source_url=url,
            metadata=metadata,
        )
