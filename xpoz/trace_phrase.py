import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from xpoz import XpozClient
from xpoz._config import _tools

from xpoz_cache import XpozCache, dicts_to_fake_users

# XPOZ_API_KEY=... ./.venv/bin/python trace_phrase.py realDonaldTrump "tylenol" \
#   --network-json network_map_output2/realDonaldTrump_follow_network.json \
#   --output-dir trump_phrase_trace_test2 --debug

USER_FIELDS = [
    "id",
    "username",
    "name",
    "followers_count",
    "following_count",
    "verified",
]

POST_FIELDS = [
    "id",
    "text",
    "author_id",
    "author_username",
    "created_at",
    "created_at_date",
    "like_count",
    "retweet_count",
    "reply_count",
    "quote_count",
    "impression_count",
    "is_retweet",
    "retweeted_tweet_id",
    "quoted_tweet_id",
    "reply_to_tweet_id",
    "urls",
]


class FlexibleTwitterPost(BaseModel, extra="allow"):
    id: Any = None
    text: Any = None
    author_id: Any = None
    author_username: Any = None
    created_at: Any = None
    created_at_date: Any = None
    like_count: Any = None
    retweet_count: Any = None
    reply_count: Any = None
    quote_count: Any = None
    impression_count: Any = None
    is_retweet: Any = None
    retweeted_tweet_id: Any = None
    quoted_tweet_id: Any = None
    reply_to_tweet_id: Any = None
    urls: Any = None


def debug_log(enabled: bool, message: str) -> None:
    if enabled:
        print(f"[debug] {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Search for an exact phrase across a seed user's following network. "
            "The script searches the seed, accounts they follow, and accounts those "
            "first-degree accounts follow."
        )
    )
    parser.add_argument("username", help="Seed username, without the @")
    parser.add_argument("phrase", help="Exact phrase to search for")
    parser.add_argument(
        "--api-key",
        default=os.getenv("XPOZ_API_KEY"),
        help="xpoz API key. Defaults to the XPOZ_API_KEY environment variable.",
    )
    parser.add_argument(
        "--seed-limit",
        type=int,
        default=25,
        help="Maximum number of accounts to pull from the seed user's following list.",
    )
    parser.add_argument(
        "--per-account-limit",
        type=int,
        default=100,
        help="Maximum following records to inspect for each first-degree account.",
    )
    parser.add_argument(
        "--posts-per-author",
        type=int,
        default=20,
        help="Maximum matching posts to collect per author.",
    )
    parser.add_argument(
        "--max-authors",
        type=int,
        default=500,
        help="Maximum unique authors to search after building the network sample.",
    )
    parser.add_argument(
        "--start-date",
        help="Optional search start date, for example 2025-01-01.",
    )
    parser.add_argument(
        "--end-date",
        help="Optional search end date, for example 2025-12-31.",
    )
    parser.add_argument(
        "--output-dir",
        default="phrase_trace_output",
        help="Directory for generated JSON and CSV files.",
    )
    parser.add_argument(
        "--network-json",
        help=(
            "Path to a JSON file created by network_map.py. When provided, "
            "the script reuses that author network instead of rebuilding it."
        ),
    )
    parser.add_argument(
        "--include-retweets",
        action="store_true",
        help="Include retweets in search results. By default retweets are filtered out.",
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
        help="Max age in seconds for cached user profiles. Omit to keep forever.",
    )
    parser.add_argument(
        "--ttl-connections",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Max age in seconds for cached connection lists. Omit to keep forever.",
    )
    parser.add_argument(
        "--ttl-posts",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Max age in seconds for cached post search results. Omit to keep forever.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable the cache for this run (always hits the API).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print detailed progress logs while building the trace.",
    )
    return parser.parse_args()


def safe_slug(value: str) -> str:
    keep = []
    for char in value.lower():
        if char.isalnum():
            keep.append(char)
        elif keep and keep[-1] != "_":
            keep.append("_")
    return "".join(keep).strip("_")[:80] or "phrase"


