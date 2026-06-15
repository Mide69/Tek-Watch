"""FastAPI dependencies for authentication and authorisation."""
import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.cognito import verify_admin_token, verify_customer_token

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer()


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
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CustomerContext:
    """FastAPI dependency — validates customer JWT and returns CustomerContext.

    The customer_id is ALWAYS extracted from the verified JWT.
    It is never accepted from query parameters or request body.

    Raises:
        HTTPException 401: If token is missing or invalid.
    """
    try:
        claims = verify_customer_token(credentials.credentials)
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
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> AdminContext:
    """FastAPI dependency — validates admin JWT and returns AdminContext.

    Raises:
        HTTPException 401: If token is missing or invalid.
        HTTPException 403: If token is not from the admin user pool.
    """
    try:
        claims = verify_admin_token(credentials.credentials)
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
