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

    customer_id = claims.get("cognito:username") or claims.get("username", "")
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
