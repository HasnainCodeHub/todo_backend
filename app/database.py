"""Database module for MCP Server using SQLModel with Neon PostgreSQL and enhanced resilience."""

from sqlmodel import create_engine, Session
from contextlib import contextmanager
from .config import settings
from sqlalchemy.pool import QueuePool, StaticPool
from sqlalchemy import event, inspect, text
import logging
import os

logger = logging.getLogger(__name__)

# Determine the database URL - use SQLite for testing if no URL provided
_database_url = settings.database_url
if not _database_url or _database_url == "":
    # Use in-memory SQLite for testing
    _database_url = "sqlite:///:memory:"
    logger.warning("No DATABASE_URL set, using in-memory SQLite for testing")
elif _database_url.startswith("postgresql://") or _database_url.startswith("postgres://"):
    # Convert to psycopg2 driver format
    _database_url = _database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    _database_url = _database_url.replace("postgres://", "postgresql+psycopg2://", 1)

# Configure engine based on database type
if _database_url.startswith("sqlite"):
    # SQLite configuration (for testing)
    engine = create_engine(
        _database_url,
        echo=settings.debug,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Use StaticPool for SQLite
    )
else:
    # PostgreSQL configuration (for production)
    engine = create_engine(
        _database_url,
        echo=settings.debug,  # Log SQL queries in debug mode
        pool_pre_ping=True,  # Verify connections before use (critical for Neon serverless)
        pool_size=5,  # Number of connection pools
        max_overflow=10,  # Additional connections beyond pool_size
        pool_recycle=300,  # Recycle connections after 5 minutes (recommended for Neon)
        pool_timeout=30,  # Time to wait for a connection from the pool
        poolclass=QueuePool,  # Use QueuePool for thread safety
        connect_args={
            "connect_timeout": 10,  # Timeout for establishing connection
            "application_name": "todo-backend",  # Application name for monitoring
        },
    )


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas if using SQLite (for local development)."""
    # Check if this is a SQLite connection by checking the module name
    connection_module = type(dbapi_connection).__module__
    if 'sqlite' in connection_module.lower():
        cursor = dbapi_connection.cursor()
        # Enable WAL mode for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=1000")
        cursor.close()


def get_engine():
    """Get the database engine instance."""
    return engine


@contextmanager
def get_session():
    """Get a database session using context manager with enhanced error handling."""
    session = Session(engine)
    try:
        yield session
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {str(e)}")
        raise
    finally:
        # Explicitly close the session to return connection to pool
        session.close()


def init_db():
    """Initialize the database by creating all tables."""
    from .models.task import Task  # Import here to avoid circular imports
    from .models.conversation import Conversation, Message  # Phase 3: Chat tables
    from sqlmodel import SQLModel

    # Create all tables defined in SQLModel models
    SQLModel.metadata.create_all(engine)
    _ensure_task_schema_columns()
    logger.info("Database tables created successfully")


def _ensure_task_schema_columns():
    """Apply idempotent task-table schema updates for existing databases."""
    inspector = inspect(engine)

    if "task" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("task")}
    statements = []

    if "priority" not in existing_columns:
        statements.append("ALTER TABLE task ADD COLUMN priority VARCHAR(10) NOT NULL DEFAULT 'medium'")
    if "due_date" not in existing_columns:
        statements.append("ALTER TABLE task ADD COLUMN due_date TIMESTAMP NULL")
    if "category" not in existing_columns:
        statements.append("ALTER TABLE task ADD COLUMN category VARCHAR(50) NULL")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

    logger.info("Applied task schema column updates for: %s", ", ".join(
        statement.split(" ADD COLUMN ", 1)[1].split(" ", 1)[0] for statement in statements
    ))


def test_connection():
    """Test the database connection."""
    try:
        with Session(engine) as session:
            # Execute a simple query to test the connection
            session.execute("SELECT 1")
            logger.info("Database connection test successful")
            return True
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        return False


if __name__ == "__main__":
    # Initialize database when run directly
    init_db()
    print("Database initialized successfully!")
