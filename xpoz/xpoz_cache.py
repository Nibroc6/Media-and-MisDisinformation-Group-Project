"""
xpoz_cache.py — SQLite-backed cache for xpoz API responses.

Cached call types
-----------------
  get_user(username)                    → user profile dict
  get_user_connections(username, type)  → list of user profile dicts (full paginated result)
  search_posts(author, phrase, ...)     → list of post-row dicts

Cache entries record their fetch timestamp so you can set per-type TTLs and
force-refresh stale data without nuking the whole database.

Usage
-----
    from xpoz_cache import XpozCache

    cache = XpozCache("xpoz_cache.db")          # opens / creates the DB
    cache = XpozCache("xpoz_cache.db", debug=True)

    # --- user profile ---
    hit = cache.get_user("realDonaldTrump")
    if hit is None:
        user = client.twitter.get_user(...)
        cache.set_user(user)

    # --- connections (full paginated list, stored as one blob) ---
    hit = cache.get_connections("realDonaldTrump", "following", limit=100)
    if hit is None:
        pages = ...
        cache.set_connections("realDonaldTrump", "following", limit=100, items=pages)

    # --- post search ---
    hit = cache.get_posts("realDonaldTrump", "tylenol", start=None, end=None,
                          include_retweets=False, limit=20)
    if hit is None:
        rows = search_author_posts(...)
        cache.set_posts("realDonaldTrump", "tylenol", ..., rows=rows)

    cache.close()

Or use it as a context manager:

    with XpozCache("xpoz_cache.db") as cache:
        ...

TTLs
----
Pass ttl_users / ttl_connections / ttl_posts (seconds) to the constructor.
None (default) means "never expire".  Use 0 to disable caching for a type.

    cache = XpozCache("xpoz_cache.db",
                      ttl_users=86_400,        # 1 day
                      ttl_connections=3_600,   # 1 hour
                      ttl_posts=None)          # forever
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    username    TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,           -- JSON dict
    fetched_at  REAL NOT NULL
)
"""

_CREATE_CONNECTIONS = """
CREATE TABLE IF NOT EXISTS connections (
    cache_key   TEXT PRIMARY KEY,        -- username|type|limit
    payload     TEXT NOT NULL,           -- JSON array of user-profile dicts
    fetched_at  REAL NOT NULL
)
"""

_CREATE_POSTS = """
CREATE TABLE IF NOT EXISTS posts (
    cache_key   TEXT PRIMARY KEY,        -- username|phrase|start|end|retweets|limit
    payload     TEXT NOT NULL,           -- JSON array of post-row dicts
    fetched_at  REAL NOT NULL
)
"""

_CREATE_META = """
CREATE TABLE IF NOT EXISTS meta (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
)
"""

_SCHEMA_VERSION = "1"


def _connections_key(username: str, connection_type: str, limit: int) -> str:
    return f"{username.lower()}|{connection_type}|{limit}"


def _posts_key(
    username: str,
    phrase: str,
    start_date: str | None,
    end_date: str | None,
    include_retweets: bool,
    limit: int,
) -> str:
    parts = [
        username.lower(),
        phrase.lower(),
        start_date or "",
        end_date or "",
        "rt" if include_retweets else "nort",
        str(limit),
    ]
    return "|".join(parts)


