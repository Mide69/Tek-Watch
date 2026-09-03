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
    """Create the customer's Cognito login.

    The pool is case-insensitive, so Cognito stores and returns this username
    lower-cased however it is passed in. Anything that turns a token back into
    a database key therefore has to fold the case itself — see
    auth.dependencies.canonical_customer_id. Passing the id unchanged here is
    correct; assuming it comes back unchanged is what created a second,
    parallel customer record.
    """
    """Create a Cognito user for a newly self-signed-up customer with a
    permanent password, ready to sign in immediately.

    Raises:
        ClientError: If Cognito user creation fails (e.g. duplicate username).
    """
    client = boto3.client("cognito-idp", region_name=region)

    # Let Cognito send the invite. The pool's admin_create_user_config already
    # carries a template for exactly this ("Your Customer ID is {username} and
    # temporary password is {####}"), and Cognito's own delivery is proven in
    # this account.
    #
    # This previously passed MessageAction="SUPPRESS" and then set a permanent
    # password, so the app had to deliver the credentials itself over SES — a
    # path that was never configured, failed silently, and left customers with
    # an account and no way to learn about it.
    #
    # Not setting a permanent password is deliberate: the customer arrives in
    # FORCE_CHANGE_PASSWORD and chooses their own on first sign-in, so no
    # password we generated is ever transmitted or stored by us.
    client.admin_create_user(
        UserPoolId=user_pool_id,
        Username=customer_id,
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
        ],
        TemporaryPassword=password,
        DesiredDeliveryMediums=["EMAIL"],
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
