"""
Database connection and table setup for AWS RDS PostgreSQL.

Reads credentials from environment variables (see .env.example).
Falls back to in-memory storage when the database is unreachable,
so local development works without an RDS connection.
"""

import os
import logging
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection settings (all from env vars – never hard-code secrets)
# ---------------------------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "food-recall-db.cwbmyoom67nu.us-east-1.rds.amazonaws.com")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "food_recall")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")  # MUST be set via env / .env

# Track whether the DB is available
_db_available: bool = False


def get_connection():
    """Return a new psycopg2 connection to the RDS instance."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=5,
    )


@contextmanager
def get_cursor(commit: bool = False):
    """Context manager that yields a RealDictCursor and optionally commits."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
            if commit:
                conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Table creation (idempotent – safe to run on every startup)
# ---------------------------------------------------------------------------
_INIT_SQL = """
-- Users table for authentication.
-- Uses username (not email) to match the frontend auth flow.
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- User preferences (state, allergies, diet) – one row per user.
CREATE TABLE IF NOT EXISTS user_preferences (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    state_location   VARCHAR(100),
    allergies        TEXT[] DEFAULT '{}',
    diet_preferences TEXT[] DEFAULT '{}'
);
"""


def init_db() -> bool:
    """Create tables if they don't exist. Returns True on success."""
    global _db_available
    if not DB_PASSWORD:
        logger.warning(
            "DB_PASSWORD is not set – running without database. "
            "Auth endpoints will use in-memory storage."
        )
        _db_available = False
        return False

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(_INIT_SQL)
        _db_available = True
        logger.info("Database tables verified / created successfully.")
        return True
    except Exception as exc:
        logger.warning("Could not connect to RDS (%s). Using in-memory fallback.", exc)
        _db_available = False
        return False


def is_db_available() -> bool:
    return _db_available
