"""Generates the per-customer CloudFormation template for the self-hosted agent.

Shared by the admin download endpoint and the customer-facing one so both
stay in sync: there is exactly one place that defines what the agent stack
looks like.
"""
import yaml

from config import APIConfig


def _queue_arn(queue_url: str) -> str:
    """arn for an SQS queue url, or a permissive fallback if it is not one.

    A queue url is https://sqs.<region>.amazonaws.com/<account>/<name>, and the
    arn is arn:aws:sqs:<region>:<account>:<name>. Naming the exact queue keeps
    the grant to one resource, and — more to the point — makes it impossible
    for the policy and the queue to disagree about what the queue is called.
    """
    try:
        _, _, host, account, name = queue_url.split("/", 4)
        region = host.split(".")[1]
        return f"arn:aws:sqs:{region}:{account}:{name}"
    except (ValueError, IndexError):
        # Nothing sane to name. Better a broad grant than a template that
        # cannot be generated at all, and the queue policy still gates it.
        return "arn:aws:sqs:*:*:*"


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
                "MinLength": 1,
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
            # A number rather than a free-text schedule, because the agent has
            # to be told the same value: it decides which runs sweep every
            # region or fetch costs, and how long a run may take. Capped at
            # 15 because the silence detector alarms after 20 minutes without
            # a heartbeat. The default was 5, which with a slow run meant nine
            # overlapping tasks and a bill of about $14 a day.
            "RunIntervalMinutes": {
                "Type": "Number",
                "Default": 15,
                "AllowedValues": [5, 10, 15],
                "Description": "How often the agent runs, in minutes",
            },
            # Fargate tasks need awsvpc networking, so the schedule has to know
            # where to place them. Typed as EC2 resource ids so CloudFormation
            # renders them as pick-lists of the customer's own VPC and subnets.
            "VpcId": {
                "Type": "AWS::EC2::VPC::Id",
                "Description": "VPC to run the agent in. The default VPC is fine.",
            },
            "SubnetIds": {
                "Type": "List<AWS::EC2::Subnet::Id>",
                "Description": (
                    "Subnets to run the agent in. Pick public subnets, or private "
                    "ones with a NAT gateway: the agent makes outbound calls only."
                ),
            },
        },
        "Resources": {
            "AgentCluster": {
                "Type": "AWS::ECS::Cluster",
                "Properties": {
                    "ClusterName": f"tek-watch-agent-{customer_id}",
                    "CapacityProviders": ["FARGATE"],
                },
            },
            "AgentTaskRole": {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "RoleName": f"TekWatchAgentRole-{customer_id}",
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
                                # SendMessage also authorises SendMessageBatch;
                                # "sqs:SendMessageBatch" is not an IAM action.
                                "Action": ["sqs:SendMessage"],
                                # The exact queue, derived from the url this
                                # deployment actually publishes to.
                                #
                                # This was the wildcard arn:aws:sqs:*:*:tek-watch-ingest-*,
                                # which matches nothing we own: the queue is
                                # tek-watch-prod-ingest, and that name does not
                                # start with "tek-watch-ingest-". So the agent
                                # collected 163 records without an error and was
                                # then refused at the last step — cross-account
                                # sending needs the queue policy AND the caller's
                                # own identity policy, and this was the second one.
                                "Resource": _queue_arn(config.sqs_ingest_queue_url),
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
                    "RoleName": f"TekWatchAgentExecutionRole-{customer_id}",
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
                    "Policies": [{
                        "PolicyName": "TekWatchReadApiKeySecret",
                        "PolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [{
                                "Effect": "Allow",
                                "Action": "secretsmanager:GetSecretValue",
                                "Resource": {"Ref": "AgentApiKeySecret"},
                            }],
                        },
                    }],
                },
            },
            # Holds the agent's own API key. It used to sit in the task
            # definition's plain Environment array, which meant anyone in this
            # AWS account with ecs:DescribeTaskDefinition — a far more common
            # grant than secretsmanager:GetSecretValue — could read it in
            # plaintext. NoEcho on the APIKey parameter only hides it from
            # stack describe calls; it does nothing once the value has been
            # placed in a resource property. This narrows who can read it to
            # exactly the execution role, which is the only thing that
            # legitimately needs to.
            #
            # The name carries a suffix from the stack's own id, not just the
            # customer id, because Secrets Manager does not delete a secret
            # when its stack is deleted — it schedules deletion 30 days out,
            # and CloudFormation has no property to force it. A customer who
            # uninstalls and reinstalls, which the product explicitly offers
            # as a supported flow, would hit "already scheduled for deletion"
            # on a fixed name for a full month. A name that is unique to this
            # stack's own creation can never collide with a secret an earlier,
            # deleted stack left behind.
            "AgentApiKeySecret": {
                "Type": "AWS::SecretsManager::Secret",
                "Properties": {
                    "Name": {
                        "Fn::Sub": [
                            f"tek-watch-agent-{customer_id}-api-key-${{StackSuffix}}",
                            {"StackSuffix": {"Fn::Select": [2, {"Fn::Split": ["/", {"Ref": "AWS::StackId"}]}]}},
                        ]
                    },
                    "Description": f"Tek Watch agent API key for {customer_id}",
                    "SecretString": {"Ref": "APIKey"},
                },
            },
            "AgentLogGroup": {
                "Type": "AWS::Logs::LogGroup",
                "Properties": {
                    "LogGroupName": f"/ecs/tek-watch-agent-{customer_id}",
                    "RetentionInDays": 7,
                },
            },
            "AgentTaskDefinition": {
                "Type": "AWS::ECS::TaskDefinition",
                "Properties": {
                    "Family": f"tek-watch-agent-{customer_id}",
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
                            {"Name": "LOG_LEVEL", "Value": "INFO"},
                            {"Name": "TEK_WATCH_RUN_INTERVAL_MINUTES", "Value": {"Ref": "RunIntervalMinutes"}},
                        ],
                        # Resolved by the ECS agent at container start, using
                        # the execution role's secretsmanager:GetSecretValue
                        # grant above — never written into the task
                        # definition itself, unlike everything in Environment.
                        "Secrets": [
                            {"Name": "TEK_WATCH_API_KEY", "ValueFrom": {"Ref": "AgentApiKeySecret"}},
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
            # Outbound only. No ingress rule at all, which is what lets us say
            # no inbound firewall changes are needed.
            "AgentSecurityGroup": {
                "Type": "AWS::EC2::SecurityGroup",
                "Properties": {
                    "GroupDescription": "Tek Watch agent: outbound only",
                    "VpcId": {"Ref": "VpcId"},
                    "SecurityGroupEgress": [{
                        "IpProtocol": "-1",
                        "CidrIp": "0.0.0.0/0",
                        "Description": "Reach ECR Public, CloudWatch and the Tek Watch queue",
                    }],
                },
            },
            # EventBridge needs its own role to start the task and to hand the
            # task its roles.
            "AgentSchedulerRole": {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "AssumeRolePolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [{
                            "Effect": "Allow",
                            "Principal": {"Service": "events.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }],
                    },
                    "Policies": [{
                        "PolicyName": "run-agent-task",
                        "PolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "ecs:RunTask",
                                    "Resource": {"Ref": "AgentTaskDefinition"},
                                    "Condition": {
                                        "ArnEquals": {
                                            "ecs:cluster": {"Fn::GetAtt": ["AgentCluster", "Arn"]}
                                        }
                                    },
                                },
                                {
                                    "Effect": "Allow",
                                    "Action": "iam:PassRole",
                                    "Resource": [
                                        {"Fn::GetAtt": ["AgentTaskRole", "Arn"]},
                                        {"Fn::GetAtt": ["AgentExecutionRole", "Arn"]},
                                    ],
                                },
                            ],
                        },
                    }],
                },
            },
            # Without this the stack creates a task definition and nothing that
            # ever runs it. The deploy reported CREATE_COMPLETE, the customer
            # was told to expect data within ten minutes, and none would ever
            # have arrived — a silent failure dressed as a success.
            "AgentSchedule": {
                "Type": "AWS::Events::Rule",
                "Properties": {
                    "Name": f"tek-watch-agent-{customer_id}-schedule",
                    "Description": "Runs the Tek Watch collection agent",
                    "ScheduleExpression": {"Fn::Sub": "rate(${RunIntervalMinutes} minutes)"},
                    "State": "ENABLED",
                    "Targets": [{
                        "Id": "agent-task",
                        "Arn": {"Fn::GetAtt": ["AgentCluster", "Arn"]},
                        "RoleArn": {"Fn::GetAtt": ["AgentSchedulerRole", "Arn"]},
                        "EcsParameters": {
                            "TaskDefinitionArn": {"Ref": "AgentTaskDefinition"},
                            "TaskCount": 1,
                            "LaunchType": "FARGATE",
                            "PlatformVersion": "LATEST",
                            "NetworkConfiguration": {
                                "AwsVpcConfiguration": {
                                    "Subnets": {"Ref": "SubnetIds"},
                                    "SecurityGroups": [
                                        {"Fn::GetAtt": ["AgentSecurityGroup", "GroupId"]}
                                    ],
                                    # Public subnets have no NAT, and the agent
                                    # has to reach ECR Public to start at all.
                                    "AssignPublicIp": "ENABLED",
                                },
                            },
                        },
                    }],
                },
            },
        },
        "Outputs": {
            "CustomerID": {"Value": customer_id, "Description": "Tek Watch Customer ID"},
            "ScheduleName": {
                "Value": {"Ref": "AgentSchedule"},
                "Description": "EventBridge rule that runs the agent",
            },
            "ClusterName": {"Value": {"Ref": "AgentCluster"}, "Description": "ECS Cluster"},
        },
    }

    return yaml.dump(template, default_flow_style=False, sort_keys=False)
