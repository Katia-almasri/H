# Tech Stack

## Runtime & Framework

| Concern | Choice | Version | Reason |
|---|---|---|---|
| Language | Python | 3.12 | Latest stable, `asyncio` improvements, `StrEnum` built-in |
| Web framework | FastAPI | 0.115 | Async-first, OpenAPI auto-generation, Depends system |
| ASGI server | Uvicorn + Gunicorn | 0.32 | Production-grade process management |
| ORM | SQLModel + SQLAlchemy async | 0.0.21 / 2.0 | Pydantic-native models + full async query API |
| Migrations | Alembic | 1.14 | Battle-tested, multi-head merge support |
| Validation | Pydantic v2 | 2.10 | 10× faster than v1, strict mode, serialisation |
| Settings | pydantic-settings | 2.6 | Typed env vars, `.env` file support, `lru_cache` singleton |

## Database

| Concern | Choice | Notes |
|---|---|---|
| Primary DB | PostgreSQL 16 | AWS RDS `me-south-1` (Bahrain) — UAE data residency |
| Async driver | `asyncpg` | Fastest Python async Postgres driver |
| Multi-tenancy | Discriminator column `tenant_id` on every scoped table | Row-level filter applied in `TenantRepository`. RLS policies as defence-in-depth. |
| Connection pooling | SQLAlchemy `pool_size=20`, `max_overflow=40` | Tune per instance size |
| Read replica | Separate `read_engine` for GET-heavy endpoints (property list, portfolio, audit log) | Configured in `packages/database/base.py` |

### Append-only tables (immutable by design)

These tables have `UPDATE` and `DELETE` blocked at the RLS level — enforced in `init.sql`:

- `ownership_ledger`
- `audit_logs`
- `governance_votes`
- `user_agreements`

Any correction requires a new compensating row. Never attempt an `UPDATE` on these.

## Caching & Session State

| Concern | Choice | TTL |
|---|---|---|
| Refresh token blocklist | Redis `SET rt_blocklist:<hash> 1 EX <ttl>` | 31 days |
| OTP storage | Redis `SET otp:<user_id> <hash> EX 600` | 10 minutes |
| Login rate limit counter | Redis sliding window | 1 minute |
| Portfolio summary cache | Redis `SET portfolio:<user_id> <json> EX 300` | 5 minutes |
| Property list cache | Redis `SET props:<tenant>:<filters_hash> <json> EX 300` | 5 minutes |

**Rule:** Financial write endpoints (investment, vote, distribution) always query the primary DB. Never serve financial data from cache.

## Security

| Concern | Implementation |
|---|---|
| Password hashing | `argon2-cffi` — Argon2id, `time_cost=2`, `memory_cost=65536`, `parallelism=2` |
| Access tokens | RS256 JWT, 15-minute TTL. Private key from AWS Secrets Manager. |
| Refresh tokens | UUID4, stored hashed in `user_sessions` table + Redis blocklist. Single-use rotation. |
| Token storage (client) | `HttpOnly` + `Secure` + `SameSite=Strict` cookies. Never `localStorage`. |
| 2FA | `pyotp` TOTP (RFC 6238). 30-second window, ±1 step tolerance. |
| 2FA secrets | AES-256 encrypted at application layer before DB insert. |
| Recovery codes | 8 × 16-char alphanumeric. `bcrypt`-hashed in `user_security.recovery_codes` JSONB. |
| Rate limiting | `slowapi` Redis-backed limiter. Login: `10/minute` per IP. |
| CORS | Explicit origin whitelist in `settings.CORS_ORIGINS`. No wildcard. |
| CSRF | `fastapi-csrf-protect` on all state-changing endpoints. |
| Input validation | Pydantic strict mode on all request bodies. No raw SQL string interpolation. ORM only. |
| Secrets management | All secrets in AWS Secrets Manager. No `.env` files in production. No hardcoded values. |
| TLS | Enforced at ALB + CloudFront. TLS 1.3. Auto-renewed ACM certificates. |

## Email

- Provider: **AWS SES** (`boto3`), region `me-south-1`
- All 14 notification templates defined in `packages/notification/templates/`
- Sent asynchronously via `asyncio.create_task` — never blocks request thread
- Failed sends: logged in `notification_logs` with `status=FAILED`. Retry 3× with exponential backoff (60s, 300s, 900s).
- From address: `noreply@shard.ae` — must be SES-verified before production

## File Storage

- Provider: **AWS S3**, bucket `shard-kyc-documents`, region `me-south-1`
- Encryption: SSE-KMS with customer-managed key (CMK)
- Access: pre-signed PUT URLs for upload (15-minute expiry), pre-signed GET URLs for admin review (15-minute expiry)
- Public access: **Block All Public Access** ON
- KYC documents never served directly — always via pre-signed URL logged in audit trail

## Infrastructure

| Component | AWS Service | Config |
|---|---|---|
| Compute | ECS Fargate | Min 2 tasks, auto-scale on CPU > 70% |
| Database | RDS PostgreSQL 16 | Multi-AZ, `me-south-1`, encrypted |
| Cache | ElastiCache Redis 7 | Cluster mode, 1 replica |
| Load balancer | ALB | HTTPS only, TLS 1.3 |
| CDN | CloudFront | Static assets + Flutter web build |
| Secrets | AWS Secrets Manager | JWT keys, DB credentials, Stripe keys |
| Monitoring | CloudWatch + AWS X-Ray | Structured logs, distributed tracing |

## Dependency Injection Pattern

FastAPI `Depends()` is used for all cross-cutting concerns. Never instantiate services directly inside routers.

```python
# Always use Depends — never direct instantiation in routers
@router.post("/register")
async def register(
    body: RegisterRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ApiResponse:
    ...
```

Service factory functions live in each module's `router.py` or a dedicated `dependencies.py`.

## Error handling

All errors are raised as `AppException` subclasses from `packages/core/exceptions.py`. The global handler in `app/main.py` converts them to structured JSON using the `ApiResponse` envelope.

**Never** return raw exceptions, validation dicts, or non-envelope responses from any endpoint.

## Testing

| Tool | Purpose |
|---|---|
| `pytest` + `pytest-asyncio` | Async test runner |
| `httpx.AsyncClient` | In-process HTTP testing (no real server) |
| `fakeredis` | In-memory Redis for tests — no real Redis needed |
| `factory-boy` | Model factories for test data |
| `pytest-cov` | Coverage gate: 80% minimum on `app/modules/` |

Every module must have tests covering: happy path, validation errors, auth errors, and DB constraint violations.