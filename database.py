"""Database connection helpers for the Job Application Tracker.

Connection settings come from environment variables (or a .env file)
so no password is hard-coded in the source:

    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
"""

import os

import mysql.connector

try:  # python-dotenv is optional; load .env if it is installed
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "job_tracker"),
}


def get_db():
    """Open and return a new MySQL connection."""
    return mysql.connector.connect(**DB_CONFIG)


def query_all(sql, params=None):
    """Run a SELECT and return every row as a dict."""
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params or ())
        return cursor.fetchall()
    finally:
        conn.close()


def query_one(sql, params=None):
    """Run a SELECT and return the first row as a dict (or None)."""
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params or ())
        return cursor.fetchone()
    finally:
        conn.close()


def execute(sql, params=None):
    """Run an INSERT/UPDATE/DELETE, commit, and return the last insert id."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()
