"""Compute router — EC2, Lambda, ECS/EKS metrics."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/ec2")
async def get_ec2_instances(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get EC2 instance inventory and metrics."""
    ts = TimestreamQueryService()
    instances = ts.get_resources_by_service(customer.customer_id, "ec2")
    return {"instances": instances}


@router.get("/lambda")
async def get_lambda_functions(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get Lambda function inventory and metrics."""
    ts = TimestreamQueryService()
    functions = ts.get_resources_by_service(customer.customer_id, "lambda")
    return {"functions": functions}


@router.get("/ecs")
async def get_ecs_services(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get ECS/EKS service metrics."""
    ts = TimestreamQueryService()
    services = ts.get_resources_by_service(customer.customer_id, "ecs")
    return {"services": services}
