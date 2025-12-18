"""
FastAPI dependencies for authentication.
"""

import logging
import os
from dataclasses import dataclass

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Header, HTTPException


@dataclass
class AuthInfo:
    """Authentication info from JWT."""
    user_id: str
    token: str  # Raw JWT token for passthrough to backend

logger = logging.getLogger(__name__)

# JWT verification config
# JWT_VERIFY=true (default) requires JWT_PUBLIC_KEY to be set
# JWT_VERIFY=false skips signature verification (for local dev only)
JWT_VERIFY = os.getenv("JWT_VERIFY", "true").lower() == "true"
JWT_PUBLIC_KEY_HEX = os.getenv("JWT_PUBLIC_KEY")
PUBLIC_KEY = None

if JWT_VERIFY:
    if not JWT_PUBLIC_KEY_HEX:
        raise RuntimeError("JWT_PUBLIC_KEY must be set when JWT_VERIFY=true")
    try:
        # Load EC public key from hex string (uncompressed format: 04 + x + y)
        if not JWT_PUBLIC_KEY_HEX.startswith("04"):
            raise ValueError("Public key must be in uncompressed format (start with 04)")

        x_hex = JWT_PUBLIC_KEY_HEX[2:66]
        y_hex = JWT_PUBLIC_KEY_HEX[66:130]

        x = int(x_hex, 16)
        y = int(y_hex, 16)

        public_numbers = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1())
        PUBLIC_KEY = public_numbers.public_key(default_backend())
        logger.info("JWT signature validation enabled")
    except Exception as e:
        raise RuntimeError(f"Failed to load JWT public key: {e}")
else:
    logger.warning("JWT_VERIFY=false - signature validation DISABLED (dev mode only)")


async def require_api_key(
    x_api_key: str = Header(None, alias="X-API-KEY"),
    authorization: str = Header(None, alias="Authorization"),
) -> str:
    """
    Dependency to require API key authentication. Returns user_id.

    Accepts JWT token via:
    - X-API-KEY header
    - Authorization: Bearer <token> header

    Validates the JWT signature using ES256 if public key is available,
    otherwise decodes without verification (backend validates on API calls).
    """
    token = x_api_key

    # Try Bearer token if no X-API-KEY
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide X-API-KEY or Authorization header",
        )

    try:
        if JWT_VERIFY:
            # Verify JWT signature with ES256
            payload = jwt.decode(token, PUBLIC_KEY, algorithms=["ES256"])
        else:
            # Dev mode: decode without signature verification
            payload = jwt.decode(token, options={"verify_signature": False})

        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token missing user_id")

        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


async def require_auth(
    x_api_key: str = Header(None, alias="X-API-KEY"),
    authorization: str = Header(None, alias="Authorization"),
) -> AuthInfo:
    """
    Dependency that returns AuthInfo with user_id and raw token.
    Use this when you need to pass the token through to the backend.
    """
    token = x_api_key

    # Try Bearer token if no X-API-KEY
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide X-API-KEY or Authorization header",
        )

    try:
        if JWT_VERIFY:
            payload = jwt.decode(token, PUBLIC_KEY, algorithms=["ES256"])
        else:
            payload = jwt.decode(token, options={"verify_signature": False})

        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token missing user_id")

        return AuthInfo(user_id=user_id, token=token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
