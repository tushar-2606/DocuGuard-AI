from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _column_names(table: str) -> set:
    with engine.connect() as conn:
        if DATABASE_URL.startswith("sqlite"):
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            return {row[1] for row in rows}
        rows = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :table"
            ),
            {"table": table},
        ).fetchall()
        return {row[0] for row in rows}


def _add_column_if_missing(table: str, column: str, ddl_type: str) -> None:
    existing = _column_names(table)
    if column in existing:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


def ensure_schema_upgrades() -> None:
    """
    Safe additive upgrades for existing SQLite/Postgres databases.
    Never drops columns or tables. create_all handles brand-new installs.
    """
    try:
        tables = set()
        with engine.connect() as conn:
            if DATABASE_URL.startswith("sqlite"):
                rows = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).fetchall()
                tables = {r[0] for r in rows}
            else:
                rows = conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                ).fetchall()
                tables = {r[0] for r in rows}
    except Exception:
        return

    if "documents" in tables:
        _add_column_if_missing("documents", "status", "VARCHAR(50) DEFAULT 'completed'")
        _add_column_if_missing("documents", "processing_error", "TEXT DEFAULT ''")
        _add_column_if_missing("documents", "content_hash", "VARCHAR(64) DEFAULT ''")
        _add_column_if_missing("documents", "safe_filename", "VARCHAR(255) DEFAULT ''")
        _add_column_if_missing("documents", "extraction_warnings", "TEXT DEFAULT ''")

    if "tasks" in tables:
        _add_column_if_missing("tasks", "page_number", "INTEGER")
        _add_column_if_missing("tasks", "date_explicit", "BOOLEAN DEFAULT 0")
        _add_column_if_missing("tasks", "review_status", "VARCHAR(30) DEFAULT 'pending'")
        _add_column_if_missing("tasks", "extraction_method", "VARCHAR(50) DEFAULT 'rule_based'")
        _add_column_if_missing("tasks", "updated_at", "DATETIME")
        _add_column_if_missing("tasks", "description", "TEXT DEFAULT ''")

    if "deadlines" in tables:
        _add_column_if_missing("deadlines", "page_number", "INTEGER")
        _add_column_if_missing("deadlines", "date_explicit", "BOOLEAN DEFAULT 0")

    if "rules" in tables:
        _add_column_if_missing("rules", "page_number", "INTEGER")


def init_db():
    from app.models import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_schema_upgrades()
