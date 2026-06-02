"""
Generate a TOTP QR code for testing 2FA setup.

Usage:
    python scripts/generate_qr.py
    python scripts/generate_qr.py --email user@example.com --secret YOUR_BASE32_SECRET

The QR code is saved as scripts/totp_qr.png and can be scanned
with Google Authenticator, Authy, or any TOTP-compatible app.
"""

import argparse
import sys

try:
    import pyotp
except ImportError:
    print("ERROR: pyotp not installed. Run: pip install pyotp")
    sys.exit(1)

try:
    import qrcode
except ImportError:
    print("ERROR: qrcode not installed. Run: pip install qrcode[pil]")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Generate TOTP QR code for 2FA testing")
    parser.add_argument("--email", default="investor@harvest.ae", help="Account email (default: investor@harvest.ae)")
    parser.add_argument("--secret", default=None, help="Base32 TOTP secret (auto-generated if not provided)")
    parser.add_argument("--issuer", default="Harvest", help="Issuer name shown in authenticator app")
    parser.add_argument("--output", default="scripts/totp_qr.png", help="Output file path (default: scripts/totp_qr.png)")
    args = parser.parse_args()

    # Generate or use provided secret
    secret = args.secret or pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=args.email, issuer_name=args.issuer)

    # Generate QR code image
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(args.output)

    # Print info
    print("=" * 60)
    print("TOTP 2FA QR Code Generated")
    print("=" * 60)
    print(f"Email:            {args.email}")
    print(f"Issuer:           {args.issuer}")
    print(f"Secret (base32):  {secret}")
    print(f"Provisioning URI: {provisioning_uri}")
    print(f"QR saved to:      {args.output}")
    print(f"Current OTP:      {totp.now()}")
    print("=" * 60)
    print()
    print("Scan the QR code with Google Authenticator, Authy, or similar.")
    print("Use the 'Current OTP' above to test /api/v1/2fa/confirm immediately.")


if __name__ == "__main__":
    main()
