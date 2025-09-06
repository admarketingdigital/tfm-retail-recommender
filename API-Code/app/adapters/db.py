# app/adapters/db.py
import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import settings

def get_conn():
    return psycopg2.connect(
        host=settings.pg_host,
        port=settings.pg_port,
        dbname=settings.pg_db,
        user=settings.pg_user,
        password=settings.pg_password,
    )

def ping() -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return True
    except Exception:
        return False

def table_exists(schema: str, table: str) -> bool:
    # Busca en information_schema sin crear nada
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = %s
                    LIMIT 1;
                """, ("public", table))
                return cur.fetchone() is not None
    except Exception:
        return False