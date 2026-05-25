"""Admin operations router — platform health monitoring."""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends

from auth.dependencies import AdminContext, get_current_admin
from config import load_config
from services.dynamodb import DynamoDBService

logger = logging.getLogger(__name__)
router = APIRouter()

# Track API start time for uptime calculation
_START_TIME = time.monotonic()


@router.get("")
async def get_operations_dashboard(
    admin: AdminContext = Depends(get_current_admin),
):
    """Get full platform health metrics for the ops dashboard."""
    config = load_config()
    loop   = asyncio.get_event_loop()

    # ── SQS ingest queue ──────────────────────────────────────────────────────
    ingest_queue: dict = {"depth": 0, "dlq_depth": 0, "oldest_message_age_seconds": None}

    if config.sqs_ingest_queue_url:
        try:
            sqs = boto3.client("sqs", region_name=config.aws_region)

            def _get_queue_attrs(url: str) -> dict:
                return sqs.get_queue_attributes(
                    QueueUrl=url,
                    AttributeNames=[
                        "ApproximateNumberOfMessages",
                        "ApproximateNumberOfMessagesNotVisible",
                        "ApproximateAgeOfOldestMessage",
                    ],
                )["Attributes"]

            attrs = await loop.run_in_executor(
                None, lambda: _get_queue_attrs(config.sqs_ingest_queue_url)
            )
            ingest_queue["depth"] = int(attrs.get("ApproximateNumberOfMessages", 0))
            age = attrs.get("ApproximateAgeOfOldestMessage")
            if age:
                ingest_queue["oldest_message_age_seconds"] = int(age)

            # DLQ
            try:
                dlq_url = config.sqs_ingest_queue_url.replace("-ingest", "-ingest-dlq")
                dlq_attrs = await loop.run_in_executor(
                    None, lambda: _get_queue_attrs(dlq_url)
                )
                ingest_queue["dlq_depth"] = int(
                    dlq_attrs.get("ApproximateNumberOfMessages", 0)
                )
            except ClientError:
                pass

        except ClientError as exc:
            logger.warning("SQS queue metrics failed: %s", exc)

    # ── Customer / agent summary ───────────────────────────────────────────────
    db = DynamoDBService()
    customers = db.list_customers()
    active_customers = [c for c in customers if c.get("status") == "active"]

    agent_counts: dict = {"healthy": 0, "warning": 0, "offline": 0, "unknown": 0}
    for c in active_customers:
        status = c.get("agent_status", "unknown")
        agent_counts[status] = agent_counts.get(status, 0) + 1

    # ── Ingest consumer metrics (last 1h from CloudWatch) ─────────────────────
    consumer_metrics: dict = {
        "status": "unknown",
        "messages_processed_1h": 0,
        "messages_failed_1h": 0,
    }
    try:
        cw = boto3.client("cloudwatch", region_name=config.aws_region)
        end   = datetime.now(timezone.utc)
        start = end - timedelta(hours=1)
        queue_name = config.sqs_ingest_queue_url.split("/")[-1] if config.sqs_ingest_queue_url else ""

        if queue_name:
            resp = await loop.run_in_executor(
                None,
                lambda: cw.get_metric_statistics(
                    Namespace="AWS/SQS",
                    MetricName="NumberOfMessagesSent",
                    Dimensions=[{"Name": "QueueName", "Value": queue_name}],
                    StartTime=start,
                    EndTime=end,
                    Period=3600,
                    Statistics=["Sum"],
                ),
            )
            pts = resp.get("Datapoints", [])
            consumer_metrics["messages_processed_1h"] = int(pts[0]["Sum"]) if pts else 0
            consumer_metrics["status"] = "running"
    except Exception:  # noqa: BLE001
        pass

    # ── Recent errors from CloudWatch Logs Insights ───────────────────────────
    recent_errors: list = []
    try:
        logs = boto3.client("logs", region_name=config.aws_region)
        end_ts   = int(datetime.now(timezone.utc).timestamp())
        start_ts = end_ts - 3600

        # Derive log group prefix from table name
        prefix = config.dynamodb_customers_table.replace("_customers", "").replace("_", "-")
        log_groups = [
            f"/ecs/{prefix}/api",
            f"/ecs/{prefix}/ingest-consumer",
        ]

        query_resp = await loop.run_in_executor(
            None,
            lambda: logs.start_query(
                logGroupNames=log_groups,
                startTime=start_ts,
                endTime=end_ts,
                queryString=(
                    "fields @timestamp, @logStream, level, message "
                    "| filter level = 'ERROR' "
                    "| sort @timestamp desc "
                    "| limit 10"
                ),
            ),
        )
        query_id = query_resp["queryId"]

        # Poll for results (max 5s, non-blocking)
        for _ in range(10):
            await asyncio.sleep(0.5)
            result = await loop.run_in_executor(
                None,
                lambda: logs.get_query_results(queryId=query_id),
            )
            if result["status"] in ("Complete", "Failed", "Cancelled"):
                for row in result.get("results", []):
                    row_dict = {f["field"]: f["value"] for f in row}
                    recent_errors.append({
                        "timestamp": row_dict.get("@timestamp", ""),
                        "service":   row_dict.get("@logStream", "").split("/")[0],
                        "message":   row_dict.get("message", ""),
                    })
                break

    except Exception:  # noqa: BLE001
        pass  # CloudWatch Logs Insights not critical for ops dashboard

    return {
        "ingest_queue": ingest_queue,
        "api_service": {
            "status":         "healthy",
            "uptime_seconds": int(time.monotonic() - _START_TIME),
        },
        "ingest_consumer": consumer_metrics,
        "customers": {
            "total":          len(customers),
            "active":         len(active_customers),
            "agents_healthy": agent_counts["healthy"],
            "agents_offline": agent_counts["offline"] + agent_counts["unknown"],
        },
        "recent_errors": recent_errors,
    }
