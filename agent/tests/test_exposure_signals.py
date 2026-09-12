"""The signals the incident engine needs to spot an exposure.

A database with a public endpoint looked exactly like a private one, because
nothing collected the flag, and a database being modified was not treated as
high risk, so no cause could be found for it either.
"""
import pytest
from unittest.mock import MagicMock

from collectors.cloudtrail import HIGH_RISK_EVENTS
from collectors.rds import RDSCollector


def make_db_instance(public=None, db_id="prod-db"):
    db = {
        "DBInstanceIdentifier": db_id,
        "Engine": "postgres",
        "EngineVersion": "15.3",
        "DBInstanceStatus": "available",
        "DBInstanceClass": "db.t3.medium",
        "MultiAZ": True,
        "AvailabilityZone": "eu-west-1a",
        "AllocatedStorage": 100,
    }
    if public is not None:
        db["PubliclyAccessible"] = public
    return db


@pytest.fixture
def collector():
    session = MagicMock()
    rds_client, cw_client = MagicMock(), MagicMock()
    session.client.side_effect = lambda svc, **kw: rds_client if svc == "rds" else cw_client
    # No CloudWatch datapoints: this file is about the inventory record, and an
    # unstubbed mock is not an empty list.
    cw_client.get_metric_statistics.return_value = {"Datapoints": []}
    c = RDSCollector(session, "eu-west-1", "TT-0001")
    c._rds = rds_client
    c._cw = cw_client
    return c, rds_client


def inventory_record(records):
    return next(r for r in records if r.metric_name == "db_instance_status")


class TestPubliclyAccessibleFlag:
    def test_public_database_is_reported_as_public(self, collector):
        c, rds = collector
        rds.get_paginator.return_value.paginate.return_value = [
            {"DBInstances": [make_db_instance(public=True)]}
        ]
        assert inventory_record(c.collect()).dimensions["publicly_accessible"] == "True"

    def test_private_database_is_reported_as_private(self, collector):
        c, rds = collector
        rds.get_paginator.return_value.paginate.return_value = [
            {"DBInstances": [make_db_instance(public=False)]}
        ]
        assert inventory_record(c.collect()).dimensions["publicly_accessible"] == "False"

    def test_missing_field_is_not_reported_as_public(self, collector):
        c, rds = collector
        rds.get_paginator.return_value.paginate.return_value = [
            {"DBInstances": [make_db_instance()]}
        ]
        assert inventory_record(c.collect()).dimensions["publicly_accessible"] == "False"


class TestDatabaseChangesAreHighRisk:
    @pytest.mark.parametrize("name", ["ModifyDBInstance", "CreateDBInstance"])
    def test_event_is_watched(self, name):
        assert name in HIGH_RISK_EVENTS

    def test_security_group_changes_are_still_watched(self):
        # The other half of how a database becomes reachable.
        assert "AuthorizeSecurityGroupIngress" in HIGH_RISK_EVENTS
