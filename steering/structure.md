---
inclusion: always
---

# Project Structure & Conventions

## Architecture

Modular monolith. All domain modules live under `app/modules/<name>/` as self-contained units. Shared utilities live in `packages/`.

```
app/
├── main.py              # FastAPI app, lifespan, middleware registration
├── config.py            # Pydantic settings singleton
├── database.py          # Async engine, session factory, Base declarative
├── redis_client.py      # Redis async client factory
├── api/v1/routes.py     # Central router — mounts all module routers
├── middleware/           # Custom middleware (timeout, tenant, etc.)
└── modules/             # Domain modules (auth, user, property, etc.)

packages/
├── core/                # Response envelope, exceptions, enums, error codes
├── auth/                # JWT handler, password hashing utilities
└── database/            # Shared engine config, base model
```

## Module Structure

Every module under `app/modules/<name>/` follows this layout:

```
module_name/
├── __init__.py
├── router.py                    # FastAPI routes (HTTP layer only)
├── services/                    # Business logic (one service per concern)
│   ├── __init__.py              # Re-exports all service classes
│   ├── main_service.py          # Primary orchestrator service
│   └── helper_service.py        # Focused sub-services
├── models/                      # SQLAlchemy models (one per file)
│   ├── __init__.py
│   └── entity.py
├── repositories/                # Data access (one per model)
│   ├── __init__.py
│   └── entity_repository.py
├── schemas/
│   ├── requests/                # Pydantic request DTOs
│   └── responses/               # Pydantic response DTOs
└── enums/                       # Module-specific enums (optional)
```

When a module has only one service, a single `service.py` file is acceptable. When complexity grows, split into a `services/` directory with focused classes.

## Layer Responsibilities

| Layer | Does | Does NOT |
|-------|------|----------|
| `router.py` | Parse HTTP, validate input, call service, return envelope | Contain business logic, call repositories directly |
| `services/` | Orchestrate business rules, coordinate repos and external calls | Execute raw SQL, return HTTP responses |
| `repositories/` | Execute ORM queries, handle DB transactions | Contain business rules, raise HTTP exceptions |
| `schemas/` | Validate and serialize data shapes | Contain logic beyond field validation |

## Naming Conventions

### Files (snake_case, singular)
- Models: `user.py`, `property.py`
- Repositories: `user_repository.py`
- Services: `auth_service.py`, `token_service.py`
- Request schemas: `register.py`, `login.py` (action-based)
- Response schemas: `user.py`, `token.py` (entity-based)

### Classes (PascalCase)
- Models: `User`, `Property`
- Repositories: `UserRepository`
- Services: `AuthService`, `TokenService`
- Request schemas: `RegisterRequest`, `LoginRequest`
- Response schemas: `UserResponse`, `TokenResponse`

### Functions (snake_case)
- Services: `register_user()`, `authenticate_user()` (verb + noun)
- Repositories: `get_by_id()`, `get_by_email()`, `create()`, `update()` (CRUD verbs)
- Dependencies: `get_auth_service()`, `get_db()` (prefixed with `get_`)

## Dependency Injection Pattern

All dependencies use FastAPI `Depends()`. Service factories are defined in `router.py`.

```python
from typing import Annotated
from fastapi import Depends

# Dependency factory in router.py
def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> AuthService:
    return AuthService(db, redis_client)

# Route using the dependency
@router.post("/auth/login")
async def login(
    body: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    ...
```

Never instantiate services directly inside route handlers.

## Service Composition

Services receive `AsyncSession` and `Redis` in their constructor. They instantiate their own repositories and sub-services internally:

```python
class AuthService:
    def __init__(self, db: AsyncSession, redis_client: Redis):
        self.db = db
        self.redis = redis_client
        self.user_repo = UserRepository(db)
        self.session_repo = SessionRepository(db)
        self.token_service = TokenService(redis_client)
```

## Model Pattern

Models use plain SQLAlchemy declarative style with `Base` from `app.database`:

```python
from sqlalchemy import Column, String, Boolean, DateTime
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)  # UUID as string
    email = Column(String, unique=True, index=True, nullable=False)
    ...
```

- Primary keys: UUID4 strings generated in the service layer.
- Enum columns: stored as `String` matching the enum `.value`.
- Timestamps: `created_at`, `updated_at` on every model.

## Repository Pattern

Repositories take `AsyncSession` in their constructor and use SQLAlchemy `select`/`update` statements:

```python
class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
```

## Response Envelope

Every endpoint returns the unified envelope via `packages.core.response.api_response`:

```python
from packages.core.response import api_response

return api_response(
    message="Login successful",
    data=LoginResponse(...).model_dump(),
    code=200,
)
```

Shape: `{ "success": bool, "message": str, "code": int, "data": any }`

## Error Handling

All errors are raised as `AppException` subclasses from `packages.core.exceptions`:

- `ValidationException` (422)
- `AuthenticationException` (401)
- `AuthorizationException` (403)
- `NotFoundException` (404)
- `ConflictException` (409)
- `RateLimitException` (429)
- `AccountLockedException` (423)

Never return raw exceptions, plain dicts, or bare `HTTPException`.

## Import Conventions

Use absolute imports everywhere:

```python
# Models
from app.modules.auth.models.user import User

# Repositories
from app.modules.auth.repositories import UserRepository

# Services (via __init__.py re-exports)
from app.modules.auth.services import AuthService, TokenService

# Schemas
from app.modules.auth.schemas import RegisterRequest, UserResponse

# Shared packages
from packages.core.response import api_response
from packages.core.exceptions import AuthenticationException
from app.config import settings
from app.database import get_db
from app.redis_client import get_redis
```

## Router Registration

All module routers are mounted in `app/api/v1/routes.py`:

```python
from fastapi import APIRouter
from app.modules.auth.router import router as auth_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
```

## Adding a New Module

1. Create directory: `app/modules/<name>/` with subdirectories `models/`, `repositories/`, `services/`, `schemas/requests/`, `schemas/responses/`
2. Add `__init__.py` to every directory
3. Implement: model → repository → service → schemas → router
4. Register router in `app/api/v1/routes.py`
5. Import models in `app/database.py` so Alembic detects them
6. Generate migration: `alembic revision --autogenerate -m "Add <name> tables"`
7. Add tests under `tests/<name>/`

## Key Rules

- One model per file, one repository per model
- No business logic in routers — routers only parse HTTP and delegate
- All DB access goes through repositories — never query from services directly via raw session
- Use `Annotated[Type, Depends(...)]` for all injected dependencies
- Schemas split into `requests/` and `responses/` — never reuse a request schema as a response
- Enums stored as string values in the DB, compared via `.value`
- All async — no synchronous DB calls or blocking I/O in the request path
