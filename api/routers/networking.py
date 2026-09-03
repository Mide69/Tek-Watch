"""Networking router — VPCs, load balancers, CloudFront, Route 53."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.inventory_view import dim, flag, num, text, wants_region_filter
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/vpc")
async def get_vpcs(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get VPC inventory."""
    ts = TimestreamQueryService()
    resources = [
        {
            "vpc_id": dim(v, "vpc_id") or v["resource_id"],
            "name": v["resource_name"],
            "cidr": dim(v, "cidr_block"),
            "region": v.get("region") or "",
            "state": text(v, "vpc_state", "unknown"),
            "subnets": num(v, "subnet_count")
            or (float(dim(v, "subnet_count")) if dim(v, "subnet_count").isdigit() else None),
            "is_default": flag(v, "is_default"),
            # Route tables are not collected, so this stays unknown rather
            # than reporting zero route tables for a VPC that has several.
            "route_tables": None,
            "last_seen": v.get("last_seen"),
        }
        for v in ts.get_service_inventory(customer.customer_id, "vpc")
        # The vpc collector also reports NAT gateways. Selecting on the
        # vpc_state metric rather than resource_type identifies a VPC from
        # what was measured about it, which does not depend on rows written
        # before the events table started carrying a resource type.
        if "vpc_state" in (v.get("metrics") or {})
    ]
    if wants_region_filter(region):
        resources = [v for v in resources if v["region"] == region]
    return {"resources": resources}


@router.get("/elb")
async def get_load_balancers(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get load balancer inventory and health."""
    ts = TimestreamQueryService()
    load_balancers = []
    for lb in ts.get_service_inventory(customer.customer_id, "elb"):
        healthy = num(lb, "healthy_host_count")
        unhealthy = num(lb, "unhealthy_host_count")
        latency = num(lb, "target_response_time_sec")
        if latency is None:
            latency = num(lb, "latency_seconds")

        # The collector reports raw HTTP_4XX/5XX counts, not a rate — a
        # count of 3 is meaningless without knowing the request volume it
        # came out of. The page renders a percentage and colours it red past
        # 1%, so this divides by request_count rather than pass the count
        # through as if it already were one.
        requests = num(lb, "request_count")
        count_4xx = num(lb, "http_4xx_count")
        count_5xx = num(lb, "http_5xx_count")
        error_4xx = round(count_4xx / requests * 100, 2) if requests and count_4xx is not None else None
        error_5xx = round(count_5xx / requests * 100, 2) if requests and count_5xx is not None else None

        load_balancers.append({
            "name": lb["resource_name"],
            "region": lb.get("region") or "",
            "type": dim(lb, "type"),
            "scheme": dim(lb, "scheme"),
            "state": text(lb, "load_balancer_state", "unknown"),
            "healthy": healthy,
            "targets": (
                healthy + unhealthy
                if healthy is not None and unhealthy is not None
                else None
            ),
            "request_count": requests,
            "error_4xx": error_4xx,
            "error_5xx": error_5xx,
            "latency_ms": None if latency is None else round(latency * 1000, 1),
            "last_seen": lb.get("last_seen"),
        })
    if wants_region_filter(region):
        load_balancers = [lb for lb in load_balancers if lb["region"] == region]
    return {"load_balancers": load_balancers}


@router.get("/cloudfront")
async def get_cloudfront_distributions(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get CloudFront distribution inventory and edge metrics."""
    ts = TimestreamQueryService()
    distributions = [
        {
            # The page keys each card on cf.id and reads cf.id again for the
            # subtitle — "distribution_id" was never read at all, so every
            # card shared the same React key and the id line was blank.
            "id": d["resource_id"],
            "domain": dim(d, "domain") or d["resource_name"],
            "aliases": [a for a in dim(d, "aliases").split(",") if a],
            "status": text(d, "distribution_status", "unknown"),
            "enabled": flag(d, "enabled"),
            "price_class": dim(d, "price_class"),
            "requests_day": num(d, "requests"),
            "cache_hit": num(d, "cache_hit_rate"),
            "error_rate": num(d, "total_error_rate"),
            "last_seen": d.get("last_seen"),
        }
        for d in ts.get_service_inventory(customer.customer_id, "cloudfront")
    ]
    return {"distributions": distributions}


@router.get("/route53")
async def get_route53_health_checks(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get Route 53 hosted zones and health checks."""
    ts = TimestreamQueryService()
    inventory = ts.get_service_inventory(customer.customer_id, "route53")

    health_checks = [
        {
            "health_check_id": h["resource_id"],
            "name": h["resource_name"],
            "status": text(h, "health_check_status", "unknown"),
            "health_percentage": num(h, "health_percentage"),
            "last_seen": h.get("last_seen"),
        }
        for h in inventory
        if "health_check_status" in (h.get("metrics") or {})
        or "health_percentage" in (h.get("metrics") or {})
    ]
    hosted_zones = [
        {
            "zone_id": z["resource_id"],
            "zone_name": dim(z, "zone_name") or z["resource_name"],
            "record_count": num(z, "record_set_count"),
            "private": flag(z, "private_zone"),
            "last_seen": z.get("last_seen"),
        }
        for z in inventory
        if "record_set_count" in (z.get("metrics") or {})
    ]
    return {"health_checks": health_checks, "hosted_zones": hosted_zones}