def _is_fresh(fetched_at: float, ttl: float | None) -> bool:
    if ttl is None:
        return True
    return (time.time() - fetched_at) < ttl


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class XpozCache:
    """Persistent SQLite cache for xpoz API responses.

    Parameters
    ----------
    db_path:
        File path for the SQLite database.  Pass ":memory:" for an in-process
        cache that still matches the same interface but doesn't survive the run.
    ttl_users:
        Seconds before a cached user profile is considered stale.  ``None``
        means never expire.
    ttl_connections:
        Seconds before a cached connection list is considered stale.
    ttl_posts:
        Seconds before cached post-search results are considered stale.
    debug:
        Print cache hit/miss messages.
    """

    def __init__(
        self,
        db_path: str | Path = "xpoz_cache.db",
        *,
        ttl_users: float | None = None,
        ttl_connections: float | None = None,
        ttl_posts: float | None = None,
        debug: bool = False,
    ) -> None:
        self._db_path = str(db_path)
        self._ttl_users = ttl_users
        self._ttl_connections = ttl_connections
        self._ttl_posts = ttl_posts
        self._debug = debug

        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._migrate()

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "XpozCache":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    def _migrate(self) -> None:
        cur = self._conn
        cur.execute(_CREATE_USERS)
        cur.execute(_CREATE_CONNECTIONS)
        cur.execute(_CREATE_POSTS)
        cur.execute(_CREATE_META)
        cur.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
            ("schema_version", _SCHEMA_VERSION),
        )
        cur.commit()

    # ------------------------------------------------------------------
    # User profiles
    # ------------------------------------------------------------------

    def get_user(self, username: str) -> dict | None:
        """Return a cached user-profile dict or ``None`` on miss/expiry."""
        row = self._conn.execute(
            "SELECT payload, fetched_at FROM users WHERE username = ?",
            (username.lower(),),
        ).fetchone()
        if row is None:
            self._dlog(f"MISS  user:{username}")
            return None
        payload, fetched_at = row
        if not _is_fresh(fetched_at, self._ttl_users):
            self._dlog(f"STALE user:{username}")
            return None
        self._dlog(f"HIT   user:{username}")
        return json.loads(payload)

    def set_user(self, user: Any) -> None:
        """Cache a user object returned by ``client.twitter.get_user()``.

        Accepts either an xpoz user object (with attribute access) or a plain dict.
        """
        d = _user_to_dict(user)
        username = (d.get("username") or "").lower()
        if not username:
            return
        self._conn.execute(
            "INSERT OR REPLACE INTO users(username, payload, fetched_at) VALUES (?,?,?)",
            (username, json.dumps(d), time.time()),
        )
        self._conn.commit()
        self._dlog(f"SET   user:{username}")

    # ------------------------------------------------------------------
    # Connection lists (following / followers)
    # ------------------------------------------------------------------

    def get_connections(
        self,
        username: str,
        connection_type: str,
        limit: int,
    ) -> list[dict] | None:
        """Return a cached list of user-profile dicts or ``None`` on miss/expiry."""
        key = _connections_key(username, connection_type, limit)
        row = self._conn.execute(
            "SELECT payload, fetched_at FROM connections WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            self._dlog(f"MISS  connections:{key}")
            return None
        payload, fetched_at = row
        if not _is_fresh(fetched_at, self._ttl_connections):
            self._dlog(f"STALE connections:{key}")
            return None
        self._dlog(f"HIT   connections:{key}")
        return json.loads(payload)

    def set_connections(
        self,
        username: str,
        connection_type: str,
        limit: int,
        items: list[Any],
    ) -> None:
        """Cache the full paginated connection list.

        ``items`` may be a list of xpoz user objects or plain dicts.
        """
        key = _connections_key(username, connection_type, limit)
        serialisable = [_user_to_dict(u) for u in items]
        self._conn.execute(
            "INSERT OR REPLACE INTO connections(cache_key, payload, fetched_at) VALUES (?,?,?)",
            (key, json.dumps(serialisable), time.time()),
        )
        self._conn.commit()
        self._dlog(f"SET   connections:{key} ({len(serialisable)} items)")

    # ------------------------------------------------------------------
    # Post-search results
    # ------------------------------------------------------------------

    def get_posts(
        self,
        username: str,
        phrase: str,
        start_date: str | None,
        end_date: str | None,
        include_retweets: bool,
        limit: int,
    ) -> list[dict] | None:
        """Return cached post-row dicts or ``None`` on miss/expiry."""
        key = _posts_key(username, phrase, start_date, end_date, include_retweets, limit)
        row = self._conn.execute(
            "SELECT payload, fetched_at FROM posts WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            self._dlog(f"MISS  posts:{key}")
            return None
        payload, fetched_at = row
        if not _is_fresh(fetched_at, self._ttl_posts):
            self._dlog(f"STALE posts:{key}")
            return None
        self._dlog(f"HIT   posts:{key}")
        return json.loads(payload)

    def set_posts(
        self,
        username: str,
        phrase: str,
        start_date: str | None,
        end_date: str | None,
        include_retweets: bool,
        limit: int,
        rows: list[dict],
    ) -> None:
        """Cache the post-row dicts produced by ``search_author_posts()``."""
        key = _posts_key(username, phrase, start_date, end_date, include_retweets, limit)
        self._conn.execute(
            "INSERT OR REPLACE INTO posts(cache_key, payload, fetched_at) VALUES (?,?,?)",
            (key, json.dumps(rows), time.time()),
        )
        self._conn.commit()
        self._dlog(f"SET   posts:{key} ({len(rows)} rows)")

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def invalidate_user(self, username: str) -> None:
        self._conn.execute(
            "DELETE FROM users WHERE username = ?", (username.lower(),)
        )
        self._conn.commit()

    def invalidate_connections(
        self, username: str, connection_type: str, limit: int
    ) -> None:
        key = _connections_key(username, connection_type, limit)
        self._conn.execute("DELETE FROM connections WHERE cache_key = ?", (key,))
        self._conn.commit()

    def purge_stale(self) -> tuple[int, int, int]:
        """Delete all expired rows (requires TTLs to be set).

        Returns (users_deleted, connections_deleted, posts_deleted).
        """
        now = time.time()
        u = c = p = 0
        if self._ttl_users is not None:
            cur = self._conn.execute(
                "DELETE FROM users WHERE ? - fetched_at > ?",
                (now, self._ttl_users),
            )
            u = cur.rowcount
        if self._ttl_connections is not None:
            cur = self._conn.execute(
                "DELETE FROM connections WHERE ? - fetched_at > ?",
                (now, self._ttl_connections),
            )
            c = cur.rowcount
        if self._ttl_posts is not None:
            cur = self._conn.execute(
                "DELETE FROM posts WHERE ? - fetched_at > ?",
                (now, self._ttl_posts),
            )
            p = cur.rowcount
        self._conn.commit()
        return u, c, p

    def stats(self) -> dict:
        """Return row counts and DB file size."""
        users = self._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conns = self._conn.execute("SELECT COUNT(*) FROM connections").fetchone()[0]
        posts = self._conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        size_bytes = (
            Path(self._db_path).stat().st_size
            if self._db_path != ":memory:"
            else 0
        )
        return {
            "users": users,
            "connections": conns,
            "posts": posts,
            "db_size_bytes": size_bytes,
            "db_size_mb": round(size_bytes / 1_048_576, 2),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _dlog(self, msg: str) -> None:
        if self._debug:
            print(f"[cache] {msg}")


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _user_to_dict(user: Any) -> dict:
    """Convert an xpoz user object or plain dict into a JSON-safe dict."""
    if isinstance(user, dict):
        return user
    # xpoz user object — pull known fields via getattr with None fallback
    return {
        "id": getattr(user, "id", None),
        "username": getattr(user, "username", None),
        "name": getattr(user, "name", None),
        "followers_count": getattr(user, "followers_count", None),
        "following_count": getattr(user, "following_count", None),
        "verified": getattr(user, "verified", None),
    }


class _FakeUser:
    """Lightweight stand-in for an xpoz user object, reconstructed from cache."""

    __slots__ = ("id", "username", "name", "followers_count", "following_count", "verified")

    def __init__(self, d: dict) -> None:
        self.id = d.get("id")
        self.username = d.get("username")
        self.name = d.get("name")
        self.followers_count = d.get("followers_count")
        self.following_count = d.get("following_count")
        self.verified = d.get("verified")


def dicts_to_fake_users(dicts: list[dict]) -> list[_FakeUser]:
    """Reconstruct fake xpoz user objects from cached dicts.

    Use this when existing code expects attribute-access user objects rather
    than plain dicts.

        cached = cache.get_connections(username, "following", limit)
        if cached is not None:
            users = dicts_to_fake_users(cached)
        else:
            users = fetch_connections(client, username, "following", limit, debug)
            cache.set_connections(username, "following", limit, users)
    """
    return [_FakeUser(d) for d in dicts]
