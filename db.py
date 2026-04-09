"""
db.py  –  MySQL connection helper using PyMySQL
Install: pip install pymysql cryptography
"""

import pymysql
import pymysql.cursors
import os

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", "Samarth@1009"),        # ← set your MySQL password
    "database": os.getenv("DB_NAME",     "ai_recruitment"),
    "charset":  "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}


def get_conn():
    """Return a fresh PyMySQL connection (DictCursor)."""
    return pymysql.connect(**DB_CONFIG)


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
            return cur.lastrowid
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
