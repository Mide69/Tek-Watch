"""
Tek Watch Agent — entry point.

Execution flow:
  1. Load config from environment variables
  2. Discover all active AWS regions
  3. Run regional collectors in parallel (ThreadPoolExecutor)
  4. Run global collectors (IAM, Cost Explorer)
  5. Publish all records to SQS
  6. Send heartbeat record
  7. Exit (ECS task completes)
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List

import boto3

from collectors.acm import ACMCollector
from collectors.base import MetricRecord
from collectors.cloudfront import CloudFrontCollector
from collectors.cloudtrail import CloudTrailCollector
from collectors.cloudwatch_alarms import CloudWatchAlarmsCollector
from collectors.config_service import ConfigServiceCollector
from collectors.cost_explorer import CostExplorerCollector
from collectors.dynamodb import DynamoDBCollector
from collectors.ec2 import EC2Collector
from collectors.ecs import ECSCollector
from collectors.eks import EKSCollector
from collectors.elasticache import ElastiCacheCollector
from collectors.elb import ELBCollector
from collectors.guardduty import GuardDutyCollector
from collectors.iam import IAMCollector
from collectors.lambda_ import LambdaCollector
from collectors.rds import RDSCollector
from collectors.route53 import Route53Collector
from collectors.s3 import S3Collector
from collectors.security_hub import SecurityHubCollector
from collectors.sns import SNSCollector
from collectors.sqs import SQSCollector
from collectors.trusted_advisor import TrustedAdvisorCollector
from collectors.vpc import VPCCollector
from config import load_config
from publisher.sqs_publisher import SQSPublisher
from utils.logger import configure_logging
from utils.region_discovery import discover_active_regions

logger = logging.getLogger(__name__)

# Regional collectors — instantiated per region
REGIONAL_COLLECTORS = [
    EC2Collector,
    LambdaCollector,
    RDSCollector,
    SQSCollector,
    SNSCollector,
    DynamoDBCollector,
    ECSCollector,
    EKSCollector,
    ElastiCacheCollector,
    ELBCollector,
    VPCCollector,
    CloudWatchAlarmsCollector,
    GuardDutyCollector,
    ACMCollector,
    CloudTrailCollector,
    SecurityHubCollector,
    ConfigServiceCollector,
]

# Global collectors — instantiated once (region="global")
GLOBAL_COLLECTORS = [
    IAMCollector,
    CostExplorerCollector,
    S3Collector,          # S3 is global but we collect it once
    CloudFrontCollector,  # CloudFront is global
    Route53Collector,     # Route53 is global
    TrustedAdvisorCollector,  # Support API is global
]


def collect_region(
    session: boto3.Session,
    region: str,
    customer_id: str,
) -> tuple[List[MetricRecord], int]:
    """Run all regional collectors for a single region.

    Returns:
        Tuple of (records, error_count).
    """
    records: List[MetricRecord] = []
    errors = 0

    for CollectorClass in REGIONAL_COLLECTORS:
        try:
            collector = CollectorClass(session, region, customer_id)
            collected = collector.collect()
            records.extend(collected)
            logger.info(
                "Collected %d records from %s in %s",
                len(collected),
                CollectorClass.SERVICE_NAME,
                region,
            )
        except Exception as exc:  # noqa: BLE001 — intentional broad catch per steering doc
            logger.error(
                "Collector %s failed in %s: %s",
                CollectorClass.SERVICE_NAME,
                region,
                exc,
            )
            errors += 1

    return records, errors


def collect_global(
    session: boto3.Session,
    customer_id: str,
) -> tuple[List[MetricRecord], int]:
    """Run all global (non-regional) collectors."""
    records: List[MetricRecord] = []
    errors = 0

    for CollectorClass in GLOBAL_COLLECTORS:
        try:
            collector = CollectorClass(session, "global", customer_id)
            collected = collector.collect()
            records.extend(collected)
            logger.info(
                "Collected %d records from global collector %s",
                len(collected),
                CollectorClass.SERVICE_NAME,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Global collector %s failed: %s", CollectorClass.SERVICE_NAME, exc)
            errors += 1

    return records, errors


def build_heartbeat(
    customer_id: str,
    total_records: int,
    total_errors: int,
    duration_seconds: float,
    regions: List[str],
) -> MetricRecord:
    """Build the final heartbeat MetricRecord."""
    return MetricRecord(
        customer_id=customer_id,
        collection_timestamp=datetime.now(timezone.utc).isoformat(),
        region="global",
        service="agent",
        resource_type="heartbeat",
        resource_id=customer_id,
        resource_name="agent_heartbeat",
        metric_name="heartbeat",
        metric_value="ok",
        unit="none",
        dimensions={
            "total_records_collected": total_records,
            "total_errors": total_errors,
            "collection_duration_seconds": round(duration_seconds, 2),
            "regions_collected": ",".join(regions),
            "services_collected": str(len(REGIONAL_COLLECTORS) + len(GLOBAL_COLLECTORS)),
        },
    )


def main() -> None:
    """Main agent entry point."""
    config = load_config()
    configure_logging(config.log_level)

    logger.info(
        "Agent starting: customer_id=%s region=%s",
        config.customer_id,
        config.aws_region,
    )

    start_time = time.monotonic()
    session = boto3.Session(region_name=config.aws_region)

    # Discover active regions
    regions = discover_active_regions(session)
    logger.info("Running collectors across %d regions", len(regions))

    all_records: List[MetricRecord] = []
    total_errors = 0

    # Regional collectors — parallel
    with ThreadPoolExecutor(max_workers=min(len(regions), 10)) as executor:
        futures = {
            executor.submit(collect_region, session, region, config.customer_id): region
            for region in regions
        }
        for future in as_completed(futures):
            region = futures[future]
            try:
                records, errors = future.result()
                all_records.extend(records)
                total_errors += errors
            except Exception as exc:  # noqa: BLE001
                logger.error("Region %s collection thread failed: %s", region, exc)
                total_errors += 1

    # Global collectors — sequential
    global_records, global_errors = collect_global(session, config.customer_id)
    all_records.extend(global_records)
    total_errors += global_errors

    duration = time.monotonic() - start_time
    logger.info(
        "Collection complete: records=%d errors=%d duration=%.2fs",
        len(all_records),
        total_errors,
        duration,
    )

    # Add heartbeat
    heartbeat = build_heartbeat(
        customer_id=config.customer_id,
        total_records=len(all_records),
        total_errors=total_errors,
        duration_seconds=duration,
        regions=regions,
    )
    all_records.append(heartbeat)

    # Publish to SQS
    publisher = SQSPublisher(
        session=session,
        queue_url=config.ingest_queue_url,
        api_key=config.api_key,
    )
    publisher.publish_batch(all_records)

    logger.info("Agent run complete. Exiting.")


if __name__ == "__main__":
    main()
