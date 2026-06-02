"""
Generate RSA key pair for JWT signing.

Usage:
    python scripts/generate_keys.py
"""
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


def generate_rsa_keys():
    """Generate RSA-2048 key pair for JWT signing"""
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Generate public key
    public_key = private_key.public_key()
    
    # Serialize public key
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    print("=" * 80)
    print("RSA KEY PAIR GENERATED")
    print("=" * 80)
    print("\nPrivate Key (JWT_PRIVATE_KEY):")
    print("-" * 80)
    print(private_pem.decode())
    print("\nPublic Key (JWT_PUBLIC_KEY):")
    print("-" * 80)
    print(public_pem.decode())
    print("\n" + "=" * 80)
    print("IMPORTANT: Store the private key securely!")
    print("Add these to your .env file (replace newlines with \\n)")
    print("=" * 80)


if __name__ == "__main__":
    generate_rsa_keys()
