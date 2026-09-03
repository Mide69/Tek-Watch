"""FastAPI dependencies for authentication and authorisation."""
import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.cognito import verify_admin_token, verify_customer_token

logger = logging.getLogger(__name__)

# auto_error=False so a MISSING Authorization header surfaces as credentials=None
# and we raise 401 ourselves. FastAPI's default (auto_error=True) raises 403
# instead, which contradicts the 401 documented on both dependencies below, is
# the wrong status for absent credentials, and collides with the CloudFront
# custom_error_response that maps 403 to the SPA's 404 page — turning every
# unauthenticated API call into an HTML page instead of JSON.
bearer_scheme = HTTPBearer(auto_error=False)


def _require_credentials(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> HTTPAuthorizationCredentials:
    """Return credentials, or raise 401 when the Authorization header is absent."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials


def canonical_customer_id(value: str) -> str:
    """Fold a customer id to the one casing DynamoDB is keyed on.

    Ids are minted uppercase (TT-9F4KQ7M2) and written to DynamoDB that way,
    but the Cognito pool is configured case-insensitive, and such a pool stores
    and returns the username in lower case. So the token said "tt-0001" for a
    record written as "TT-0001", and DynamoDB keys are case-sensitive.

    Every signed-in write therefore created and updated a second, parallel
    record: the customer's company name, their uploaded logo and their issued
    agent key all went to "tt-0001", while their email, subscription tier and
    account status stayed on "TT-0001". Neither record was complete, and
    nothing anywhere reported a problem.

    Folding here, at the single point where a token becomes an identity, is
    what keeps one customer to one record whatever casing arrives.
    """
    return (value or "").strip().upper()


@dataclass(frozen=True)
class CustomerContext:
    """Authenticated customer context extracted from JWT."""

    customer_id: str
    cognito_sub: str
    email: str


@dataclass(frozen=True)
class AdminContext:
    """Authenticated admin context extracted from JWT."""

    admin_sub: str
    email: str


def get_current_customer(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> CustomerContext:
    """FastAPI dependency — validates customer JWT and returns CustomerContext.

    The customer_id is ALWAYS extracted from the verified JWT.
    It is never accepted from query parameters or request body.

    Raises:
        HTTPException 401: If token is missing or invalid.
    """
    try:
        claims = verify_customer_token(_require_credentials(credentials).credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    customer_id = canonical_customer_id(
        claims.get("cognito:username") or claims.get("username", "")
    )
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="customer_id not found in token",
        )

    # Store on request state so UsageMeterMiddleware can read it after the response
    request.state.customer_id = customer_id

    return CustomerContext(
        customer_id=customer_id,
        cognito_sub=claims.get("sub", ""),
        email=claims.get("email", ""),
    )


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AdminContext:
    """FastAPI dependency — validates admin JWT and returns AdminContext.

    Raises:
        HTTPException 401: If token is missing or invalid.
        HTTPException 403: If token is not from the admin user pool.
    """
    try:
        claims = verify_admin_token(_require_credentials(credentials).credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return AdminContext(
        admin_sub=claims.get("sub", ""),
        email=claims.get("email", ""),
    )
