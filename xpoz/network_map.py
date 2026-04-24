import argparse
import csv
import json
import os
from pathlib import Path

from xpoz import XpozClient

DEFAULT_FIELDS = [
    "id",
    "username",
    "name",
    "followers_count",
    "following_count",
    "verified",
]


def debug_log(enabled: bool, message: str) -> None:
    if enabled:
        print(f"[debug] {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Twitter/X follow-back network map using xpoz. "
            "The script fetches a seed user's following list, then checks which "
            "of those accounts follow other accounts in that seed set."
        )
    )
    parser.add_argument("username", help="Seed username, without the @")
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
        default=200,
        help="Maximum following records to inspect for each account in the seed set.",
    )
    parser.add_argument(
        "--output-dir",
        default="network_map_output2",
        help="Directory for the generated JSON, CSV, and DOT files.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60,
        help="Maximum seconds to wait for each xpoz operation.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print detailed progress logs while building the network.",
    )
    return parser.parse_args()


def fetch_connections(
    client: XpozClient,
    username: str,
    connection_type: str,
    limit: int,
    debug: bool = False,
) -> list:
    if limit <= 0:
        debug_log(debug, f"Skipping {connection_type} fetch for @{username}: limit is {limit}.")
        return []

    debug_log(
        debug,
        f"Fetching up to {limit} {connection_type} records for @{username}.",
    )
    page = client.twitter.get_user_connections(
        username,
        connection_type,
        fields=DEFAULT_FIELDS,
    )
    items = []
    seen_usernames = set()
    for user in page.data:
        if user.username and user.username in seen_usernames:
            continue
        if user.username:
            seen_usernames.add(user.username)
        items.append(user)
    debug_log(
        debug,
        (
            f"Fetched requested page 1 "
            f"(reported as page {page.pagination.page_number}"
            f"/{page.pagination.total_pages or '?'} for @{username} "
            f"({len(page.data)} records, {len(items)} unique accumulated)."
        ),
    )

    total_pages = page.pagination.total_pages or 1
    requested_page = 2
    empty_or_duplicate_pages = 0

    while len(items) < limit and requested_page <= total_pages:
        page = page.get_page(requested_page)
        new_items = 0
        for user in page.data:
            if user.username and user.username in seen_usernames:
                continue
            if user.username:
                seen_usernames.add(user.username)
            items.append(user)
            new_items += 1

        debug_log(
            debug,
            (
                f"Fetched requested page {requested_page} "
                f"(reported as page {page.pagination.page_number}"
                f"/{page.pagination.total_pages or '?'} for @{username} "
                f"({len(page.data)} records, {len(items)} unique accumulated, "
                f"{new_items} new)."
            ),
        )
        if new_items == 0:
            empty_or_duplicate_pages += 1
            if empty_or_duplicate_pages >= 2:
                debug_log(
                    debug,
                    (
                        f"Stopping @{username} pagination after "
                        f"{empty_or_duplicate_pages} pages with no new users."
                    ),
                )
                break
        else:
            empty_or_duplicate_pages = 0

        requested_page += 1

    trimmed = items[:limit]
    debug_log(
        debug,
        f"Completed {connection_type} fetch for @{username}: returning {len(trimmed)} records.",
    )
    return trimmed


def node_payload(user, role: str) -> dict:
    username = user.username or ""
    return {
        "id": user.id or username,
        "username": username,
        "label": user.name or username or "Unknown user",
        "followers_count": user.followers_count,
        "following_count": user.following_count,
        "verified": bool(user.verified),
        "role": role,
    }


