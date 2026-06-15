"""Alerts router — threshold and AI anomaly alerts."""
import asyncio
import csv
import io
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import StreamingResponse

from auth.dependencies import CustomerContext, get_current_customer
from rate_limit import limiter
from services.dynamodb import DynamoDBService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
@limiter.limit("60/minute")
async def get_alerts(
    request: Request,
    customer: CustomerContext = Depends(get_current_customer),
    status_filter: Optional[str] = Query(
        None, description="Filter by status: active, acknowledged, resolved"
    ),
    limit: int = Query(50, ge=1, le=500, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
):
    """Get paginated alerts for the authenticated customer."""
    db = DynamoDBService()
    all_alerts = db.get_alerts(customer.customer_id, status_filter)
    total = len(all_alerts)
    page = all_alerts[offset: offset + limit]
    return {
        "alerts": page,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/export")
@limiter.limit("10/minute")
async def export_alerts(
    request: Request,
    customer: CustomerContext = Depends(get_current_customer),
    status_filter: Optional[str] = Query(None),
    fmt: str = Query("csv", alias="format", pattern="^(csv|json)$"),
):
    """Export all alerts as CSV or JSON."""
    db = DynamoDBService()
    alerts = db.get_alerts(customer.customer_id, status_filter)

    if fmt == "json":
        return {"alerts": alerts, "total": len(alerts)}

    fields = [
        "alert_id", "severity", "status", "type",
        "service", "resource", "description",
        "triggered_at", "acknowledged_at",
        "current_value", "threshold_value",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(alerts)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="alerts.csv"'},
    )


@router.get("/stream")
async def stream_alerts(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Server-Sent Events stream — pushes active alerts every 30 seconds.

    Connect with: EventSource('/api/v1/alerts/stream', {withCredentials: true})
    """
    async def event_generator():
        db = DynamoDBService()
        last_count = -1
        while True:
            try:
                active = db.get_alerts(customer.customer_id, "active")
                count = len(active)
                if count != last_count:
                    last_count = count
                    payload = json.dumps({"alerts": active, "total": count})
                    yield f"data: {payload}\n\n"
                else:
                    yield ": heartbeat\n\n"
            except Exception as exc:
                logger.error("SSE error for customer=%s: %s", customer.customer_id, exc)
                yield f"data: {json.dumps({'error': 'stream error'})}\n\n"
            await asyncio.sleep(30)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.put("/{alert_id}/acknowledge", status_code=status.HTTP_200_OK)
async def acknowledge_alert(
    alert_id: str = Path(...),
    customer: CustomerContext = Depends(get_current_customer),
):
    """Acknowledge an alert."""
    db = DynamoDBService()
    success = db.acknowledge_alert(customer.customer_id, alert_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found or already acknowledged",
        )
    return {"status": "acknowledged", "alert_id": alert_id}
