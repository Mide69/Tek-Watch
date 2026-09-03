"""Databases router — RDS instances, DynamoDB tables, ElastiCache clusters."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.inventory_view import dim, flag, num, text
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


def _int_dim(resource, key):
    """A dimension that holds a whole number, or None if absent."""
    raw = dim(resource, key)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


@router.get("/rds")
async def get_rds_instances(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get RDS instance inventory and metrics."""
    ts = TimestreamQueryService()
    # Field names here have to match the page, not the collector — this used
    # to send "instance_id" and "cpu" while the page reads "db_identifier"
    # and "free_storage_gb"/"read_iops"/"write_iops", none of which existed
    # in the response at all. It rendered because the page destructures with
    # optional chaining in places, but every RDS instance showed as
    # nameless with blank IOPS.
    instances = []
    for i in ts.get_service_inventory(customer.customer_id, "rds"):
        free_bytes = num(i, "free_storage_bytes")
        instances.append({
            "db_identifier": i["resource_id"],
            "region": i.get("region") or "",
            "engine": dim(i, "engine"),
            "engine_version": dim(i, "engine_version"),
            "instance_class": dim(i, "instance_class"),
            "az": dim(i, "az"),
            "multi_az": flag(i, "multi_az"),
            "allocated_storage_gb": _int_dim(i, "allocated_storage_gb"),
            "status": text(i, "db_instance_status", "unknown"),
            "storage_used_percent": num(i, "storage_used_percent"),
            "free_storage_gb": None if free_bytes is None else round(free_bytes / (1024 ** 3), 1),
            "cpu": num(i, "cpu_utilization_percent"),
            "connections": num(i, "database_connections"),
            "read_iops": num(i, "read_iops"),
            "write_iops": num(i, "write_iops"),
            "metrics": None,
            "last_seen": i.get("last_seen"),
        })
    if region:
        instances = [i for i in instances if i["region"] == region]
    return {"instances": instances}


@router.get("/dynamodb")
async def get_dynamodb_tables(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get DynamoDB table inventory and capacity metrics."""
    ts = TimestreamQueryService()
    tables = [
        {
            "table_name": t["resource_name"],
            "region": t.get("region") or "",
            "status": text(t, "table_status", "unknown"),
            "billing_mode": dim(t, "billing_mode"),
            "item_count": num(t, "item_count") or _int_dim(t, "item_count"),
            "size_bytes": num(t, "table_size_bytes"),
            "read_capacity": _int_dim(t, "read_capacity"),
            "write_capacity": _int_dim(t, "write_capacity"),
            "consumed_read": num(t, "consumed_read_capacity_units"),
            "consumed_write": num(t, "consumed_write_capacity_units"),
            "throttled_reads": num(t, "read_throttle_events"),
            "throttled_writes": num(t, "write_throttle_events"),
            "last_seen": t.get("last_seen"),
        }
        for t in ts.get_service_inventory(customer.customer_id, "dynamodb")
    ]
    if region:
        tables = [t for t in tables if t["region"] == region]
    return {"tables": tables}


@router.get("/elasticache")
async def get_elasticache_clusters(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get ElastiCache cluster inventory and metrics."""
    ts = TimestreamQueryService()
    clusters = [
        {
            "cluster_id": c["resource_id"],
            "cluster_name": c["resource_name"],
            "region": c.get("region") or "",
            "engine": dim(c, "engine"),
            "engine_version": dim(c, "engine_version"),
            "node_type": dim(c, "node_type"),
            "status": text(c, "cache_cluster_status", "unknown"),
            "cpu": num(c, "cpu_utilization_percent"),
            "evictions": num(c, "evictions"),
            "hit_rate": num(c, "cache_hit_rate"),
            "last_seen": c.get("last_seen"),
        }
        for c in ts.get_service_inventory(customer.customer_id, "elasticache")
    ]
    if region:
        clusters = [c for c in clusters if c["region"] == region]
    return {"clusters": clusters}
