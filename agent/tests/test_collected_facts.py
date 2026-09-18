"""Facts the compliance checks and the dependency graph need.

Two rules are tested everywhere here:

* a fact that was read is reported, so a control can decide
* a fact that could not be read is left out entirely, so a control says
  "unknown" instead of quietly passing or failing a customer on a guess
"""
from unittest.mock import MagicMock

import pytest

from collectors.cloudfront import CloudFrontCollector
from collectors.dynamodb import DynamoDBCollector
from collectors.ec2 import EC2Collector
from collectors.eks import EKSCollector
from collectors.elasticache import ElastiCacheCollector
from collectors.lambda_ import LambdaCollector
from collectors.rds import RDSCollector
from collectors.sns import SNSCollector
from collectors.sqs import SQSCollector

NO_POINTS = {"Datapoints": []}


def dims(records, metric_name):
    return next(r for r in records if r.metric_name == metric_name).dimensions


def collector(cls, service, client):
    session = MagicMock()
    cw = MagicMock()
    cw.get_metric_statistics.return_value = NO_POINTS
    session.client.side_effect = lambda svc, **kw: client if svc == service else cw
    c = cls(session, "eu-west-2", "TT-0001")
    for attr in ("_ec2", "_lambda", "_rds", "_cf", "_eks", "_ec", "_ddb", "_sns", "_sqs"):
        if hasattr(c, attr) and not isinstance(getattr(c, attr), MagicMock):
            continue
    return c, client, cw


class TestEc2SecurityGroups:
    def _run(self, instance):
        c, ec2, _ = collector(EC2Collector, "ec2", MagicMock())
        c._ec2 = ec2
        ec2.get_paginator.return_value.paginate.return_value = [
            {"Reservations": [{"Instances": [instance]}]}
        ]
        return dims(c.collect(), "instance_state")

    def test_groups_are_reported(self):
        d = self._run({"InstanceId": "i-1", "State": {"Name": "running"},
                       "SecurityGroups": [{"GroupId": "sg-a"}, {"GroupId": "sg-b"}]})
        assert d["security_groups"] == "sg-a,sg-b"

    def test_an_instance_without_groups_reports_none(self):
        d = self._run({"InstanceId": "i-1", "State": {"Name": "running"}})
        assert "security_groups" not in d


class TestLambdaPlacement:
    def _run(self, fn):
        c, lam, _ = collector(LambdaCollector, "lambda", MagicMock())
        c._lambda = lam
        lam.get_paginator.return_value.paginate.return_value = [{"Functions": [fn]}]
        return dims(c.collect(), "function_runtime")

    def test_a_function_in_a_vpc_reports_where(self):
        d = self._run({"FunctionName": "api", "Runtime": "python3.12",
                       "VpcConfig": {"VpcId": "vpc-1", "SubnetIds": ["sub-a"],
                                     "SecurityGroupIds": ["sg-a"]}})
        assert (d["vpc_id"], d["subnet_ids"], d["security_groups"]) == ("vpc-1", "sub-a", "sg-a")

    def test_a_function_outside_a_vpc_says_nothing(self):
        d = self._run({"FunctionName": "api", "Runtime": "python3.12", "VpcConfig": {}})
        assert "vpc_id" not in d and "security_groups" not in d


class TestRdsPlacement:
    def _run(self, db):
        c, rds, cw = collector(RDSCollector, "rds", MagicMock())
        c._rds, c._cw = rds, cw
        rds.get_paginator.return_value.paginate.return_value = [{"DBInstances": [db]}]
        return dims(c.collect(), "db_instance_status")

    def test_vpc_and_groups_are_reported(self):
        d = self._run({"DBInstanceIdentifier": "prod", "Engine": "postgres",
                       "DBSubnetGroup": {"VpcId": "vpc-1"},
                       "VpcSecurityGroups": [{"VpcSecurityGroupId": "sg-db"}]})
        assert d["vpc_id"] == "vpc-1" and d["security_groups"] == "sg-db"

    def test_backup_retention_is_reported(self):
        d = self._run({"DBInstanceIdentifier": "prod", "Engine": "postgres",
                       "BackupRetentionPeriod": 7})
        assert d["backup_retention_days"] == 7


class TestCloudFrontOrigins:
    def _run(self, dist):
        c, cf, cw = collector(CloudFrontCollector, "cloudfront", MagicMock())
        c._cf, c._cw = cf, cw
        cf.get_paginator.return_value.paginate.return_value = [
            {"DistributionList": {"Items": [dist]}}
        ]
        return dims(c.collect(), "distribution_status")

    def test_origins_are_reported_so_the_graph_can_join_them_to_buckets(self):
        d = self._run({"Id": "E1", "DomainName": "d1.cloudfront.net", "Status": "Deployed",
                       "Origins": {"Items": [{"DomainName": "assets.s3.eu-west-2.amazonaws.com"}]},
                       "DefaultCacheBehavior": {"ViewerProtocolPolicy": "redirect-to-https"}})
        assert d["origins"] == "assets.s3.eu-west-2.amazonaws.com"
        assert d["viewer_protocol_policy"] == "redirect-to-https"

    def test_a_distribution_with_no_readable_origins_says_nothing(self):
        d = self._run({"Id": "E1", "DomainName": "d1.cloudfront.net", "Status": "Deployed"})
        assert "origins" not in d and "viewer_protocol_policy" not in d


