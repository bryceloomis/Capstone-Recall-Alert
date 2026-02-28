"""
Database connection module for Food Recall Alert.
Connects to AWS RDS PostgreSQL using credentials from .env file.
"""
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":            os.getenv("DB_HOST", "food-recall-db.cqjm48os4obt.us-east-1.rds.amazonaws.com"),
    "port":            int(os.getenv("DB_PORT", "5432")),
    "dbname":          os.getenv("DB_NAME", "food_recall"),
    "user":            os.getenv("DB_USER", "postgres"),
    "password":        os.getenv("DB_PASSWORD"),
    "sslmode":         os.getenv("DB_SSLMODE", "verify-full"),
    "sslrootcert":     os.getenv("DB_SSLROOTCERT", "/certs/global-bundle.pem"),
}


def get_db_connection():
    """Open and return a new database connection."""
    return psycopg2.connect(**DB_CONFIG)


def test_connection() -> bool:
    """Return True if the database is reachable, False otherwise."""
    try:
        conn = get_db_connection()
        conn.close()
        print("Database connection successful!")
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


def execute_query(query: str, params=None):
    """
    Execute a SQL query, always commit, and return results as a list of dicts.

    - SELECT queries: commit is a no-op, returns rows.
    - INSERT/UPDATE/DELETE without RETURNING: returns [].
    - INSERT/UPDATE with RETURNING: fetches and returns the returned rows.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            results = [dict(row) for row in cur.fetchall()] if cur.description else []
            conn.commit()
            return results
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
