"""ELB/ALB/NLB inventory and performance metrics collector."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class ELBCollector(BaseCollector):
    """Collects Application, Network, and Classic Load Balancer metrics."""

    SERVICE_NAME = "elb"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._elbv2 = session.client("elbv2", region_name=region)
        self._elb = session.client("elb", region_name=region)
        self._cw = session.client("cloudwatch", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect ALB/NLB and Classic ELB inventory and metrics."""
        records: List[MetricRecord] = []
        try:
            records.extend(self._collect_v2_load_balancers())
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("ELBv2 collection failed in %s: %s", self.region, exc)
        try:
            records.extend(self._collect_classic_load_balancers())
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("Classic ELB collection failed in %s: %s", self.region, exc)
        return records

    def _collect_v2_load_balancers(self) -> List[MetricRecord]:
        """Collect ALB and NLB metrics."""
        records: List[MetricRecord] = []
        paginator = self._elbv2.get_paginator("describe_load_balancers")
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=10)

        for page in paginator.paginate():
            for lb in page.get("LoadBalancers", []):
                lb_arn = lb.get("LoadBalancerArn", "")
                lb_name = lb.get("LoadBalancerName", "")
                lb_type = lb.get("Type", "")  # application | network | gateway
                state = lb.get("State", {}).get("Code", "unknown")
                scheme = lb.get("Scheme", "")
                vpc_id = lb.get("VpcId", "")

                base_dims = {
                    "type": lb_type,
                    "scheme": scheme,
                    "vpc_id": vpc_id,
                }

                records.append(self._make_record(
                    resource_type="load_balancer",
                    resource_id=lb_arn,
                    resource_name=lb_name,
                    metric_name="load_balancer_state",
                    metric_value=state,
                    unit="none",
                    dimensions=base_dims,
                ))

                if state != "active":
                    continue

                # Extract short name for CW dimension
                # ALB dimension: app/name/id  NLB: net/name/id
                lb_dim_name = "/".join(lb_arn.split("/")[-3:]) if "/" in lb_arn else lb_name

                if lb_type == "application":
                    cw_metrics = [
                        ("RequestCount",            "request_count",            "count",   "Sum"),
                        ("TargetResponseTime",       "target_response_time_sec", "seconds", "Average"),
                        ("HTTPCode_ELB_4XX_Count",   "http_4xx_count",           "count",   "Sum"),
                        ("HTTPCode_ELB_5XX_Count",   "http_5xx_count",           "count",   "Sum"),
                        ("HealthyHostCount",         "healthy_host_count",       "count",   "Average"),
                        ("UnHealthyHostCount",       "unhealthy_host_count",     "count",   "Average"),
                    ]
                    namespace = "AWS/ApplicationELB"
                    dim_key = "LoadBalancer"
                else:
                    cw_metrics = [
                        ("ActiveFlowCount",          "active_flow_count",        "count",   "Average"),
                        ("NewFlowCount",             "new_flow_count",           "count",   "Sum"),
                        ("ProcessedBytes",           "processed_bytes",          "bytes",   "Sum"),
                        ("HealthyHostCount",         "healthy_host_count",       "count",   "Average"),
                        ("UnHealthyHostCount",       "unhealthy_host_count",     "count",   "Average"),
                    ]
                    namespace = "AWS/NetworkELB"
                    dim_key = "LoadBalancer"

                for cw_name, metric_name, unit, stat in cw_metrics:
                    try:
                        value = self._get_cw_metric(
                            namespace, cw_name, dim_key, lb_dim_name, start_time, end_time, stat
                        )
                        if value is not None:
                            records.append(self._make_record(
                                resource_type="load_balancer",
                                resource_id=lb_arn,
                                resource_name=lb_name,
                                metric_name=metric_name,
                                metric_value=round(value, 4),
                                unit=unit,
                                dimensions=base_dims,
                            ))
                    except (ClientError, EndpointResolutionError) as exc:
                        logger.warning("CW %s failed for LB %s: %s", cw_name, lb_name, exc)

        return records

    def _collect_classic_load_balancers(self) -> List[MetricRecord]:
        """Collect Classic ELB metrics."""
        records: List[MetricRecord] = []
        paginator = self._elb.get_paginator("describe_load_balancers")
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=10)

        for page in paginator.paginate():
            for lb in page.get("LoadBalancerDescriptions", []):
                lb_name = lb.get("LoadBalancerName", "")
                scheme = lb.get("Scheme", "")
                vpc_id = lb.get("VPCId", "")

                base_dims = {"type": "classic", "scheme": scheme, "vpc_id": vpc_id}

                records.append(self._make_record(
                    resource_type="load_balancer",
                    resource_id=lb_name,
                    resource_name=lb_name,
                    metric_name="load_balancer_state",
                    metric_value="active",
                    unit="none",
                    dimensions=base_dims,
                ))

                for cw_name, metric_name, unit, stat in [
                    ("RequestCount",        "request_count",        "count",   "Sum"),
                    ("Latency",             "latency_seconds",      "seconds", "Average"),
                    ("HTTPCode_ELB_4XX",    "http_4xx_count",       "count",   "Sum"),
                    ("HTTPCode_ELB_5XX",    "http_5xx_count",       "count",   "Sum"),
                    ("HealthyHostCount",    "healthy_host_count",   "count",   "Average"),
                    ("UnHealthyHostCount",  "unhealthy_host_count", "count",   "Average"),
                ]:
                    try:
                        value = self._get_cw_metric(
                            "AWS/ELB", cw_name, "LoadBalancerName", lb_name,
                            start_time, end_time, stat
                        )
                        if value is not None:
                            records.append(self._make_record(
                                resource_type="load_balancer",
                                resource_id=lb_name,
                                resource_name=lb_name,
                                metric_name=metric_name,
                                metric_value=round(value, 4),
                                unit=unit,
                                dimensions=base_dims,
                            ))
                    except (ClientError, EndpointResolutionError) as exc:
                        logger.warning("CW %s failed for classic ELB %s: %s", cw_name, lb_name, exc)

        return records

    def _get_cw_metric(
        self,
        namespace: str,
        metric_name: str,
        dim_key: str,
        dim_value: str,
        start_time: datetime,
        end_time: datetime,
        stat: str = "Average",
    ) -> Optional[float]:
        response = self._cw.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=[{"Name": dim_key, "Value": dim_value}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=[stat],
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return None
        return max(datapoints, key=lambda d: d["Timestamp"]).get(stat)
