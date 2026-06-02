import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from packages.core.config import settings
from packages.core.exceptions import AuthenticationException


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    tenant_id: str,
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a JWT access token using RS256.
    
    Args:
        user_id: User UUID
        email: User email
        role: User role
        tenant_id: Tenant ID
        additional_claims: Optional additional claims to include
        
    Returns:
        Encoded JWT token string
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "tenant_id": tenant_id,
        "iat": now,
        "exp": expires_at,
        "type": "access"
    }
    
    if additional_claims:
        payload.update(additional_claims)
    
    return jwt.encode(
        payload,
        settings.JWT_PRIVATE_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token() -> str:
    """
    Create a refresh token (UUID4).
    This token is stored hashed in the database.
    
    Returns:
        UUID4 string
    """
    return str(uuid.uuid4())


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT access token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        AuthenticationException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_PUBLIC_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        if payload.get("type") != "access":
            raise AuthenticationException("Invalid token type")
            
        return payload
        
    except jwt.ExpiredSignatureError:
        raise AuthenticationException("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationException(f"Invalid token: {str(e)}")


def get_token_expiry(token_type: str = "access") -> datetime:
    """
    Get the expiry datetime for a token type.
    
    Args:
        token_type: Type of token ("access" or "refresh")
        
    Returns:
        Expiry datetime in UTC
    """
    now = datetime.now(timezone.utc)
    
    if token_type == "access":
        return now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    elif token_type == "refresh":
        return now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    return now
