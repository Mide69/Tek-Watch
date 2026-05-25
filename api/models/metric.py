"""Metric Pydantic models."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class MetricDataPoint(BaseModel):
    """A single time-series data point."""
    time: str
    value: Optional[float] = None


class TimeSeriesResponse(BaseModel):
    resource_id: str
    metric_name: str
    time_range: str
    data: List[MetricDataPoint] = []


class ResourceMetric(BaseModel):
    """A resource with its latest metric value."""
    resource_id: str
    resource_name: Optional[str] = None
    metric_name: str
    value: Any
    time: Optional[str] = None
    dimensions: Dict[str, Any] = {}
