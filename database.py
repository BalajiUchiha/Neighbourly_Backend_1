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
    try:
        yield conn
    finally:
        connection_pool.putconn(conn)

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
