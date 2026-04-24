"""
seed_cache_from_json.py — Pre-populate xpoz_cache.db from a network_map.py JSON output.

This lets you avoid redundant API calls when re-running network_map.py or
trace_phrase.py on a network you've already mapped.

What gets seeded
----------------
  users table       — one row per node in the JSON
  connections table — one row per node's outgoing edges, reconstructed as a
                      "following" list capped at the original per_account_limit

Usage
-----
    python seed_cache_from_json.py trump_network_map/realDonaldTrump_follow_network.json

    # Point at a different cache file:
    python seed_cache_from_json.py network.json --cache-db my_cache.db

    # Dry run — show what would be written without touching the DB:
    python seed_cache_from_json.py network.json --dry-run

    # Override TTLs (seconds). Omit to keep entries forever.
    python seed_cache_from_json.py network.json --ttl-users 86400 --ttl-connections 3600

    # Suppress progress output:
    python seed_cache_from_json.py network.json --quiet

What it does NOT seed
---------------------
  - posts table  (phrase-search results are phrase-specific; the JSON doesn't
                  contain them)
  - followers    (the JSON only records "following" direction)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from xpoz_cache import XpozCache, _FakeUser


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Pre-populate xpoz_cache.db from a network_map.py JSON file so that "
            "subsequent network_map.py / trace_phrase.py runs skip redundant API calls."
        )
    )
    parser.add_argument(
        "network_json",
        help="Path to the JSON produced by network_map.py.",
    )
    parser.add_argument(
        "--cache-db",
        default="xpoz_cache.db",
        help="Path to the SQLite cache database (default: xpoz_cache.db).",
    )
    parser.add_argument(
        "--ttl-users",
        type=float,
        default=None,
        metavar="SECONDS",
        help="TTL for seeded user rows. Omit to keep forever.",
    )
    parser.add_argument(
        "--ttl-connections",
        type=float,
        default=None,
        metavar="SECONDS",
        help="TTL for seeded connection rows. Omit to keep forever.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without touching the database.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-row progress messages.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(quiet: bool, msg: str) -> None:
    if not quiet:
        print(msg)


def node_to_user_dict(node: dict) -> dict:
    """Convert a network_map node dict into the shape xpoz_cache.set_user expects."""
    username = node.get("username") or ""
    return {
        "id": node.get("id") or username,
        "username": username,
        "name": node.get("label") or node.get("name") or username,
        "followers_count": node.get("followers_count"),
        "following_count": node.get("following_count"),
        "verified": bool(node.get("verified")),
    }


def build_following_map(
    edges: list[dict],
    nodes_by_username: dict[str, dict],
) -> dict[str, list[dict]]:
    """
    Reconstruct a {username: [user_dict, ...]} following map from the edge list.

    Only "seed_follows" and "follow_back_within_seed" edges are used — both
    represent A following B within the captured network.
    """
    following: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)

    for edge in edges:
        source = edge.get("source", "")
        target = edge.get("target", "")
        if not source or not target:
            continue
        if target in seen[source]:
            continue
        seen[source].add(target)
        if target in nodes_by_username:
            following[source].append(nodes_by_username[target])

    return dict(following)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    json_path = Path(args.network_json)
    if not json_path.exists():
        sys.exit(f"Error: file not found: {json_path}")

    print(f"Loading {json_path} …")
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    nodes: list[dict] = payload.get("nodes", [])
    edges: list[dict] = payload.get("edges", [])
    seed_username: str = payload.get("seed_username", "")
    seed_limit: int = payload.get("seed_limit", 0)
    per_account_limit: int = payload.get("per_account_limit", 0)

    print(
        f"  seed_username      : @{seed_username}\n"
        f"  nodes              : {len(nodes)}\n"
        f"  edges              : {len(edges)}\n"
        f"  seed_limit         : {seed_limit}\n"
        f"  per_account_limit  : {per_account_limit}\n"
    )

    # Index nodes by username for fast lookup
    nodes_by_username: dict[str, dict] = {}
    for node in nodes:
        username = (node.get("username") or "").strip()
        if username:
            nodes_by_username[username] = node_to_user_dict(node)

    # Reconstruct following lists from edges
    following_map = build_following_map(edges, nodes_by_username)

    if args.dry_run:
        print("=== DRY RUN — nothing will be written ===\n")
        print(f"Would seed {len(nodes_by_username)} users into the users table.")
        print(f"Would seed {len(following_map)} connection lists into the connections table.")
        print("\nConnection list sizes:")
        for username, targets in sorted(following_map.items()):
            # Determine the limit that would be used as the cache key
            if username == seed_username:
                limit_used = seed_limit or len(targets)
            else:
                limit_used = per_account_limit or len(targets)
            print(f"  @{username:<30} → {len(targets):>3} following  (key limit={limit_used})")
        return

    # Open cache
    cache = XpozCache(
        args.cache_db,
        ttl_users=args.ttl_users,
        ttl_connections=args.ttl_connections,
        debug=False,
    )

    now = time.time()
    users_written = 0
    connections_written = 0

    # --- Seed users ---
    print("Seeding users …")
    for username, user_dict in nodes_by_username.items():
        fake = _FakeUser(user_dict)
        cache.set_user(fake)
        users_written += 1
        log(args.quiet, f"  [user] @{username}")

    # --- Seed connection lists ---
    print("Seeding connection lists …")
    for username, targets in following_map.items():
        # Use the same limit value that network_map.py would have used so the
        # cache key matches future lookups exactly.
        if username == seed_username:
            limit_used = seed_limit if seed_limit > 0 else len(targets)
        else:
            limit_used = per_account_limit if per_account_limit > 0 else len(targets)

        # Clamp to however many we actually have
        limit_used = max(limit_used, len(targets))

        fake_users = [_FakeUser(t) for t in targets]
        cache.set_connections(username, "following", limit_used, fake_users)
        connections_written += 1
        log(args.quiet, f"  [connections] @{username:<30} → {len(targets):>3} entries  (key limit={limit_used})")

    cache.close()

    print(
        f"\nDone.\n"
        f"  Users written       : {users_written}\n"
        f"  Connection lists    : {connections_written}\n"
        f"  Cache DB            : {args.cache_db}\n"
    )

    # Print final stats
    verify = XpozCache(args.cache_db)
    print(f"  DB stats            : {verify.stats()}")
    verify.close()


if __name__ == "__main__":
    main()