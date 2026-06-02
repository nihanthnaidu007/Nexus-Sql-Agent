from dotenv import load_dotenv
load_dotenv()

from nixus.config import settings
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy import create_engine, text

DATABASE_URL = settings.database_url
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable not set. "
        "Copy .env.example to .env and set your database URL."
    )

# ── Async engine (asyncpg) — used by all application nodes ──────────────────

if DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    ASYNC_DATABASE_URL = DATABASE_URL

# asyncpg handles SSL via connect_args, not via sslmode= query param
if "?sslmode=require" in ASYNC_DATABASE_URL:
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("?sslmode=require", "")
elif "&sslmode=require" in ASYNC_DATABASE_URL:
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("&sslmode=require", "")

IS_NEON = "neon.tech" in DATABASE_URL

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args={"ssl": "require"} if IS_NEON else {},
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def check_db_connection() -> bool:
    """Async health check — used by FastAPI /api/health."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ── Sync engine (psycopg2) — used ONLY by seed scripts and init_db ──────────
# asyncpg: async driver for main application
# psycopg2-binary: sync driver for seed scripts only

sync_engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)
