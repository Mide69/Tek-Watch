"""Networking router — VPC, ELB, CloudFront, Route53."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/vpc")
async def get_vpc_resources(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get VPC and subnet inventory."""
    ts = TimestreamQueryService()
    resources = ts.get_resources_by_service(customer.customer_id, "vpc")
    return {"resources": resources}


@router.get("/elb")
async def get_load_balancers(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get load balancer metrics."""
    ts = TimestreamQueryService()
    load_balancers = ts.get_resources_by_service(customer.customer_id, "elb")
    return {"load_balancers": load_balancers}


@router.get("/cloudfront")
async def get_cloudfront_distributions(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get CloudFront distribution metrics."""
    ts = TimestreamQueryService()
    distributions = ts.get_resources_by_service(customer.customer_id, "cloudfront")
    return {"distributions": distributions}


@router.get("/route53")
async def get_route53_health_checks(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get Route53 health check statuses."""
    ts = TimestreamQueryService()
    health_checks = ts.get_resources_by_service(customer.customer_id, "route53")
    return {"health_checks": health_checks}