def edge_payload(source: str, target: str, edge_type: str) -> dict:
    return {
        "source": source,
        "target": target,
        "type": edge_type,
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_dot(path: Path, nodes: list[dict], edges: list[dict], seed_username: str) -> None:
    lines = [
        "digraph follow_network {",
        "  rankdir=LR;",
        '  graph [fontname="Helvetica"];',
        '  node [shape=ellipse, style=filled, fillcolor="#f6f8fa", color="#8c959f", fontname="Helvetica"];',
        '  edge [color="#57606a", fontname="Helvetica"];',
    ]

    for node in nodes:
        node_id = node["username"]
        fill = "#ffd8a8" if node_id == seed_username else "#dbeafe"
        if node["role"] == "seed_following":
            fill = "#d1fae5"
        label = node["label"].replace('"', '\\"')
        lines.append(
            f'  "{node_id}" [label="{label}\\n@{node_id}", fillcolor="{fill}"];'
        )

    for edge in edges:
        color = "#1f6feb" if edge["type"] == "seed_follows" else "#2da44e"
        lines.append(
            f'  "{edge["source"]}" -> "{edge["target"]}" [color="{color}"];'
        )

    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if not args.api_key:
        raise SystemExit("Missing API key. Pass --api-key or set XPOZ_API_KEY.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    debug_log(
        args.debug,
        (
            f"Output directory is {output_dir.resolve()}. "
            f"Seed limit={args.seed_limit}, per-account limit={args.per_account_limit}, "
            f"timeout={args.timeout}s."
        ),
    )

    client = XpozClient(args.api_key, timeout=args.timeout, check_update=False)
    try:
        debug_log(args.debug, f"Looking up seed user @{args.username}.")
        seed_user = client.twitter.get_user(args.username, fields=DEFAULT_FIELDS)
        seed_username = seed_user.username or args.username
        debug_log(
            args.debug,
            f"Resolved seed user to @{seed_username} ({seed_user.name or 'no display name'}).",
        )
        first_degree = fetch_connections(
            client,
            seed_username,
            "following",
            args.seed_limit,
            debug=args.debug,
        )
        debug_log(
            args.debug,
            f"Seed following sample contains {len(first_degree)} raw records.",
        )

        nodes_by_username: dict[str, dict] = {
            seed_username: node_payload(seed_user, role="seed"),
        }
        edges: list[dict] = []

        seed_usernames: set[str] = set()
        for user in first_degree:
            if not user.username:
                debug_log(args.debug, "Skipping first-degree record with no username.")
                continue
            seed_usernames.add(user.username)
            nodes_by_username[user.username] = node_payload(user, role="seed_following")
            edges.append(edge_payload(seed_username, user.username, "seed_follows"))
            debug_log(
                args.debug,
                f"Added seed edge @{seed_username} -> @{user.username}.",
            )

        interesting_usernames = set(seed_usernames)
        interesting_usernames.add(seed_username)
        debug_log(
            args.debug,
            f"Tracking {len(interesting_usernames)} usernames in the seed neighborhood.",
        )

        for user in first_degree:
            if not user.username:
                continue

            debug_log(args.debug, f"Inspecting second-degree following for @{user.username}.")
            following = fetch_connections(
                client,
                user.username,
                "following",
                args.per_account_limit,
                debug=args.debug,
            )
            matched_edges = 0
            for neighbor in following:
                if not neighbor.username or neighbor.username not in interesting_usernames:
                    continue
                if neighbor.username == user.username:
                    continue
                if neighbor.username not in nodes_by_username:
                    nodes_by_username[neighbor.username] = node_payload(
                        neighbor,
                        role="seed",
                    )
                edges.append(
                    edge_payload(user.username, neighbor.username, "follow_back_within_seed")
                )
                matched_edges += 1
                debug_log(
                    args.debug,
                    f"Added internal edge @{user.username} -> @{neighbor.username}.",
                )
            debug_log(
                args.debug,
                f"Finished @{user.username}: found {matched_edges} edges back into the sampled network.",
            )

        deduped_edges = list(
            {
                (edge["source"], edge["target"], edge["type"]): edge
                for edge in edges
            }.values()
        )
        nodes = sorted(nodes_by_username.values(), key=lambda item: item["username"])
        debug_log(
            args.debug,
            (
                f"Deduped graph to {len(nodes)} nodes and {len(deduped_edges)} edges "
                f"from {len(edges)} raw edges."
            ),
        )

        payload = {
            "seed_username": seed_username,
            "seed_limit": args.seed_limit,
            "per_account_limit": args.per_account_limit,
            "node_count": len(nodes),
            "edge_count": len(deduped_edges),
            "nodes": nodes,
            "edges": deduped_edges,
        }

        base_name = f"{seed_username}_follow_network"
        json_path = output_dir / f"{base_name}.json"
        nodes_csv_path = output_dir / f"{base_name}_nodes.csv"
        edges_csv_path = output_dir / f"{base_name}_edges.csv"
        dot_path = output_dir / f"{base_name}.dot"

        write_json(json_path, payload)
        write_csv(
            nodes_csv_path,
            nodes,
            ["id", "username", "label", "followers_count", "following_count", "verified", "role"],
        )
        write_csv(
            edges_csv_path,
            deduped_edges,
            ["source", "target", "type"],
        )
        write_dot(dot_path, nodes, deduped_edges, seed_username)
        debug_log(
            args.debug,
            "Finished writing JSON, CSV, and DOT outputs.",
        )

        mutual_with_seed = sorted(
            edge["source"]
            for edge in deduped_edges
            if edge["target"] == seed_username and edge["type"] == "follow_back_within_seed"
        )

        print(f"Seed user: @{seed_username}")
        print(f"Pulled {len(seed_usernames)} followed accounts from the seed user.")
        print(f"Mapped {len(deduped_edges)} directed edges across {len(nodes)} nodes.")
        if mutual_with_seed:
            print("Accounts that follow the seed user back:")
            for username in mutual_with_seed:
                print(f"  - @{username}")
        else:
            print("No follow-back links to the seed user were found in the sampled network.")
        print(f"JSON: {json_path}")
        print(f"Nodes CSV: {nodes_csv_path}")
        print(f"Edges CSV: {edges_csv_path}")
        print(f"Graphviz DOT: {dot_path}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
