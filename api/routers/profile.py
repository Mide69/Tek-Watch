"""
Profile router — the customer's own company profile.

GET    /api/v1/profile        Company details plus a short-lived logo url
PUT    /api/v1/profile        Update company details
POST   /api/v1/profile/logo   Upload a company logo
DELETE /api/v1/profile/logo   Remove the company logo

The dashboard used to have nothing to show but the raw Customer ID, because
the signup form's "company" field was collected and then dropped on the floor.
These endpoints give a customer somewhere to put their real details, and give
every page a human name to display.
"""
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, field_validator

from auth.dependencies import CustomerContext, get_current_customer
from config import load_config
from services.dynamodb import DynamoDBService

logger = logging.getLogger(__name__)

router = APIRouter()

# Fields a customer may set on their own profile. Deliberately excludes
# subscription_tier, status and aws_account_ids: those are ours to set, and
# update_customer would happily accept them if they were listed here.
PROFILE_FIELDS = (
    "company_name", "name", "phone", "website",
    "address_line1", "address_line2", "city", "postcode", "country",
)

LOGO_MAX_BYTES = 2 * 1024 * 1024  # 2 MB

# Sniffed from the file's own bytes rather than trusted from the request.
# A browser-supplied Content-Type is just a claim, and "image/png" on a file
# that is actually HTML is the standard way to get stored XSS out of an upload
# endpoint. SVG is excluded on purpose — it is a document format that can carry
# script, not a safe raster image.
LOGO_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
)
LOGO_URL_TTL_SECONDS = 3600


class ProfileUpdate(BaseModel):
    """Every field optional — the form saves whatever the customer filled in."""

    company_name: Optional[str] = Field(default=None, max_length=200)
    name: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=40)
    website: Optional[str] = Field(default=None, max_length=200)
    address_line1: Optional[str] = Field(default=None, max_length=200)
    address_line2: Optional[str] = Field(default=None, max_length=200)
    city: Optional[str] = Field(default=None, max_length=100)
    postcode: Optional[str] = Field(default=None, max_length=20)
    country: Optional[str] = Field(default=None, max_length=100)

    @field_validator("*")
    @classmethod
    def _strip(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if isinstance(value, str) else value

    @field_validator("website")
    @classmethod
    def _check_website(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        # Rendered as a link in the dashboard, so anything that is not plain
        # http(s) — javascript:, data: — must not survive to the database.
        if value.startswith(("http://", "https://")):
            return value
        if ":" in value.split("/", 1)[0]:
            raise ValueError("Website must be an http or https address")
        return f"https://{value}"


def _s3():
    config = load_config()
    return boto3.client("s3", region_name=config.aws_region), config


def _logo_url(logo_key: str) -> str:
    """Presigned GET for a logo. Empty string when there is nothing to show.

    The bucket stays private: a customer's logo is their material, and a public
    bucket would make every customer's branding enumerable.
    """
    if not logo_key:
        return ""
    client, config = _s3()
    if not config.s3_uploads_bucket:
        return ""
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": config.s3_uploads_bucket, "Key": logo_key},
            ExpiresIn=LOGO_URL_TTL_SECONDS,
        )
    except ClientError as exc:
        logger.warning("Could not presign logo %s: %s", logo_key, exc)
        return ""


def _shape(profile: dict) -> dict:
    """Return only what the dashboard needs — never api_key_hash."""
    return {
        "customer_id": profile.get("customer_id", ""),
        "company_name": profile.get("company_name", "") or "",
        "name": profile.get("name", "") or "",
        "email": profile.get("email", "") or "",
        "phone": profile.get("phone", "") or "",
        "website": profile.get("website", "") or "",
        "address_line1": profile.get("address_line1", "") or "",
        "address_line2": profile.get("address_line2", "") or "",
        "city": profile.get("city", "") or "",
        "postcode": profile.get("postcode", "") or "",
        "country": profile.get("country", "") or "",
        "subscription_tier": profile.get("subscription_tier", "") or "",
        "logo_url": _logo_url(profile.get("logo_key", "") or ""),
        # What the dashboard should print in place of the Customer ID.
        "display_name": (
            profile.get("company_name")
            or profile.get("name")
            or profile.get("customer_id", "")
        ),
    }


def _load(customer_id: str) -> dict:
    profile = DynamoDBService().get_customer(customer_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer profile not found",
        )
    return profile


@router.get("")
@router.get("/")
async def get_profile(customer: CustomerContext = Depends(get_current_customer)):
    """Get the signed-in customer's company profile."""
    return _shape(_load(customer.customer_id))


@router.put("")
@router.put("/")
async def update_profile(
    body: ProfileUpdate,
    customer: CustomerContext = Depends(get_current_customer),
):
    """Update the signed-in customer's company profile."""
    updates = {
        field: value
        for field, value in body.model_dump(exclude_unset=True).items()
        if field in PROFILE_FIELDS and value is not None
    }
    if not updates:
        return _shape(_load(customer.customer_id))

    if not DynamoDBService().update_customer(customer.customer_id, updates):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save your profile. Please try again.",
        )
    return _shape(_load(customer.customer_id))


@router.post("/logo")
async def upload_logo(
    file: UploadFile = File(...),
    customer: CustomerContext = Depends(get_current_customer),
):
    """Upload a company logo (PNG, JPEG or GIF, up to 2 MB)."""
    client, config = _s3()
    if not config.s3_uploads_bucket:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Logo uploads are not configured on this environment.",
        )

    # Read with a cap rather than trusting the Content-Length header, which the
    # client controls. Reading one byte past the limit is what tells us the file
    # is too big without holding an unbounded amount in memory.
    payload = await file.read(LOGO_MAX_BYTES + 1)
    if len(payload) > LOGO_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="That logo is larger than 2 MB. Please upload a smaller image.",
        )
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That file is empty.",
        )

    content_type = extension = None
    for signature, sniffed_type, sniffed_ext in LOGO_SIGNATURES:
        if payload.startswith(signature):
            content_type, extension = sniffed_type, sniffed_ext
            break
    if not content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload a PNG, JPEG or GIF image.",
        )

    # Keyed by customer id, so one customer can never write over another's logo
    # — the id comes from the verified token, never from the request body.
    key = f"logos/{customer.customer_id}/logo.{extension}"
    try:
        client.put_object(
            Bucket=config.s3_uploads_bucket,
            Key=key,
            Body=payload,
            ContentType=content_type,
            ContentDisposition="inline",
            CacheControl="private, max-age=300",
        )
    except ClientError as exc:
        logger.error("Logo upload failed for %s: %s", customer.customer_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not store the logo. Please try again.",
        ) from exc

    if not DynamoDBService().update_customer(customer.customer_id, {"logo_key": key}):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logo uploaded but could not be linked to your profile.",
        )

    return _shape(_load(customer.customer_id))


@router.delete("/logo")
async def delete_logo(customer: CustomerContext = Depends(get_current_customer)):
    """Remove the company logo."""
    profile = _load(customer.customer_id)
    key = profile.get("logo_key", "")
    db = DynamoDBService()

    # Clear the reference first. If the S3 delete fails the customer still sees
    # the logo gone, which is what they asked for; an orphaned object is a
    # tidiness problem, not a correctness one.
    db.update_customer(customer.customer_id, {"logo_key": ""})

    if key:
        client, config = _s3()
        if config.s3_uploads_bucket:
            try:
                client.delete_object(Bucket=config.s3_uploads_bucket, Key=key)
            except ClientError as exc:
                logger.warning("Could not delete logo object %s: %s", key, exc)

    return _shape(_load(customer.customer_id))
