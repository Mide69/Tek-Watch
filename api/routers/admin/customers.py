"""Admin customers router — customer management operations."""
import logging
from typing import List

import yaml
from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from pydantic import BaseModel, EmailStr

from auth.dependencies import AdminContext, get_current_admin
from config import load_config
from services.dynamodb import DynamoDBService

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateCustomerRequest(BaseModel):
    """Request model for creating a new customer."""
    name: str
    email: EmailStr
    subscription_tier: str
    aws_account_ids: List[str]


class UpdateCustomerRequest(BaseModel):
    """Request model for updating a customer."""
    name: str | None = None
    email: EmailStr | None = None
    subscription_tier: str | None = None
    aws_account_ids: List[str] | None = None
    status: str | None = None


@router.get("")
async def list_customers(
    admin: AdminContext = Depends(get_current_admin),
):
    """List all customers (admin only)."""
    db = DynamoDBService()
    customers = db.list_customers()
    return {"customers": customers}


@router.post("")
async def create_customer(
    request: CreateCustomerRequest,
    admin: AdminContext = Depends(get_current_admin),
):
    """Create a new customer account."""
    db = DynamoDBService()
    
    result = db.create_customer(
        name=request.name,
        email=request.email,
        subscription_tier=request.subscription_tier,
        aws_account_ids=request.aws_account_ids,
    )
    
    return {
        "customer_id": result["customer_id"],
        "api_key": result["api_key"],
        "message": "Customer created successfully. Save the API key — it won't be shown again.",
        "profile": result["profile"],
    }


@router.get("/{customer_id}")
async def get_customer(
    customer_id: str = Path(...),
    admin: AdminContext = Depends(get_current_admin),
):
    """Get customer details."""
    db = DynamoDBService()
    customer = db.get_customer(customer_id)
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found",
        )
    
    return {"customer": customer}


@router.put("/{customer_id}")
async def update_customer(
    request: UpdateCustomerRequest,
    customer_id: str = Path(...),
    admin: AdminContext = Depends(get_current_admin),
):
    """Update customer details."""
    db = DynamoDBService()
    
    updates = request.model_dump(exclude_none=True)
    success = db.update_customer(customer_id, updates)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found or update failed",
        )
    
    return {"status": "updated", "customer_id": customer_id}


@router.post("/{customer_id}/rotate-key")
async def rotate_api_key(
    customer_id: str = Path(...),
    admin: AdminContext = Depends(get_current_admin),
):
    """Rotate customer API key."""
    db = DynamoDBService()
    new_key = db.rotate_api_key(customer_id)
    
    if not new_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found",
        )
    
    return {
        "customer_id": customer_id,
        "new_api_key": new_key,
        "message": "API key rotated. Old key is now invalid. Save the new key — it won't be shown again.",
    }


@router.get("/{customer_id}/cfn-template")
async def download_cloudformation_template(
    customer_id: str = Path(...),
    admin: AdminContext = Depends(get_current_admin),
):
    """Download pre-filled CloudFormation template for customer agent deployment."""
    db = DynamoDBService()
    customer = db.get_customer(customer_id)

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found",
        )

    config = load_config()

    # Build the CloudFormation template as a dict and serialise to YAML
    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": f"Tribe Watch Agent — {customer_id} ({customer.get('name', '')})",
        "Parameters": {
            "CustomerID": {
                "Type": "String",
                "Default": customer_id,
                "Description": "Tribe Watch Customer ID",
            },
            "IngestQueueURL": {
                "Type": "String",
                "Default": config.sqs_ingest_queue_url,
                "Description": "Tribe Watch SQS ingest queue URL",
            },
            "APIKey": {
                "Type": "String",
                "NoEcho": True,
                "Description": "Tribe Watch API key — enter the value provided by your admin",
            },
            "AgentImageURI": {
                "Type": "String",
                "Default": "123456789012.dkr.ecr.eu-west-2.amazonaws.com/tribe-watch-agent:latest",
                "Description": "Tribe Watch agent Docker image URI",
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
                    "ClusterName": {"Fn::Sub": f"tribe-watch-agent-{customer_id}"},
                    "CapacityProviders": ["FARGATE"],
                },
            },
            "AgentTaskRole": {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "RoleName": {"Fn::Sub": f"TribeWatchAgentRole-{customer_id}"},
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
                        "PolicyName": "TribeWatchSQSSend",
                        "PolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [{
                                "Effect": "Allow",
                                "Action": ["sqs:SendMessage", "sqs:SendMessageBatch"],
                                "Resource": {"Fn::Sub": "arn:aws:sqs:*:*:tribe-watch-ingest-*"},
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
                    "RoleName": {"Fn::Sub": f"TribeWatchAgentExecutionRole-{customer_id}"},
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
                    "LogGroupName": {"Fn::Sub": f"/ecs/tribe-watch-agent-{customer_id}"},
                    "RetentionInDays": 7,
                },
            },
            "AgentTaskDefinition": {
                "Type": "AWS::ECS::TaskDefinition",
                "Properties": {
                    "Family": {"Fn::Sub": f"tribe-watch-agent-{customer_id}"},
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
                            {"Name": "TRIBE_WATCH_CUSTOMER_ID", "Value": {"Ref": "CustomerID"}},
                            {"Name": "TRIBE_WATCH_INGEST_QUEUE_URL", "Value": {"Ref": "IngestQueueURL"}},
                            {"Name": "TRIBE_WATCH_API_KEY", "Value": {"Ref": "APIKey"}},
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
            "CustomerID": {"Value": customer_id, "Description": "Tribe Watch Customer ID"},
            "ClusterName": {"Value": {"Ref": "AgentCluster"}, "Description": "ECS Cluster"},
        },
    }

    template_yaml = yaml.dump(template, default_flow_style=False, sort_keys=False)
    filename = f"tribe-watch-agent-{customer_id}.yaml"

    return Response(
        content=template_yaml,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
