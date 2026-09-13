"""
Tek Watch Agent — entry point.

Execution flow:
  1. Load config from environment variables
  2. Work out what is due on this run (utils/schedule.py)
  3. Run regional and global collectors in parallel, against a deadline
  4. Publish all records to SQS, with a heartbeat
  5. Exit (ECS task completes)

What a run covers:
  - every run: the home region, and the global collectors except Cost Explorer
  - every 30 minutes: every enabled region
  - every 6 hours: Cost Explorer

Every run used to do all of it: 17 collectors in each of 17 regions plus
Cost Explorer, every 5 minutes. Cost Explorer bills $0.01 a request, which
came to $74 in eleven days, more than everything else in the account. The
rest of the API calls are all written to CloudTrail, and the organisation
trail's CloudWatch log ingestion was another $29.
"""
import logging
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
from utils.schedule import is_due

logger = logging.getLogger(__name__)

ALL_REGIONS_EVERY_MINUTES = 30   # the dashboard's inventory window is 1 hour
COST_EVERY_MINUTES = 6 * 60      # cost pages read a 24-hour window
# A run must finish before the next one starts, or they stack up. Leave a
# minute of the interval for startup and publishing.
DEADLINE_MARGIN_SECONDS = 60
MIN_DEADLINE_SECONDS = 150

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
    collectors=None,
) -> tuple[List[MetricRecord], int]:
    """Run global (non-regional) collectors, all of them unless told which."""
    records: List[MetricRecord] = []
    errors = 0

    for CollectorClass in (GLOBAL_COLLECTORS if collectors is None else collectors):
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


def plan_run(now: datetime, interval_minutes: int) -> tuple[bool, list]:
    """(sweep every region?, global collectors to run) for a run starting now."""
    all_regions = is_due(now, interval_minutes, ALL_REGIONS_EVERY_MINUTES)
    globals_due = [
        c for c in GLOBAL_COLLECTORS
        if c is not CostExplorerCollector or is_due(now, interval_minutes, COST_EVERY_MINUTES)
    ]
    return all_regions, globals_due


def deadline_seconds(interval_minutes: int) -> int:
    return max(MIN_DEADLINE_SECONDS, interval_minutes * 60 - DEADLINE_MARGIN_SECONDS)


def main() -> None:
    """Main agent entry point."""
    config = load_config()
    configure_logging(config.log_level)

    logger.info(
        "Agent starting: customer_id=%s region=%s interval=%dm",
        config.customer_id,
        config.aws_region,
        config.run_interval_minutes,
    )

    start_time = time.monotonic()
    budget = deadline_seconds(config.run_interval_minutes)
    session = boto3.Session(region_name=config.aws_region)

    sweep_all, globals_due = plan_run(datetime.now(timezone.utc), config.run_interval_minutes)
    regions = discover_active_regions(session) if sweep_all else [config.aws_region]
    logger.info(
        "Running collectors across %d regions (%s); global: %s",
        len(regions),
        "all enabled" if sweep_all else "home only",
        ", ".join(c.SERVICE_NAME for c in globals_due),
    )

    all_records: List[MetricRecord] = []
    total_errors = 0

    # boto3 sessions are not safe to share between threads, so each job gets
    # its own. Credentials come from the task role either way.
    def region_job(region: str):
        return collect_region(boto3.Session(region_name=region), region, config.customer_id)

    def global_job():
        return collect_global(boto3.Session(region_name=config.aws_region), config.customer_id, globals_due)

    executor = ThreadPoolExecutor(max_workers=min(len(regions) + 1, 10))
    futures = {executor.submit(region_job, region): region for region in regions}
    futures[executor.submit(global_job)] = "global"

    pending = set(futures)
    timed_out = False
    while pending:
        remaining = budget - (time.monotonic() - start_time)
        if remaining <= 0:
            timed_out = True
            break
        done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
        for future in done:
            name = futures[future]
            try:
                records, errors = future.result()
                all_records.extend(records)
                total_errors += errors
            except Exception as exc:  # noqa: BLE001
                logger.error("Collection thread %s failed: %s", name, exc)
                total_errors += 1

    if timed_out:
        unfinished = sorted(futures[f] for f in pending)
        logger.warning(
            "Deadline of %ds reached; publishing without: %s", budget, ", ".join(unfinished)
        )
        total_errors += len(unfinished)
    executor.shutdown(wait=False, cancel_futures=True)

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
    if timed_out:
        # Threads still stuck in a slow call would otherwise keep the task,
        # and the bill, running: Python waits for pool threads at exit.
        logging.shutdown()
        os._exit(0)


if __name__ == "__main__":
    main()
