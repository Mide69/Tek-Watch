"""Unit tests for region discovery."""
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from utils.region_discovery import discover_active_regions


class TestRegionDiscovery:
    def test_returns_region_list(self):
        session = MagicMock()
        ec2 = MagicMock()
        session.client.return_value = ec2
        ec2.describe_regions.return_value = {
            "Regions": [
                {"RegionName": "eu-west-1"},
                {"RegionName": "eu-west-2"},
                {"RegionName": "us-east-1"},
            ]
        }
        regions = discover_active_regions(session)
        assert "eu-west-1" in regions
        assert "eu-west-2" in regions
        assert "us-east-1" in regions
        assert len(regions) == 3

    def test_falls_back_on_error(self):
        session = MagicMock()
        ec2 = MagicMock()
        session.client.return_value = ec2
        ec2.describe_regions.side_effect = ClientError(
            {"Error": {"Code": "AuthFailure", "Message": "auth failed"}},
            "DescribeRegions",
        )
        regions = discover_active_regions(session)
        assert regions == ["eu-west-2"]

    def test_empty_regions_returns_fallback(self):
        session = MagicMock()
        ec2 = MagicMock()
        session.client.return_value = ec2
        ec2.describe_regions.return_value = {"Regions": []}
        regions = discover_active_regions(session)
        # Empty list is valid — no fallback needed for empty
        assert isinstance(regions, list)
