"""Server-side Cognito user provisioning for self-service signup.

The customer user pool has AllowAdminCreateUserOnly=true by design (see
infrastructure/terraform/modules/cognito/main.tf), self-signup happens
through this backend-mediated path instead of a public Cognito signup
flow, keeping Cognito itself admin-only and all validation/abuse
prevention in code we control.

Sets the generated password as permanent (rather than leaving Cognito's
usual "temporary password, must change on first login" flow) because the
dashboard's sign-in flow (dashboard/src/lib/auth.ts) does not yet handle
the NEW_PASSWORD_REQUIRED challenge. Customers can still change their
password any time via the existing forgot-password flow.
"""
import logging
import secrets
import string

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def generate_password(length: int = 16) -> str:
    """Generate a random password satisfying the customer pool's policy
    (12+ chars, upper, lower, number; see modules/cognito/main.tf)."""
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
        ):
            return password


def provision_customer_login(
    user_pool_id: str, region: str, customer_id: str, email: str, password: str
) -> None:
    """Create a Cognito user for a newly self-signed-up customer with a
    permanent password, ready to sign in immediately.

    Raises:
        ClientError: If Cognito user creation fails (e.g. duplicate username).
    """
    client = boto3.client("cognito-idp", region_name=region)

    client.admin_create_user(
        UserPoolId=user_pool_id,
        Username=customer_id,
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
        ],
        TemporaryPassword=password,
        MessageAction="SUPPRESS",
    )
    client.admin_set_user_password(
        UserPoolId=user_pool_id,
        Username=customer_id,
        Password=password,
        Permanent=True,
    )
    logger.info("Cognito login provisioned for %s", customer_id)


def deprovision_customer_login(user_pool_id: str, region: str, customer_id: str) -> None:
    """Best-effort cleanup of a Cognito user if a later signup step fails.

    Swallows errors: this is a rollback path, not the primary flow, and
    should never mask the original failure that triggered it.
    """
    try:
        client = boto3.client("cognito-idp", region_name=region)
        client.admin_delete_user(UserPoolId=user_pool_id, Username=customer_id)
    except ClientError as exc:
        logger.error("Failed to roll back Cognito user for %s: %s", customer_id, exc)
