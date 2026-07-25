"""Public self-service signup: no authentication required.

Backend-mediated by design: the customer Cognito pool stays
AllowAdminCreateUserOnly=true (see modules/cognito/main.tf), and this
endpoint does the equivalent of an admin creating the customer, triggered
by the customer themselves instead of a human. Keeps all validation, rate
limiting, and abuse prevention in application code rather than opening a
public Cognito signup surface.
"""
import logging

from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from config import load_config
from rate_limit import limiter
from services.cognito_admin import generate_password, provision_customer_login
from services.dynamodb import DynamoDBService
from services.notifications import NotificationService

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_SIGNUP_TIER = "starter"


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    company: str | None = Field(default=None, max_length=200)


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def signup(request: Request, body: SignupRequest):
    """Create a customer account and Cognito login, then email the credentials
    and next steps. Returns only the Customer ID; the password is emailed,
    never returned in the API response."""
    db = DynamoDBService()
    config = load_config()

    existing = db.list_customers()
    if any(c.get("email", "").lower() == body.email.lower() for c in existing):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account already exists for this email address. Try signing in, "
                   "or use the forgot-password link if you don't remember your details.",
        )

    result = db.create_customer(
        name=body.name,
        email=body.email,
        subscription_tier=DEFAULT_SIGNUP_TIER,
        aws_account_ids=[],
    )
    customer_id = result["customer_id"]

    if not config.cognito_customer_user_pool_id:
        # Local/dev fallback, no live Cognito pool to provision against.
        logger.warning(
            "No Cognito customer pool configured, created %s without a login. "
            "This should only happen outside prod/staging.",
            customer_id,
        )
        return {"customer_id": customer_id, "message": "Account created (dev mode, no email sent)."}

    password = generate_password()
    try:
        provision_customer_login(
            user_pool_id=config.cognito_customer_user_pool_id,
            region=config.aws_region,
            customer_id=customer_id,
            email=body.email,
            password=password,
        )
    except ClientError as exc:
        logger.error("Cognito provisioning failed for %s, rolling back: %s", customer_id, exc)
        db.delete_customer(customer_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create your account right now. Please try again shortly.",
        ) from exc

    notifications = NotificationService()
    await notifications.send_customer_email(
        to_address=body.email,
        subject="Welcome to TekWatch: your account is ready",
        text_body=_welcome_email_text(customer_id, password, body.name),
        html_body=_welcome_email_html(customer_id, password, body.name),
    )

    logger.info("Self-service signup complete: %s (%s)", customer_id, body.email)

    return {
        "customer_id": customer_id,
        "message": "Account created. Check your email for your login details.",
    }


def _welcome_email_text(customer_id: str, password: str, name: str) -> str:
    return (
        f"Hi {name},\n\n"
        f"Your TekWatch account is ready.\n\n"
        f"Customer ID: {customer_id}\n"
        f"Password: {password}\n\n"
        f"Sign in at https://app.tekwatch.io/login\n\n"
        f"Once you're in, head to the Agent page to download your CloudFormation "
        f"template and deploy the read-only monitoring agent into your AWS account. "
        f"It takes about 30 minutes and needs no inbound firewall changes.\n\n"
        f"Want to change your password? Use the forgot-password link on the sign-in page.\n\n"
        f"Questions? Just reply to this email or reach us at hello@tekwatch.co.uk.\n\n"
        f"The TekWatch team\n"
    )


def _welcome_email_html(customer_id: str, password: str, name: str) -> str:
    return f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="background: #4f46e5; padding: 16px 24px; border-radius: 8px 8px 0 0;">
        <h2 style="color: white; margin: 0; font-size: 18px;">Your TekWatch account is ready</h2>
      </div>
      <div style="background: #f9fafb; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
        <p>Hi {name},</p>
        <p>Here are your sign-in details:</p>
        <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
          <tr><td style="padding: 6px 0; color: #6b7280; width: 120px;">Customer ID</td><td style="padding: 6px 0; font-weight: 600; font-family: monospace;">{customer_id}</td></tr>
          <tr><td style="padding: 6px 0; color: #6b7280;">Password</td><td style="padding: 6px 0; font-weight: 600; font-family: monospace;">{password}</td></tr>
        </table>
        <div style="margin: 20px 0;">
          <a href="https://app.tekwatch.io/login" style="background: #4f46e5; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600;">
            Sign in
          </a>
        </div>
        <p>Once you're in, head to the Agent page to download your CloudFormation template and deploy the read-only monitoring agent into your AWS account. It takes about 30 minutes and needs no inbound firewall changes.</p>
        <p>Want to change your password? Use the forgot-password link on the sign-in page.</p>
        <p style="margin-top: 20px; font-size: 12px; color: #9ca3af;">
          Questions? Reply to this email or reach us at hello@tekwatch.co.uk.<br>
          Sent by TekWatch, powered by Tek Tribe Ltd.
        </p>
      </div>
    </div>
    """