def fetch_connections(
    client: XpozClient,
    cache: XpozCache | None,
    username: str,
    connection_type: str,
    limit: int,
    debug: bool,
) -> list:
    """Fetch paginated connections, consulting the cache first."""
    if limit <= 0:
        return []

    # --- cache read ---
    if cache is not None:
        cached = cache.get_connections(username, connection_type, limit)
        if cached is not None:
            debug_log(debug, f"Cache hit: {connection_type} for @{username} ({len(cached)} items).")
            return dicts_to_fake_users(cached)

    debug_log(debug, f"Fetching up to {limit} {connection_type} for @{username}.")
    page = client.twitter.get_user_connections(
        username,
        connection_type,
        fields=USER_FIELDS,
    )
    items = list(page.data)
    debug_log(
        debug,
        (
            f"@{username} {connection_type} page {page.pagination.page_number}"
            f"/{page.pagination.total_pages or '?'}: {len(page.data)} records."
        ),
    )

    while len(items) < limit and page.has_next_page():
        page = page.next_page()
        items.extend(page.data)
        debug_log(
            debug,
            (
                f"@{username} {connection_type} page {page.pagination.page_number}"
                f"/{page.pagination.total_pages or '?'}: {len(page.data)} records."
            ),
        )

    trimmed = items[:limit]

    # --- cache write ---
    if cache is not None:
        cache.set_connections(username, connection_type, limit, trimmed)

    return trimmed


def user_row(user, role: str, discovered_from: str | None) -> dict:
    username = user.username or ""
    return {
        "id": user.id or username,
        "username": username,
        "name": user.name or username,
        "followers_count": user.followers_count,
        "following_count": user.following_count,
        "verified": bool(user.verified),
        "role": role,
        "discovered_from": discovered_from or "",
    }


def build_author_sample(
    client: XpozClient,
    cache: XpozCache | None,
    seed_username: str,
    seed_limit: int,
    per_account_limit: int,
    max_authors: int,
    debug: bool,
) -> tuple[dict[str, dict], list[dict]]:
    # --- cached seed user lookup ---
    seed_user = None
    if cache is not None:
        cached_user = cache.get_user(seed_username)
        if cached_user is not None:
            from xpoz_cache import _FakeUser
            seed_user = _FakeUser(cached_user)

    if seed_user is None:
        seed_user = client.twitter.get_user(seed_username, fields=USER_FIELDS)
        if cache is not None:
            cache.set_user(seed_user)

    resolved_seed = seed_user.username or seed_username
    authors: dict[str, dict] = {
        resolved_seed: user_row(seed_user, "seed", None),
    }
    edges: list[dict] = []

    first_degree = fetch_connections(
        client,
        cache,
        resolved_seed,
        "following",
        seed_limit,
        debug,
    )
    debug_log(debug, f"Collected {len(first_degree)} first-degree accounts.")

    for user in first_degree:
        if not user.username:
            continue
        authors[user.username] = user_row(user, "seed_following", resolved_seed)
        edges.append(
            {
                "source": resolved_seed,
                "target": user.username,
                "type": "seed_follows",
            }
        )

    for index, user in enumerate(first_degree, start=1):
        if len(authors) >= max_authors:
            debug_log(debug, f"Reached max author sample size of {max_authors}.")
            break
        if not user.username:
            continue

        debug_log(
            debug,
            f"Expanding @{user.username} ({index}/{len(first_degree)} first-degree accounts).",
        )
        second_degree = fetch_connections(
            client,
            cache,
            user.username,
            "following",
            per_account_limit,
            debug,
        )
        for neighbor in second_degree:
            if len(authors) >= max_authors:
                break
            if not neighbor.username:
                continue
            if neighbor.username not in authors:
                authors[neighbor.username] = user_row(
                    neighbor,
                    "followed_by_seed_following",
                    user.username,
                )
            edges.append(
                {
                    "source": user.username,
                    "target": neighbor.username,
                    "type": "second_degree_follows",
                }
            )

    deduped_edges = list(
        {
            (edge["source"], edge["target"], edge["type"]): edge
            for edge in edges
        }.values()
    )
    return authors, deduped_edges


