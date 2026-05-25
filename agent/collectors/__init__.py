"""Tribe Watch agent collectors package."""
from collectors.acm import ACMCollector
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

__all__ = [
    "ACMCollector",
    "CloudFrontCollector",
    "CloudTrailCollector",
    "CloudWatchAlarmsCollector",
    "ConfigServiceCollector",
    "CostExplorerCollector",
    "DynamoDBCollector",
    "EC2Collector",
    "ECSCollector",
    "EKSCollector",
    "ElastiCacheCollector",
    "ELBCollector",
    "GuardDutyCollector",
    "IAMCollector",
    "LambdaCollector",
    "RDSCollector",
    "Route53Collector",
    "S3Collector",
    "SecurityHubCollector",
    "SNSCollector",
    "SQSCollector",
    "TrustedAdvisorCollector",
    "VPCCollector",
]
