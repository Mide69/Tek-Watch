"""Threshold Pydantic models."""
from pydantic import BaseModel, field_validator


class Threshold(BaseModel):
    """Threshold configuration record."""
    PK: str                      # "DEFAULT" or customer_id
    SK: str                      # "{service}#{metric_name}"
    service: str
    metric_name: str
    operator: str                # "gt" | "lt" | "gte" | "lte"
    threshold_value: float
    severity: str                # "low" | "medium" | "high" | "critical"
    enabled: bool = True

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        allowed = {"gt", "lt", "gte", "lte"}
        if v not in allowed:
            raise ValueError(f"operator must be one of {allowed}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "critical"}
        if v not in allowed:
            raise ValueError(f"severity must be one of {allowed}")
        return v


class ThresholdUpsertRequest(BaseModel):
    service: str
    metric_name: str
    operator: str
    threshold_value: float
    severity: str = "medium"
    enabled: bool = True
