"""VPC inventory and NAT Gateway metrics collector."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class VPCCollector(BaseCollector):
    """Collects VPC, subnet, NAT gateway, and internet gateway inventory."""

    SERVICE_NAME = "vpc"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._ec2 = session.client("ec2", region_name=region)
        self._cw = session.client("cloudwatch", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect VPC inventory and NAT gateway metrics."""
        records: List[MetricRecord] = []
        try:
            records.extend(self._collect_vpcs())
            records.extend(self._collect_nat_gateways())
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("VPC collection failed in %s: %s", self.region, exc)
        return records

    def _collect_vpcs(self) -> List[MetricRecord]:
        """Collect VPC and subnet inventory."""
        records: List[MetricRecord] = []
        try:
            vpcs = self._ec2.describe_vpcs().get("Vpcs", [])
            subnets = self._ec2.describe_subnets().get("Subnets", [])

            subnet_counts: dict = {}
            for subnet in subnets:
                vpc_id = subnet.get("VpcId", "")
                subnet_counts[vpc_id] = subnet_counts.get(vpc_id, 0) + 1

            for vpc in vpcs:
                vpc_id = vpc.get("VpcId", "")
                name = self._get_tag(vpc.get("Tags", []), "Name", vpc_id)
                state = vpc.get("State", "unknown")
                is_default = vpc.get("IsDefault", False)
                cidr = vpc.get("CidrBlock", "")

                records.append(self._make_record(
                    resource_type="vpc",
                    resource_id=vpc_id,
                    resource_name=name,
                    metric_name="vpc_state",
                    metric_value=state,
                    unit="none",
                    dimensions={
                        "cidr_block": cidr,
                        "is_default": str(is_default),
                        "subnet_count": subnet_counts.get(vpc_id, 0),
                    },
                ))
        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("VPC describe failed in %s: %s", self.region, exc)
        return records

    def _collect_nat_gateways(self) -> List[MetricRecord]:
        """Collect NAT gateway inventory and CloudWatch metrics."""
        records: List[MetricRecord] = []
        try:
            paginator = self._ec2.get_paginator("describe_nat_gateways")
            nat_gateways = []
            for page in paginator.paginate():
                nat_gateways.extend(page.get("NatGateways", []))

            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=10)

            for ngw in nat_gateways:
                ngw_id = ngw.get("NatGatewayId", "")
                state = ngw.get("State", "unknown")
                vpc_id = ngw.get("VpcId", "")
                subnet_id = ngw.get("SubnetId", "")

                records.append(self._make_record(
                    resource_type="nat_gateway",
                    resource_id=ngw_id,
                    resource_name=ngw_id,
                    metric_name="nat_gateway_state",
                    metric_value=state,
                    unit="none",
                    dimensions={"vpc_id": vpc_id, "subnet_id": subnet_id},
                ))

                if state != "available":
                    continue

                for cw_name, metric_name, unit in [
                    ("BytesInFromDestination", "bytes_in_from_destination", "bytes"),
                    ("BytesInFromSource",      "bytes_in_from_source",      "bytes"),
                    ("BytesOutToDestination",  "bytes_out_to_destination",  "bytes"),
                    ("BytesOutToSource",       "bytes_out_to_source",       "bytes"),
                    ("PacketsDropCount",       "packets_drop_count",        "count"),
                ]:
                    try:
                        value = self._get_cw_metric(ngw_id, cw_name, start_time, end_time)
                        if value is not None:
                            records.append(self._make_record(
                                resource_type="nat_gateway",
                                resource_id=ngw_id,
                                resource_name=ngw_id,
                                metric_name=metric_name,
                                metric_value=round(value, 2),
                                unit=unit,
                                dimensions={"vpc_id": vpc_id},
                            ))
                    except (ClientError, EndpointResolutionError) as exc:
                        logger.warning("CW metric %s failed for NAT %s: %s", cw_name, ngw_id, exc)

        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("NAT gateway collection failed in %s: %s", self.region, exc)
        return records

    def _get_tag(self, tags: list, key: str, default: str = "") -> str:
        for tag in tags or []:
            if tag.get("Key") == key:
                return tag.get("Value", default)
        return default

    def _get_cw_metric(
        self,
        ngw_id: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[float]:
        response = self._cw.get_metric_statistics(
            Namespace="AWS/NATGateway",
            MetricName=metric_name,
            Dimensions=[{"Name": "NatGatewayId", "Value": ngw_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=["Sum"],
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return None
        return max(datapoints, key=lambda d: d["Timestamp"]).get("Sum")
