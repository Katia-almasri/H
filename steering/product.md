---
inclusion: always
---

# Product Rules & Domain Context

## Platform

Harvest is a UAE-regulated fractional real estate investment platform (DFSA Crowdfunding, DIFC). Investors buy property shares from AED 500, earn pro-rata rental income, and vote on property decisions.

Regulatory constraints that affect all code:
- UAE data residency — Federal Decree-Law No. 45/2021
- AML/KYC obligations — Federal Decree-Law No. 20/2018

## Actors

| Actor | Client | Capabilities |
|---|---|---|
| Investor | Flutter mobile + web | Register, KYC, invest, earn rent, vote, AI signals |
| Admin | Next.js dashboard | KYC review, AML, property mgmt, distributions, audit |
| Developer | Next.js portal | Submit properties, upload rent, track funding |
| Guest | Public browse | View listings only — cannot invest or authenticate |

## Active Sprint (Sprint 1) — Auth & 2FA

| Story | Endpoint(s) | Module |
|---|---|---|
| US-002 | `POST /api/v1/auth/register` | `auth` |
| US-003 | `POST /api/v1/auth/verify-email` · `POST /api/v1/auth/resend-otp` | `auth` |
| US-004 | `POST /api/v1/auth/login` | `auth` |
| US-005 | `POST /api/v1/auth/refresh` · `POST /api/v1/auth/logout` | `auth` |
| US-006 | `POST /api/v1/2fa/setup` · `POST /api/v1/2fa/confirm` | `two_fa` |
| US-007 | `POST /api/v1/2fa/recover` | `two_fa` |
| US-008 | New device alert (triggered inside login) | `auth` |
| US-009 | `POST /api/v1/auth/forgot-password` · `POST /api/v1/auth/reset-password` | `auth` |

Sprint 1 is done when: all endpoints pass tests, Argon2id hashing works, JWT access/refresh cycle works, Redis blocklist active, TOTP setup/verify/recovery functional, audit log written on every state change, new-device alert email sent.

## Non-Negotiable Rules

These apply to every line of code regardless of sprint or module.

### Security Rules

- Hash passwords with **Argon2id** (`time_cost=2`, `memory_cost=65536`, `parallelism=2`). Never use MD5, SHA-1, or bcrypt.
- Sign JWTs with **HS256 in dev** (fallback when no RSA keys present), **RS256 in production**. Access token TTL = 15 min.
- Refresh tokens: UUID4, stored hashed, single-use rotation, blocklisted in Redis on revocation.
- 2FA is **mandatory** for: investment actions, governance votes, withdrawals, admin login. Optional at regular investor login.
- Encrypt TOTP secrets with **AES-256** before writing to the database.
- Set cookies to `HttpOnly`, `Secure`, `SameSite=Strict`. Never return tokens in a JSON response body for browser clients.
- Rate-limit login: **10 attempts/min/IP**. Lock account after 5 consecutive failures (30 min cooldown). Permanent lock after 10 failures (requires admin unlock).

### Data Rules

- Store KYC documents in **S3 `me-south-1`** with SSE-KMS. No public access.
- Store PII and financial data in **RDS `me-south-1`** with AES-256 at rest.
- Tables `ownership_ledger`, `audit_logs`, `governance_votes`, `user_agreements` are **append-only**. Never issue UPDATE or DELETE. Corrections use compensating rows.
- Every scoped query MUST filter by `tenant_id` via `TenantRepository`. No raw queries that bypass tenant isolation.

### API Contract Rules

- Wrap every response in the unified envelope: `{ success: bool, message: str, code: int, data: any }`.
- `code` mirrors the HTTP status code (200, 201, 401, 422, etc.).
- On success, populate `data`. On error, set `data` to `null` or include error details.
- Never return raw Pydantic models, plain dicts, or bare `HTTPException`.
- All errors MUST be raised as `AppException` subclasses (from `packages/core/exceptions.py`). The global handler converts them to the envelope format.
- Prefix all routes with `/api/v1/`. Breaking changes go to `/api/v2/`.

### Audit Rules

- Every state-changing endpoint MUST write to `audit_logs`.
- If the audit write fails, the parent transaction MUST roll back.
- Required fields: `user_id`, `action` (from `AuditAction` enum), `ip_address`, `user_agent`, `timestamp_utc`, `metadata` (JSON blob).

### Registration Flow (Exact Sequence)

1. `POST /register` → create user with `account_status = "needs_email_verification"`, send OTP email, return user info (no tokens).
2. `POST /verify-email` → verify OTP, transition status to `"active"`, issue JWT access + refresh tokens.
3. Login is blocked until email is verified.

### 2FA Flow (Exact Sequence)

1. `POST /2fa/setup` → generate TOTP secret, QR URI, and 8 recovery codes.
2. `POST /2fa/acknowledge-codes` → investor confirms codes are saved.
3. `POST /2fa/confirm` → verify a TOTP code, enable 2FA on the account.
4. Recovery code use → disable 2FA, require re-enrollment within 24 hours.
5. All codes exhausted → manual recovery path (KYC re-upload + video liveness, admin approval).

## Multi-Tenancy

- Read `tenant_id` from `X-Tenant-ID` header via `TenantMiddleware`.
- Default tenant: `harvest-uae`. Never hard-code tenant values — use `get_current_tenant()`.
- All queries scoped through `TenantRepository`.

## Future Sprints (Context Only — Do Not Implement)

| Sprint | Scope |
|---|---|
| 2 | KYC, AML, suitability, legal agreements, notifications |
| 3 | Property management + browse |
| 4 | Investment flow, Stripe escrow, ownership ledger, portfolio |
| 5 | Rental distribution |
| 6 | Governance engine |
| 7 | AI insights |
| 8 | NFRs, audit UI, pen test, app store |

## Fee Model (Future Reference)

| Fee | Rate | Trigger |
|---|---|---|
| Acquisition | 1.5% | At share purchase |
| Annual management | 0.75% of AUM | Deducted from gross rent |
| Exit (standard) | 1.5% | On property sale |
| Exit (loyalty) | 0% | Shares held ≥ 5 years |
| Developer listing | 0.5% | On successful funding |
