"""Admin customers router — customer management operations."""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from pydantic import BaseModel, EmailStr

from auth.dependencies import AdminContext, get_current_admin
from config import load_config
from services.audit_log import log_action
from services.cfn_template import generate_agent_template
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
    limit: int = Query(50, ge=1, le=500, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
):
    """List customers with pagination (admin only)."""
    db = DynamoDBService()
    all_customers = db.list_customers()
    total = len(all_customers)
    page = all_customers[offset: offset + limit]
    return {"customers": page, "total": total, "limit": limit, "offset": offset}


@router.post("")
async def create_customer(
    http_request: Request,
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

    log_action(
        admin.admin_sub,
        "customer.create",
        customer_id=result["customer_id"],
        details={"name": request.name, "tier": request.subscription_tier},
        ip_address=http_request.client.host if http_request.client else None,
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
    http_request: Request,
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

    log_action(
        admin.admin_sub,
        "customer.update",
        customer_id=customer_id,
        details={"fields_changed": list(updates.keys())},
        ip_address=http_request.client.host if http_request.client else None,
    )

    return {"status": "updated", "customer_id": customer_id}


@router.post("/{customer_id}/rotate-key")
async def rotate_api_key(
    http_request: Request,
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

    log_action(
        admin.admin_sub,
        "customer.rotate_key",
        customer_id=customer_id,
        ip_address=http_request.client.host if http_request.client else None,
    )

    return {
        "customer_id": customer_id,
        "new_api_key": new_key,
        "message": "API key rotated. Old key is now invalid. Save the new key — it won't be shown again.",
    }


@router.get("/{customer_id}/usage")
async def get_customer_usage(
    customer_id: str = Path(...),
    month: str = Query(None, description="Month in YYYY-MM format; defaults to current month"),
    admin: AdminContext = Depends(get_current_admin),
):
    """Return API usage counters for a customer in a given month."""
    from services.usage_meter import get_usage
    record = get_usage(customer_id, month)
    return {"customer_id": customer_id, "usage": record}


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
    template_yaml = generate_agent_template(customer_id, customer.get("name", ""), config)
    filename = f"tek-watch-agent-{customer_id}.yaml"

    return Response(
        content=template_yaml,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
