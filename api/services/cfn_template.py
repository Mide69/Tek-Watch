"""Generates the per-customer CloudFormation template for the self-hosted agent.

Shared by the admin download endpoint and the customer-facing one so both
stay in sync: there is exactly one place that defines what the agent stack
looks like.
"""
import yaml

from config import APIConfig


def generate_agent_template(
    customer_id: str,
    customer_name: str,
    config: APIConfig,
    api_key: str = "",
) -> str:
    """Build the CloudFormation template as YAML for a customer's agent deployment."""
    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": f"Tek Watch Agent: {customer_id} ({customer_name})",
        "Parameters": {
            "CustomerID": {
                "Type": "String",
                "Default": customer_id,
                "Description": "Tek Watch Customer ID",
            },
            "IngestQueueURL": {
                "Type": "String",
                "Default": config.sqs_ingest_queue_url,
                "Description": "Tek Watch SQS ingest queue URL",
            },
            "APIKey": {
                "Type": "String",
                "NoEcho": True,
                # Filled in when the key is being issued to this customer, which
                # is the only moment it exists in plaintext. Otherwise left blank
                # and they paste the one they saved. It used to say "provided by
                # your admin", and there was no way for an admin to provide it
                # short of rotating the key by hand.
                **({"Default": api_key} if api_key else {}),
                "Description": (
                    "Tek Watch agent key. Already filled in if this template was "
                    "downloaded with a new key, otherwise paste the key you saved."
                ),
            },
            "AgentImageURI": {
                "Type": "String",
                # Was hardcoded to 123456789012, a documentation placeholder.
                # Every customer stack that reached the pull step failed on it.
                "Default": config.agent_public_image_uri,
                "Description": "Tek Watch agent image (public, no credentials needed)",
            },
            "ScheduleExpression": {
                "Type": "String",
                "Default": "rate(5 minutes)",
                "Description": "How often the agent runs",
            },
        },
        "Resources": {
            "AgentCluster": {
                "Type": "AWS::ECS::Cluster",
                "Properties": {
                    "ClusterName": {"Fn::Sub": f"tek-watch-agent-{customer_id}"},
                    "CapacityProviders": ["FARGATE"],
                },
            },
            "AgentTaskRole": {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "RoleName": {"Fn::Sub": f"TekWatchAgentRole-{customer_id}"},
                    "AssumeRolePolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [{
                            "Effect": "Allow",
                            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }],
                    },
                    "ManagedPolicyArns": ["arn:aws:iam::aws:policy/ReadOnlyAccess"],
                    "Policies": [{
                        "PolicyName": "TekWatchSQSSend",
                        "PolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [{
                                "Effect": "Allow",
                                "Action": ["sqs:SendMessage", "sqs:SendMessageBatch"],
                                "Resource": {"Fn::Sub": "arn:aws:sqs:*:*:tek-watch-ingest-*"},
                            }, {
                                "Effect": "Allow",
                                "Action": ["ce:GetCostAndUsage", "ce:GetCostForecast"],
                                "Resource": "*",
                            }],
                        },
                    }],
                },
            },
            "AgentExecutionRole": {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "RoleName": {"Fn::Sub": f"TekWatchAgentExecutionRole-{customer_id}"},
                    "AssumeRolePolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [{
                            "Effect": "Allow",
                            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }],
                    },
                    "ManagedPolicyArns": [
                        "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
                    ],
                },
            },
            "AgentLogGroup": {
                "Type": "AWS::Logs::LogGroup",
                "Properties": {
                    "LogGroupName": {"Fn::Sub": f"/ecs/tek-watch-agent-{customer_id}"},
                    "RetentionInDays": 7,
                },
            },
            "AgentTaskDefinition": {
                "Type": "AWS::ECS::TaskDefinition",
                "Properties": {
                    "Family": {"Fn::Sub": f"tek-watch-agent-{customer_id}"},
                    "NetworkMode": "awsvpc",
                    "RequiresCompatibilities": ["FARGATE"],
                    "Cpu": "512",
                    "Memory": "1024",
                    "TaskRoleArn": {"Fn::GetAtt": ["AgentTaskRole", "Arn"]},
                    "ExecutionRoleArn": {"Fn::GetAtt": ["AgentExecutionRole", "Arn"]},
                    "ContainerDefinitions": [{
                        "Name": "agent",
                        "Image": {"Ref": "AgentImageURI"},
                        "Essential": True,
                        "Environment": [
                            {"Name": "TEK_WATCH_CUSTOMER_ID", "Value": {"Ref": "CustomerID"}},
                            {"Name": "TEK_WATCH_INGEST_QUEUE_URL", "Value": {"Ref": "IngestQueueURL"}},
                            {"Name": "TEK_WATCH_API_KEY", "Value": {"Ref": "APIKey"}},
                            {"Name": "LOG_LEVEL", "Value": "INFO"},
                        ],
                        "LogConfiguration": {
                            "LogDriver": "awslogs",
                            "Options": {
                                "awslogs-group": {"Ref": "AgentLogGroup"},
                                "awslogs-region": {"Ref": "AWS::Region"},
                                "awslogs-stream-prefix": "agent",
                            },
                        },
                    }],
                },
            },
        },
        "Outputs": {
            "CustomerID": {"Value": customer_id, "Description": "Tek Watch Customer ID"},
            "ClusterName": {"Value": {"Ref": "AgentCluster"}, "Description": "ECS Cluster"},
        },
    }

    return yaml.dump(template, default_flow_style=False, sort_keys=False)
