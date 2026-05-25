"""Abstract base class for all metric collectors."""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3


@dataclass
class MetricRecord:
    """A single metric data point to be published to SQS."""

    customer_id: str
    collection_timestamp: str
    region: str
    service: str
    resource_type: str
    resource_id: str
    resource_name: str
    metric_name: str
    metric_value: Any          # float for numeric, str for inventory/state
    unit: str                  # "percent", "bytes", "count", "none", etc.
    dimensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict for JSON encoding."""
        return {
            "customer_id": self.customer_id,
            "collection_timestamp": self.collection_timestamp,
            "region": self.region,
            "service": self.service,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "unit": self.unit,
            "dimensions": self.dimensions,
        }


class BaseCollector(ABC):
    """Abstract base class for all AWS service collectors.

    Each subclass collects metrics for one AWS service in one region.
    """

    SERVICE_NAME: str = "unknown"

    def __init__(
        self,
        session: boto3.Session,
        region: str,
        customer_id: str,
    ) -> None:
        self.session = session
        self.region = region
        self.customer_id = customer_id
        self.logger = logging.getLogger(f"collector.{self.SERVICE_NAME}")
        self._collection_timestamp = datetime.now(timezone.utc).isoformat()

    def _make_record(
        self,
        resource_type: str,
        resource_id: str,
        resource_name: str,
        metric_name: str,
        metric_value: Any,
        unit: str,
        dimensions: Optional[Dict[str, Any]] = None,
    ) -> MetricRecord:
        """Factory method to create a MetricRecord with common fields pre-filled."""
        return MetricRecord(
            customer_id=self.customer_id,
            collection_timestamp=self._collection_timestamp,
            region=self.region,
            service=self.SERVICE_NAME,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            metric_name=metric_name,
            metric_value=metric_value,
            unit=unit,
            dimensions=dimensions or {},
        )

    @abstractmethod
    def collect(self) -> List[MetricRecord]:
        """Collect metrics and return a list of MetricRecord objects.

        Must not raise exceptions — catch all errors internally and return
        whatever was successfully collected.
        """
