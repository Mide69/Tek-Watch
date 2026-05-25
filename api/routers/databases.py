"""Databases router — RDS, DynamoDB, ElastiCache metrics."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/rds")
async def get_rds_instances(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get RDS instance inventory and metrics."""
    ts = TimestreamQueryService()
    instances = ts.get_resources_by_service(customer.customer_id, "rds")
    return {"instances": instances}


@router.get("/dynamodb")
async def get_dynamodb_tables(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get DynamoDB table metrics."""
    ts = TimestreamQueryService()
    tables = ts.get_resources_by_service(customer.customer_id, "dynamodb")
    return {"tables": tables}


@router.get("/elasticache")
async def get_elasticache_clusters(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get ElastiCache cluster metrics."""
    ts = TimestreamQueryService()
    clusters = ts.get_resources_by_service(customer.customer_id, "elasticache")
    return {"clusters": clusters}
