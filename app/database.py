from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

engine = create_async_engine(
    settings.database_url.replace('asyncpg', 'psycopg'),  # Use psycopg driver
    echo=False,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Import all module models so Alembic autogenerate detects them.
#
# These imports MUST sit at the bottom of the file: the model modules
# themselves do ``from app.database import Base``, so ``Base`` must already be
# defined before they are imported.
#
# The plain ``import a.b.c`` form (rather than ``from a.b.c import D``) is
# deliberate: it only binds the module reference, so Python tolerates the
# partial-initialisation state that occurs when a model's own
# ``from app.database import Base`` re-enters this file. The class objects
# still register themselves on ``Base.metadata`` as their module bodies
# execute, which is all Alembic autogenerate requires.
import app.modules.suitability_questionnaire.models.investor_suitability  # noqa: E402, F401
import app.modules.suitability_questionnaire.models.suitability_acknowledgement  # noqa: E402, F401
import app.modules.suitability_questionnaire.models.suitability_completion_marker  # noqa: E402, F401
