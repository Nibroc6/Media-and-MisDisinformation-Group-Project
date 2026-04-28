import sqlite3
import json
from config import DB_PATH

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    with open("schema.sql", "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

def upsert_user(user_data):
    """
    Insert or replace a user record. Keeps the most recent metadata.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO users (
            id, username, display_name, created_at, 
            followers_count, following_count, statuses_count, raw_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_data.get("id"),
        user_data.get("username"),
        user_data.get("display_name"),
        user_data.get("created_at"),
        user_data.get("followers_count"),
        user_data.get("following_count"),
        user_data.get("statuses_count"),
        json.dumps(user_data)
    ))
    conn.commit()
    conn.close()

def upsert_post(post_data, author_id, source_tag=None):
    """
    Insert or ignore a post.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR IGNORE INTO posts (
            id, author_id, content, created_at,
            reblogs_count, replies_count, favourites_count, source_tag, raw_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        post_data.get("id"),
        author_id,
        post_data.get("content"),
        post_data.get("created_at"),
        post_data.get("reblogs_count"),
        post_data.get("replies_count"),
        post_data.get("favourites_count"),
        source_tag,
        json.dumps(post_data)
    ))
    conn.commit()
    conn.close()

def insert_edge(source_user_id, target_user_id, post_id, interaction_type, source_tag=None):
    """
    Insert an interaction edge between two users for the network map.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR IGNORE INTO edges (
            source_user_id, target_user_id, post_id, interaction_type, source_tag
        ) VALUES (?, ?, ?, ?, ?)
    """, (
        source_user_id,
        target_user_id,
        post_id,
        interaction_type,
        source_tag
    ))
    conn.commit()
    conn.close()

def post_exists(post_id):
    """
    Check if a post already exists in the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM posts WHERE id = ?", (post_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists
