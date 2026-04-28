"""
Database connector for the visualization dashboard.
Provides safe, optimized queries for network analysis and aggregation.
"""
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "cache.db")


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Ensures connections are properly closed.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def execute_query(query, params=None):
    """
    Execute a SELECT query and return results as list of dicts.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        columns = [description[0] for description in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        return results


def execute_query_single(query, params=None):
    """
    Execute a SELECT query and return first result as dict.
    """
    results = execute_query(query, params)
    return results[0] if results else None


def get_db_stats():
    """
    Get basic statistics about the database.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM users")
        user_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM posts")
        post_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM edges")
        edge_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT MIN(created_at) as min_date, MAX(created_at) as max_date FROM posts")
        date_range = dict(cursor.fetchone())
        
        return {
            "user_count": user_count,
            "post_count": post_count,
            "edge_count": edge_count,
            "date_range": date_range
        }
