"""Compute router — EC2 instances, Lambda functions, ECS services."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.inventory_view import dim, num, text
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/ec2")
async def get_ec2_instances(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get EC2 instance inventory and CloudWatch metrics."""
    ts = TimestreamQueryService()
    instances = [
        {
            "instance_id": i["resource_id"],
            "instance_name": i["resource_name"],
            "instance_type": dim(i, "instance_type"),
            "state": dim(i, "state") or text(i, "instance_state", "unknown"),
            "region": i.get("region") or "",
            "az": dim(i, "az"),
            "vpc_id": dim(i, "vpc_id"),
            "private_ip": dim(i, "private_ip"),
            "cpu": num(i, "cpu_utilization_percent"),
            "network_in": num(i, "network_in_bytes"),
            "network_out": num(i, "network_out_bytes"),
            "metrics": None,
            "last_seen": i.get("last_seen"),
        }
        for i in ts.get_service_inventory(customer.customer_id, "ec2")
    ]
    if region:
        instances = [i for i in instances if i["region"] == region]
    return {"instances": instances}


@router.get("/lambda")
async def get_lambda_functions(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get Lambda function inventory and invocation metrics."""
    ts = TimestreamQueryService()
    functions = [
        {
            "function_name": f["resource_name"],
            "region": f.get("region") or "",
            "runtime": dim(f, "runtime") or text(f, "function_runtime", ""),
            "memory": num(f, "memory_mb")
            or (float(dim(f, "memory_mb")) if dim(f, "memory_mb").isdigit() else None),
            "timeout": (
                float(dim(f, "timeout_seconds")) if dim(f, "timeout_seconds").isdigit() else None
            ),
            "invocations": num(f, "invocations_24h"),
            "errors": num(f, "errors_24h"),
            "throttles": num(f, "throttles_24h"),
            "duration_avg": num(f, "duration_avg_ms"),
            "metrics": None,
            "last_seen": f.get("last_seen"),
        }
        for f in ts.get_service_inventory(customer.customer_id, "lambda")
    ]
    if region:
        functions = [f for f in functions if f["region"] == region]
    return {"functions": functions}


@router.get("/ecs")
async def get_ecs_services(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get ECS service inventory and task counts."""
    ts = TimestreamQueryService()
    services = [
        {
            "service_name": s["resource_name"],
            "cluster": dim(s, "cluster"),
            "region": s.get("region") or "",
            "status": text(s, "service_status", "unknown"),
            "running": num(s, "running_task_count")
            or (float(dim(s, "running_tasks")) if dim(s, "running_tasks").isdigit() else None),
            "pending": (
                float(dim(s, "pending_tasks")) if dim(s, "pending_tasks").isdigit() else None
            ),
            # Desired count and per-service CPU/memory are not collected.
            "desired": None,
            "cpu": None,
            "memory": None,
            "last_seen": s.get("last_seen"),
        }
        for s in ts.get_service_inventory(customer.customer_id, "ecs")
        # The ecs collector reports clusters as well as services. A service is
        # identified by what was measured about it, so this keeps working on
        # rows written before the events table carried a resource type.
        if "service_status" in (s.get("metrics") or {})
        or "running_task_count" in (s.get("metrics") or {})
    ]
    if region:
        services = [s for s in services if s["region"] == region]
    return {"services": services}