class TestEksEndpoint:
    def _run(self, cluster):
        c, eks, cw = collector(EKSCollector, "eks", MagicMock())
        c._eks, c._cw = eks, cw
        eks.get_paginator.return_value.paginate.return_value = [{"clusters": ["prod"]}]
        eks.describe_cluster.return_value = {"cluster": cluster}
        eks.list_nodegroups.side_effect = Exception("not needed")
        return dims(c.collect(), "cluster_status")

    @pytest.mark.parametrize("public,expected", [(True, "True"), (False, "False")])
    def test_public_api_access_is_reported(self, public, expected):
        d = self._run({"status": "ACTIVE", "version": "1.30",
                       "resourcesVpcConfig": {"endpointPublicAccess": public, "vpcId": "vpc-1"}})
        assert d["endpoint_public_access"] == expected
        assert d["vpc_id"] == "vpc-1"

    def test_an_unreadable_endpoint_setting_is_left_out(self):
        d = self._run({"status": "ACTIVE", "version": "1.30"})
        assert "endpoint_public_access" not in d


class TestElastiCacheEncryption:
    def _run(self, cluster):
        c, ec, cw = collector(ElastiCacheCollector, "elasticache", MagicMock())
        c._ec, c._cw = ec, cw
        ec.get_paginator.return_value.paginate.return_value = [{"CacheClusters": [cluster]}]
        return dims(c.collect(), "cluster_status")

    def test_both_kinds_of_encryption_are_reported(self):
        d = self._run({"CacheClusterId": "cache-1", "Engine": "redis",
                       "CacheClusterStatus": "available",
                       "AtRestEncryptionEnabled": True, "TransitEncryptionEnabled": False})
        assert d["at_rest_encryption"] == "True"
        assert d["transit_encryption"] == "False"

    def test_missing_flags_are_left_out(self):
        d = self._run({"CacheClusterId": "cache-1", "Engine": "redis",
                       "CacheClusterStatus": "available"})
        assert "at_rest_encryption" not in d


class TestDynamoDbRecovery:
    def _run(self, table, backups=None, raises=False):
        c, ddb, cw = collector(DynamoDBCollector, "dynamodb", MagicMock())
        c._ddb, c._cw = ddb, cw
        ddb.get_paginator.return_value.paginate.return_value = [{"TableNames": ["orders"]}]
        ddb.describe_table.return_value = {"Table": table}
        if raises:
            from botocore.exceptions import ClientError
            ddb.describe_continuous_backups.side_effect = ClientError(
                {"Error": {"Code": "AccessDeniedException"}}, "DescribeContinuousBackups")
        else:
            ddb.describe_continuous_backups.return_value = backups or {}
        return dims(c.collect(), "table_status")

    def test_point_in_time_recovery_on(self):
        d = self._run({"TableName": "orders", "TableStatus": "ACTIVE"},
                      backups={"ContinuousBackupsDescription": {
                          "PointInTimeRecoveryDescription": {"PointInTimeRecoveryStatus": "ENABLED"}}})
        assert d["point_in_time_recovery"] == "True"

    def test_point_in_time_recovery_off(self):
        d = self._run({"TableName": "orders", "TableStatus": "ACTIVE"},
                      backups={"ContinuousBackupsDescription": {
                          "PointInTimeRecoveryDescription": {"PointInTimeRecoveryStatus": "DISABLED"}}})
        assert d["point_in_time_recovery"] == "False"

    def test_no_permission_is_not_reported_as_off(self):
        # Being unable to look is different from looking and finding nothing.
        d = self._run({"TableName": "orders", "TableStatus": "ACTIVE"}, raises=True)
        assert "point_in_time_recovery" not in d

    def test_encryption_status_is_reported_when_present(self):
        d = self._run({"TableName": "orders", "TableStatus": "ACTIVE",
                       "SSEDescription": {"Status": "ENABLED"}})
        assert d["encryption_status"] == "ENABLED"


class TestQueueAndTopicEncryption:
    def _queue(self, attrs):
        c, sqs, _ = collector(SQSCollector, "sqs", MagicMock())
        c._sqs = sqs
        sqs.list_queues.return_value = {"QueueUrls": ["https://sqs/q/orders"]}
        sqs.get_queue_attributes.return_value = {"Attributes": {
            "QueueArn": "arn:aws:sqs:eu-west-2:1:orders",
            "ApproximateNumberOfMessages": "3", **attrs}}
        return dims(c.collect(), "approximate_number_of_messages_visible")

    def test_a_kms_key_counts_as_encrypted(self):
        assert self._queue({"KmsMasterKeyId": "alias/aws/sqs"})["encryption_enabled"] == "True"

    def test_sqs_managed_encryption_counts_too(self):
        assert self._queue({"SqsManagedSseEnabled": "true"})["encryption_enabled"] == "True"

    def test_neither_means_not_encrypted(self):
        assert self._queue({"SqsManagedSseEnabled": "false"})["encryption_enabled"] == "False"

    def test_an_unreadable_setting_is_left_out(self):
        assert "encryption_enabled" not in self._queue({})

    def test_topic_encryption_is_reported(self):
        c, sns, cw = collector(SNSCollector, "sns", MagicMock())
        c._sns, c._cw = sns, cw
        sns.get_paginator.return_value.paginate.return_value = [
            {"Topics": [{"TopicArn": "arn:aws:sns:eu-west-2:1:alerts"}]}
        ]
        sns.get_topic_attributes.return_value = {
            "Attributes": {"SubscriptionsConfirmed": "2", "KmsMasterKeyId": "alias/aws/sns"}}
        assert dims(c.collect(), "topic_state")["encryption_enabled"] == "True"
