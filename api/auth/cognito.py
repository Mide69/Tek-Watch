"""Cognito JWT validation for customer and admin tokens."""
import logging
from functools import lru_cache
from typing import Optional

import httpx
from jose import JWTError, jwk, jwt

from config import load_config

logger = logging.getLogger(__name__)


@lru_cache(maxsize=2)
def _get_jwks(user_pool_id: str, region: str) -> dict:
    """Fetch and cache Cognito JWKS for a user pool."""
    url = (
        f"https://cognito-idp.{region}.amazonaws.com"
        f"/{user_pool_id}/.well-known/jwks.json"
    )
    response = httpx.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def _find_key(kid: str, jwks: dict) -> Optional[object]:
    """Find the matching public key for a given key ID."""
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            return jwk.construct(key_data)
    return None


def verify_customer_token(token: str) -> dict:
    """Verify a customer Cognito JWT and return claims.

    Raises:
        ValueError: If the token is invalid or verification fails.
    """
    config = load_config()
    return _verify_token(
        token=token,
        user_pool_id=config.cognito_customer_user_pool_id,
        app_client_id=config.cognito_customer_app_client_id,
        region=config.aws_region,
    )


def verify_admin_token(token: str) -> dict:
    """Verify an admin Cognito JWT and return claims.

    Raises:
        ValueError: If the token is invalid or verification fails.
    """
    config = load_config()
    return _verify_token(
        token=token,
        user_pool_id=config.cognito_admin_user_pool_id,
        app_client_id=config.cognito_admin_app_client_id,
        region=config.aws_region,
    )


def _verify_token(
    token: str, user_pool_id: str, app_client_id: str, region: str
) -> dict:
    """Core JWT verification logic."""
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid", "")
    except JWTError as exc:
        raise ValueError(f"Cannot decode token header: {exc}") from exc

    jwks = _get_jwks(user_pool_id, region)
    public_key = _find_key(kid, jwks)
    if not public_key:
        raise ValueError(f"No matching key found for kid: {kid}")

    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=app_client_id,
            options={"verify_exp": True},
        )
    except JWTError as exc:
        raise ValueError(f"Token verification failed: {exc}") from exc

    if claims.get("token_use") not in ("id", "access"):
        raise ValueError("Invalid token_use claim")

    return claims
