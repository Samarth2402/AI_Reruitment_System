"""
db.py – PostgreSQL connection helper (Render)
Install: pip install psycopg2-binary
"""

import psycopg2
import psycopg2.extras
import os


def get_conn():
    """Return PostgreSQL connection (DictCursor)."""
    return psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )


# ─── Generic helpers ────────────────────────────────────────

def fetchall(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    finally:
        conn.close()


def fetchone(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()
    finally:
        conn.close()


def execute(sql, params=None):
    """INSERT / UPDATE / DELETE – returns lastrowid."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            conn.commit()
            return cur.rowcount
    finally:
        conn.close()


def executemany(sql, seq):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, seq)
            conn.commit()
    finally:
        conn.close()
