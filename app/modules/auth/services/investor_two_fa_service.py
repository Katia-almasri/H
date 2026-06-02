"""Investor 2FA service — TOTP setup, verification, and recovery."""

import uuid
import json
import secrets
import string
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

import pyotp
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.investor import Investor
from app.modules.auth.repositories.investor_repository import InvestorRepository


class InvestorTwoFAService:
    """TOTP 2FA for investors."""

    RECOVERY_CODE_COUNT = 8
    RECOVERY_CODE_LENGTH = 16
    RE_ENROLLMENT_HOURS = 24
    LOW_CODES_THRESHOLD = 3

    def __init__(self, db: AsyncSession, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client
        self.investor_repo = InvestorRepository(db)

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def initiate_setup(self, user_id: str, email: str) -> dict:
        """Generate TOTP secret, QR URI, and 8 recovery codes."""
        investor = await self._get_or_create_investor(user_id)

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(name=email, issuer_name="Harvest")

        recovery_codes = self._generate_recovery_codes()
        recovery_hashes = [self._hash_code(c) for c in recovery_codes]

        investor.totp_secret_encrypted = secret  # TODO: AES-256 encrypt
        investor.two_fa_status = "pending_confirmation"
        investor.recovery_codes_hash = json.dumps(recovery_hashes)
        investor.recovery_codes_remaining = str(self.RECOVERY_CODE_COUNT)
        investor.recovery_codes_acknowledged = False
        investor.updated_at = datetime.utcnow()
        await self.investor_repo.update(investor)

        return {
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "recovery_codes": recovery_codes,
        }

    async def acknowledge_recovery_codes(self, user_id: str) -> bool:
        """Investor confirms saving recovery codes."""
        investor = await self.investor_repo.get_by_user_id(user_id)
        if not investor:
            return False
        investor.recovery_codes_acknowledged = True
        investor.updated_at = datetime.utcnow()
        await self.investor_repo.update(investor)
        return True

    async def confirm_setup(self, user_id: str, totp_code: str) -> bool:
        """Verify TOTP code to complete enrollment."""
        investor = await self.investor_repo.get_by_user_id(user_id)
        if not investor or investor.two_fa_status != "pending_confirmation":
            return False
        if not investor.recovery_codes_acknowledged:
            return False

        totp = pyotp.TOTP(investor.totp_secret_encrypted)
        if not totp.verify(totp_code, valid_window=1):
            return False

        investor.two_fa_enabled = True
        investor.two_fa_status = "enabled"
        investor.two_fa_enabled_at = datetime.utcnow()
        investor.re_enrollment_deadline = None
        investor.updated_at = datetime.utcnow()
        await self.investor_repo.update(investor)
        return True

    # ── Verification ──────────────────────────────────────────────────────────

    async def verify_totp(self, user_id: str, code: str) -> bool:
        """Verify a TOTP code."""
        investor = await self.investor_repo.get_by_user_id(user_id)
        if not investor or not investor.two_fa_enabled:
            return False
        totp = pyotp.TOTP(investor.totp_secret_encrypted)
        return totp.verify(code, valid_window=1)

    async def is_2fa_enabled(self, user_id: str) -> bool:
        investor = await self.investor_repo.get_by_user_id(user_id)
        return investor.two_fa_enabled if investor else False

    # ── Recovery ──────────────────────────────────────────────────────────────

    async def use_recovery_code(
        self, user_id: str, code: str, ip_address: str, user_agent: Optional[str] = None
    ) -> bool:
        """Use a single-use recovery code. Disables 2FA, sets re-enrollment deadline."""
        investor = await self.investor_repo.get_by_user_id(user_id)
        if not investor or not investor.recovery_codes_hash:
            return False

        code_hash = self._hash_code(code)
        codes = json.loads(investor.recovery_codes_hash)

        if code_hash not in codes:
            return False

        codes.remove(code_hash)
        remaining = len(codes)

        investor.recovery_codes_hash = json.dumps(codes)
        investor.recovery_codes_remaining = str(remaining)
        investor.two_fa_enabled = False
        investor.two_fa_status = "requires_re_enrollment"
        investor.re_enrollment_deadline = datetime.utcnow() + timedelta(hours=self.RE_ENROLLMENT_HOURS)
        investor.updated_at = datetime.utcnow()
        await self.investor_repo.update(investor)

        # Log to console (replace with audit log in production)
        print(f"[RECOVERY] user={user_id} ip={ip_address} agent={user_agent} remaining={remaining}")

        if 0 < remaining < self.LOW_CODES_THRESHOLD:
            print(f"[SEC_001] user={user_id} — Only {remaining} recovery codes remaining!")

        return True

    async def get_status(self, user_id: str) -> dict:
        """Get 2FA status for an investor."""
        investor = await self.investor_repo.get_by_user_id(user_id)
        if not investor:
            return {"two_fa_enabled": False, "status": "disabled", "recovery_codes_remaining": 0, "re_enrollment_deadline": None}
        return {
            "two_fa_enabled": investor.two_fa_enabled,
            "status": investor.two_fa_status,
            "recovery_codes_remaining": int(investor.recovery_codes_remaining),
            "re_enrollment_deadline": investor.re_enrollment_deadline.isoformat() if investor.re_enrollment_deadline else None,
        }

    async def disable(self, user_id: str) -> bool:
        """Disable 2FA completely."""
        investor = await self.investor_repo.get_by_user_id(user_id)
        if not investor:
            return False
        investor.two_fa_enabled = False
        investor.two_fa_status = "disabled"
        investor.totp_secret_encrypted = None
        investor.recovery_codes_hash = None
        investor.recovery_codes_remaining = "0"
        investor.recovery_codes_acknowledged = False
        investor.re_enrollment_deadline = None
        investor.updated_at = datetime.utcnow()
        await self.investor_repo.update(investor)
        return True

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_or_create_investor(self, user_id: str) -> Investor:
        investor = await self.investor_repo.get_by_user_id(user_id)
        if not investor:
            investor = Investor(id=str(uuid.uuid4()), user_id=user_id)
            investor = await self.investor_repo.create(investor)
        return investor

    def _generate_recovery_codes(self) -> List[str]:
        chars = string.ascii_uppercase + string.digits
        return ["".join(secrets.choice(chars) for _ in range(self.RECOVERY_CODE_LENGTH)) for _ in range(self.RECOVERY_CODE_COUNT)]

    def _hash_code(self, code: str) -> str:
        return hashlib.sha256(code.upper().encode()).hexdigest()
