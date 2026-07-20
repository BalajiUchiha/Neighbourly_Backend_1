import psycopg2
from psycopg2 import pool
import os
from dotenv import load_dotenv

load_dotenv()

connection_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=os.getenv("DATABASE_URL")
)

def get_db():
    conn = connection_pool.getconn()
    # Check if connection is dead
    try:
        if conn.closed != 0:
            raise psycopg2.InterfaceError("Connection is closed")
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    except (psycopg2.OperationalError, psycopg2.InterfaceError, psycopg2.DatabaseError):
        # Connection is dead, try to get a new one
        try:
            connection_pool.putconn(conn, close=True)
        except Exception:
            pass
        conn = connection_pool.getconn()
    
    try:
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            connection_pool.putconn(conn)
        except Exception:
            pass


def execute_query(conn, query: str, params=None, fetch=None):
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        if fetch == "one":
            row = cur.fetchone()
            if row and cur.description:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
            return None
        elif fetch == "all":
            rows = cur.fetchall()
            if rows and cur.description:
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in rows]
            return []
        else:
            conn.commit()
            return None
