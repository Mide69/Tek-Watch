"""Discovers all active AWS regions in the customer account."""
import logging
from typing import List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

logger = logging.getLogger(__name__)


def discover_active_regions(session: boto3.Session) -> List[str]:
    """Return all regions that are opted-in or opt-in-not-required.

    Args:
        session: A boto3 Session with credentials for the customer account.

    Returns:
        List of region name strings, e.g. ['eu-west-1', 'us-east-1', ...]
    """
    try:
        ec2 = session.client("ec2", region_name="eu-west-2")
        response = ec2.describe_regions(
            Filters=[
                {
                    "Name": "opt-in-status",
                    "Values": ["opt-in-not-required", "opted-in"],
                }
            ]
        )
        regions = [r["RegionName"] for r in response.get("Regions", [])]
        logger.info("Discovered %d active regions", len(regions))
        return regions
    except (ClientError, EndpointResolutionError) as exc:
        logger.error("Failed to discover regions: %s", exc)
        return ["eu-west-2"]  # Fallback to home region
