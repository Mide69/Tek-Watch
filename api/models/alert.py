"""Alert Pydantic models."""
from typing import Optional
from pydantic import BaseModel


class Alert(BaseModel):
    """Alert record as stored in DynamoDB."""
    customer_id: str
    alert_id: str
    type: str                    # "threshold" | "ai_anomaly"
    severity: str                # "low" | "medium" | "high" | "critical"
    service: str
    resource_id: str
    resource_name: Optional[str] = None
    metric_name: str
    current_value: Optional[float] = None
    threshold_value: Optional[float] = None
    description: str
    recommendation: Optional[str] = None
    status: str = "active"       # "active" | "acknowledged" | "resolved"
    triggered_at: str
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None


class AcknowledgeAlertResponse(BaseModel):
    status: str
    alert_id: str
