"""AI chat service — natural language queries over infrastructure data via Claude tool use."""
import json
import logging
from datetime import datetime, timezone
from typing import Any

import anthropic

from config import load_config
from services.dynamodb import DynamoDBService
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are TekWatch AI, an expert cloud infrastructure assistant embedded in the Tek Watch monitoring platform.

You help customers understand their AWS infrastructure through natural language. You have access to real-time data about:
- Resource inventory (EC2, Lambda, RDS, ECS, S3, and more)
- Cloud costs: month-to-date spend, forecasts, per-service breakdown
- Security: GuardDuty findings, IAM posture, active alerts
- Performance: CPU utilisation, queue depths, service health

Guidelines:
- Lead with the key number or status — be direct and concise
- Format currency values clearly (e.g. $1,234.56)
- Proactively flag anomalies or concerns you spot in the data
- For cost forecasts: explain your methodology (daily average × remaining days)
- If data is unavailable or empty, say so clearly rather than guessing
- Use markdown sparingly — bold for key figures, bullet lists for multiple items

Today's date: {today}
Customer ID: {customer_id}
"""

TOOLS = [
    {
        "name": "get_overview",
        "description": "Get a high-level summary of all AWS resources: total resource count, active alarms, security findings, estimated monthly cost, and agent status.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_cost_summary",
        "description": "Get the current month's cloud spend (MTD), daily cost history, and forecasted monthly spend. Use this for any cost or spend questions.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_cost_breakdown",
        "description": "Get per-AWS-service cost breakdown showing which services are most expensive.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_ec2_instances",
        "description": "Get EC2 instance inventory: count, instance types, states (running/stopped), CPU utilisation, and regions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "description": "AWS region filter (e.g. eu-west-2). Optional."},
            },
        },
    },
    {
        "name": "get_lambda_functions",
        "description": "Get Lambda function inventory with invocation counts, error rates, and duration metrics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "description": "AWS region filter. Optional."},
            },
        },
    },
    {
        "name": "get_ecs_services",
        "description": "Get ECS service details: running vs desired task counts, cluster names, and health status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "description": "AWS region filter. Optional."},
            },
        },
    },
    {
        "name": "get_rds_instances",
        "description": "Get RDS database instance inventory: engine type, storage used, CPU, connections, and status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "description": "AWS region filter. Optional."},
            },
        },
    },
    {
        "name": "get_s3_buckets",
        "description": "Get S3 bucket inventory: bucket names, total size, object count, and versioning status.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_alerts",
        "description": "Get infrastructure alerts with severity, service, and description. Use for questions about problems, incidents, or alert status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "acknowledged", "all"],
                    "description": "Filter by alert status. Default: active.",
                },
                "severity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low"],
                    "description": "Filter by severity. Optional.",
                },
            },
        },
    },
    {
        "name": "get_security_summary",
        "description": "Get security posture summary: GuardDuty findings, IAM issues, compliance flags, and security alert counts by severity.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


async def _execute_tool(tool_name: str, tool_input: dict, customer_id: str) -> Any:
    """Execute a tool and return the result as a JSON-serialisable dict."""
    ts = TimestreamQueryService()
    db = DynamoDBService()

    try:
        if tool_name == "get_overview":
            customer_profile = db.get_customer(customer_id)
            active_alerts = db.get_alerts(customer_id, status_filter="active")
            monthly_cost = ts.get_latest_metric(
                customer_id, "cost_explorer", "forecast", "forecasted_monthly_spend"
            )
            resources = ts.get_resources_by_service(customer_id, "ec2", "5m")
            return {
                "total_resources": len(set(r.get("resource_id") for r in resources)),
                "active_alarms": len([a for a in active_alerts if a.get("type") == "threshold"]),
                "security_findings": len(
                    [a for a in active_alerts if a.get("severity") in ["high", "critical"]]
                ),
                "estimated_monthly_cost": round(float(monthly_cost or 0), 2),
                "agent_status": (
                    customer_profile.get("agent_status", "unknown")
                    if customer_profile
                    else "unknown"
                ),
                "agent_last_seen": (
                    customer_profile.get("last_agent_seen") if customer_profile else None
                ),
            }

        if tool_name == "get_cost_summary":
            daily_costs = ts.get_daily_costs(customer_id)
            mtd_total = sum(float(row.get("cost", 0)) for row in daily_costs)
            stored_forecast = ts.get_latest_metric(
                customer_id, "cost_explorer", "forecast", "forecasted_monthly_spend"
            )
            today = datetime.now(timezone.utc)
            days_elapsed = today.day
            days_in_month = 30
            daily_avg = mtd_total / days_elapsed if days_elapsed > 0 else 0
            calculated_forecast = daily_avg * days_in_month
            return {
                "mtd_total": round(mtd_total, 2),
                "forecasted_monthly": round(float(stored_forecast or calculated_forecast), 2),
                "calculated_forecast_methodology": (
                    f"Daily average ${daily_avg:.2f} × {days_in_month} days = ${calculated_forecast:.2f}"
                ),
                "days_elapsed_this_month": days_elapsed,
                "daily_average": round(daily_avg, 2),
                "recent_daily_costs": daily_costs[-7:],
            }

        if tool_name == "get_cost_breakdown":
            breakdown = ts.get_service_costs(customer_id)
            return {"breakdown": breakdown}

        if tool_name == "get_ec2_instances":
            region = tool_input.get("region")
            instances = ts.get_resources_by_service(customer_id, "ec2")
            if region:
                instances = [i for i in instances if i.get("region") == region]
            return {
                "total": len(instances),
                "running": len([i for i in instances if i.get("state") == "running"]),
                "stopped": len([i for i in instances if i.get("state") == "stopped"]),
                "instances": instances[:20],
            }

        if tool_name == "get_lambda_functions":
            region = tool_input.get("region")
            functions = ts.get_resources_by_service(customer_id, "lambda")
            if region:
                functions = [f for f in functions if f.get("region") == region]
            return {"total": len(functions), "functions": functions[:20]}

        if tool_name == "get_ecs_services":
            region = tool_input.get("region")
            services = ts.get_resources_by_service(customer_id, "ecs")
            if region:
                services = [s for s in services if s.get("region") == region]
            return {"total": len(services), "services": services[:20]}

        if tool_name == "get_rds_instances":
            region = tool_input.get("region")
            instances = ts.get_resources_by_service(customer_id, "rds")
            if region:
                instances = [i for i in instances if i.get("region") == region]
            return {"total": len(instances), "instances": instances[:20]}

        if tool_name == "get_s3_buckets":
            buckets = ts.get_resources_by_service(customer_id, "s3")
            return {"total": len(buckets), "buckets": buckets[:20]}

        if tool_name == "get_alerts":
            status = tool_input.get("status", "active")
            severity = tool_input.get("severity")
            status_filter = None if status == "all" else status
            alerts = db.get_alerts(customer_id, status_filter=status_filter)
            if severity:
                alerts = [a for a in alerts if a.get("severity") == severity]
            return {
                "total": len(alerts),
                "critical": len([a for a in alerts if a.get("severity") == "critical"]),
                "high": len([a for a in alerts if a.get("severity") == "high"]),
                "medium": len([a for a in alerts if a.get("severity") == "medium"]),
                "alerts": alerts[:10],
            }

        if tool_name == "get_security_summary":
            alerts = db.get_alerts(customer_id, status_filter="active")
            security = [
                a for a in alerts
                if a.get("service") in ["guardduty", "security_hub", "iam", "config", "acm"]
            ]
            return {
                "total_findings": len(security),
                "critical": len([a for a in security if a.get("severity") == "critical"]),
                "high": len([a for a in security if a.get("severity") == "high"]),
                "findings": security[:10],
            }

        return {"error": f"Unknown tool: {tool_name}"}

    except Exception as exc:
        logger.error("Tool execution error: tool=%s error=%s", tool_name, exc)
        return {"error": str(exc), "tool": tool_name}


async def process_chat(message: str, customer_id: str, history: list[dict]) -> dict:
    """Process a natural language infrastructure query using Claude with tool use.

    Runs an agentic loop: Claude selects tools → we execute them → Claude
    receives results and continues until it produces a final answer.
    """
    config = load_config()

    if not config.anthropic_api_key:
        return {
            "response": "AI chat requires an Anthropic API key (ANTHROPIC_API_KEY is not set).",
            "tool_calls": [],
            "usage": None,
        }

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    system = SYSTEM_PROMPT.format(today=today, customer_id=customer_id)

    messages: list[dict] = list(history) + [{"role": "user", "content": message}]
    tool_calls_made: list[str] = []

    response = None
    for _ in range(6):  # guard against runaway loops
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_calls_made.append(block.name)
                logger.info(
                    "Chat tool: %s customer=%s input=%s",
                    block.name, customer_id, json.dumps(block.input),
                )
                result = await _execute_tool(block.name, block.input, customer_id)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    text = ""
    if response:
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text
                break

    return {
        "response": text or "I was unable to generate a response. Please try again.",
        "tool_calls": tool_calls_made,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        } if response else None,
    }