def load_author_sample_from_network_json(
    path: Path,
    max_authors: int,
    debug: bool,
) -> tuple[str | None, dict[str, dict], list[dict]]:
    debug_log(debug, f"Loading existing network map from {path}.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])
    seed_username = payload.get("seed_username")

    discovered_from_by_username: dict[str, str] = {}
    for edge in edges:
        target = edge.get("target")
        source = edge.get("source")
        if target and source:
            discovered_from_by_username.setdefault(target, source)

    authors: dict[str, dict] = {}
    for node in nodes:
        username = node.get("username")
        if not username:
            continue
        authors[username] = {
            "id": node.get("id") or username,
            "username": username,
            "name": node.get("name") or node.get("label") or username,
            "followers_count": node.get("followers_count"),
            "following_count": node.get("following_count"),
            "verified": bool(node.get("verified")),
            "role": node.get("role") or ("seed" if username == seed_username else "network_node"),
            "discovered_from": discovered_from_by_username.get(username, ""),
        }
        if len(authors) >= max_authors:
            debug_log(debug, f"Reached max author sample size of {max_authors}.")
            break

    network_edges = [
        {
            "source": edge.get("source", ""),
            "target": edge.get("target", ""),
            "type": edge.get("type", ""),
        }
        for edge in edges
        if edge.get("source") and edge.get("target")
    ]
    debug_log(
        debug,
        f"Loaded {len(authors)} authors and {len(network_edges)} edges from existing map.",
    )
    return seed_username, authors, network_edges


def exact_query(phrase: str) -> str:
    escaped = phrase.replace('"', '\\"')
    return f'"{escaped}"'


def normalize_datetime(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    return str(value)


def to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def post_row(post, searched_author: str, phrase: str) -> dict:
    text = str(post.text or "")
    author_username = str(post.author_username or searched_author)
    post_id = str(post.id or "")
    return {
        "post_id": post_id,
        "author_username": author_username,
        "searched_author": searched_author,
        "created_at": normalize_datetime(post.created_at),
        "created_at_date": normalize_datetime(post.created_at_date),
        "text": text,
        "contains_exact_phrase": phrase.lower() in text.lower(),
        "like_count": to_int(post.like_count),
        "retweet_count": to_int(post.retweet_count),
        "reply_count": to_int(post.reply_count),
        "quote_count": to_int(post.quote_count),
        "impression_count": to_int(post.impression_count),
        "is_retweet": bool(post.is_retweet),
        "retweeted_tweet_id": str(post.retweeted_tweet_id or ""),
        "quoted_tweet_id": str(post.quoted_tweet_id or ""),
        "reply_to_tweet_id": str(post.reply_to_tweet_id or ""),
        "urls": json.dumps(post.urls or []),
        "post_url": (
            f"https://x.com/{author_username}/status/{post_id}"
            if post_id
            else ""
        ),
    }


def search_author_posts(
    client: XpozClient,
    cache: XpozCache | None,
    author_username: str,
    phrase: str,
    posts_per_author: int,
    start_date: str | None,
    end_date: str | None,
    include_retweets: bool,
    debug: bool,
) -> list[dict]:
    if posts_per_author <= 0:
        return []

    # --- cache read ---
    if cache is not None:
        cached = cache.get_posts(
            author_username, phrase, start_date, end_date, include_retweets, posts_per_author
        )
        if cached is not None:
            debug_log(debug, f"Cache hit: posts for @{author_username} phrase={phrase!r} ({len(cached)} rows).")
            return cached

    query = exact_query(phrase)
    debug_log(debug, f"Searching @{author_username} for {query}.")
    args = client.twitter._build_args(
        query=query,
        fields=client.twitter._convert_fields(POST_FIELDS),
        startDate=start_date,
        endDate=end_date,
        authorUsername=author_username,
        filterOutRetweets=not include_retweets,
        limit=posts_per_author,
    )
    raw_result = client.twitter._call_and_maybe_poll(_tools.SEARCH_TWITTER_POSTS, args)
    page = client.twitter._build_paginated_result(
        raw_result,
        FlexibleTwitterPost,
        _tools.SEARCH_TWITTER_POSTS,
        args,
    )
    posts = list(page.data)

    while len(posts) < posts_per_author and page.has_next_page():
        page = page.next_page()
        posts.extend(page.data)

    rows = [
        post_row(post, author_username, phrase)
        for post in posts[:posts_per_author]
    ]
    debug_log(debug, f"Found {len(rows)} matching posts for @{author_username}.")

    # --- cache write ---
    if cache is not None:
        cache.set_posts(
            author_username, phrase, start_date, end_date, include_retweets, posts_per_author, rows
        )

    return rows


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    if not args.api_key:
        raise SystemExit("Missing API key. Pass --api-key or set XPOZ_API_KEY.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cache: XpozCache | None = None
    if not args.no_cache:
        cache = XpozCache(
            args.cache_db,
            ttl_users=args.ttl_users,
            ttl_connections=args.ttl_connections,
            ttl_posts=args.ttl_posts,
            debug=args.debug,
        )
        if args.debug:
            print(f"[cache] opened {args.cache_db!r}  stats={cache.stats()}")

    client = XpozClient(args.api_key)
    try:
        if args.network_json:
            loaded_seed_username, authors, network_edges = load_author_sample_from_network_json(
                Path(args.network_json),
                args.max_authors,
                args.debug,
            )
            seed_username = loaded_seed_username or args.username
        else:
            debug_log(args.debug, f"Building author sample from @{args.username}.")
            authors, network_edges = build_author_sample(
                client,
                cache,
                args.username,
                args.seed_limit,
                args.per_account_limit,
                args.max_authors,
                args.debug,
            )
            seed_username = args.username

        all_posts: list[dict] = []
        author_items = sorted(authors.items())
        for index, (username, author) in enumerate(author_items, start=1):
            debug_log(
                args.debug,
                f"Searching author {index}/{len(author_items)}: @{username} ({author['role']}).",
            )
            try:
                all_posts.extend(
                    search_author_posts(
                        client,
                        cache,
                        username,
                        args.phrase,
                        args.posts_per_author,
                        args.start_date,
                        args.end_date,
                        args.include_retweets,
                        args.debug,
                    )
                )
            except Exception as exc:
                debug_log(args.debug, f"Skipping @{username} after search error: {exc}")

        all_posts.sort(key=lambda item: item["created_at"] or item["created_at_date"])
        earliest_by_author = {}
        for post in all_posts:
            earliest_by_author.setdefault(post["author_username"], post)
        earliest_posts = list(earliest_by_author.values())

        slug = safe_slug(args.phrase)
        base_name = f"{seed_username}_{slug}_trace"
        posts_csv_path = output_dir / f"{base_name}_posts.csv"
        earliest_csv_path = output_dir / f"{base_name}_earliest_by_author.csv"
        authors_csv_path = output_dir / f"{base_name}_authors.csv"
        edges_csv_path = output_dir / f"{base_name}_network_edges.csv"
        json_path = output_dir / f"{base_name}.json"

        post_fields = [
            "post_id",
            "author_username",
            "searched_author",
            "created_at",
            "created_at_date",
            "text",
            "contains_exact_phrase",
            "like_count",
            "retweet_count",
            "reply_count",
            "quote_count",
            "impression_count",
            "is_retweet",
            "retweeted_tweet_id",
            "quoted_tweet_id",
            "reply_to_tweet_id",
            "urls",
            "post_url",
        ]
        author_fields = [
            "id",
            "username",
            "name",
            "followers_count",
            "following_count",
            "verified",
            "role",
            "discovered_from",
        ]

        write_csv(posts_csv_path, all_posts, post_fields)
        write_csv(earliest_csv_path, earliest_posts, post_fields)
        write_csv(authors_csv_path, list(authors.values()), author_fields)
        write_csv(edges_csv_path, network_edges, ["source", "target", "type"])
        write_json(
            json_path,
            {
                "seed_username": seed_username,
                "network_json": args.network_json,
                "phrase": args.phrase,
                "exact_query": exact_query(args.phrase),
                "start_date": args.start_date,
                "end_date": args.end_date,
                "author_count": len(authors),
                "post_count": len(all_posts),
                "earliest_author_count": len(earliest_posts),
                "network_edge_count": len(network_edges),
                "authors": list(authors.values()),
                "network_edges": network_edges,
                "posts": all_posts,
                "earliest_by_author": earliest_posts,
            },
        )

        if cache is not None and args.debug:
            print(f"[cache] final stats={cache.stats()}")

        print(f"Searched {len(authors)} authors for: {exact_query(args.phrase)}")
        print(f"Found {len(all_posts)} matching posts from {len(earliest_posts)} authors.")
        if all_posts:
            first = all_posts[0]
            print(
                "Earliest collected match: "
                f"@{first['author_username']} at {first['created_at'] or first['created_at_date']}"
            )
            print(first["post_url"])
        print(f"Posts CSV: {posts_csv_path}")
        print(f"Earliest by author CSV: {earliest_csv_path}")
        print(f"Authors CSV: {authors_csv_path}")
        print(f"Network edges CSV: {edges_csv_path}")
        print(f"JSON: {json_path}")
    finally:
        client.close()
        if cache is not None:
            cache.close()


if __name__ == "__main__":
    main()
