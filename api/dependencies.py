import os
import uuid

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import DecodeError, ExpiredSignatureError, InvalidSignatureError, PyJWTError

JWKS_URL = os.environ.get("JWKS_URL", "")
JWT_AUDIENCE = os.environ.get("JWT_AUDIENCE", "authenticated")
JWT_ISSUER = os.environ.get("JWT_ISSUER", "")

security = HTTPBearer()

# Initialize JWKS Client
jwks_client: pyjwt.PyJWKClient | None = None
if JWKS_URL:
    jwks_client = pyjwt.PyJWKClient(JWKS_URL)

async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> uuid.UUID:  # noqa: B008
    """
    Decodes and verifies the Supabase JWT from the Authorization header
    using JWKS and returns the user_id (UUID).
    """
    token = credentials.credentials

    if not jwks_client:
        print("FATAL: JWKS_URL environment variable not set.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: JWKS URL not set."
        )

    user_id = None
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        payload = pyjwt.decode(
            token,
            key=signing_key.key,
            algorithms=["RS256"],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={
                "verify_aud": True,
                "verify_iss": True,
            }
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials: Missing user ID in token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        parsed_user_id = uuid.UUID(user_id)
        return parsed_user_id
        
    except ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except InvalidSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: Invalid signature. ({e})",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except DecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: Invalid token format or algorithm. ({e})",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials: Invalid user ID format in token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
