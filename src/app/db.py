import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def normalize(url: str) -> str:
    """Hosts hand out `postgres://` or `postgresql://`; SQLAlchemy needs the psycopg driver named."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


# shortcut: local SQLite file when DATABASE_URL is unset, fine for one user offline only.
DATABASE_URL = normalize(os.getenv("DATABASE_URL", "sqlite:///budget.db"))
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,  # a free-tier database drops idle connections
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# create_all() makes new tables but never changes existing ones, so columns added after the
# first release are added here. Running this on every start is safe: it only adds what is missing.
ADDED_COLUMNS = (
    ("wallet", "user_id", "INTEGER REFERENCES app_user(id)"),
    ("plan", "user_id", "INTEGER REFERENCES app_user(id)"),
)
ADDED_INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_wallet_user_id ON wallet (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_plan_user_id ON plan (user_id)",
)


def upgrade_schema(engine) -> None:
    with engine.begin() as conn:
        for table, column, ddl in ADDED_COLUMNS:
            if column not in {c["name"] for c in inspect(conn).get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        for statement in ADDED_INDEXES:
            conn.execute(text(statement))


def get_db():
    with SessionLocal() as db:
        yield db
