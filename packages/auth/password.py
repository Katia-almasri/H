import argon2
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from packages.core.config import settings

# Initialize Argon2id hasher with configured parameters
ph = PasswordHasher(
    time_cost=settings.ARGON2_TIME_COST,
    memory_cost=settings.ARGON2_MEMORY_COST,
    parallelism=settings.ARGON2_PARALLELISM,
    hash_len=32,
    salt_len=16,
    type=argon2.low_level.Type.ID  # Argon2id
)


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2id.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    return ph.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        password: Plain text password to verify
        hashed_password: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        ph.verify(hashed_password, password)
        
        # Check if rehashing is needed (parameters changed)
        if ph.check_needs_rehash(hashed_password):
            # In production, you'd want to rehash and update the database
            pass
            
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False
