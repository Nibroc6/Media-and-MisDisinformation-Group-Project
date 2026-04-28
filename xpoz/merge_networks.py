"""
merge_networks.py — Merge multiple network_map.py JSON files into a single
author list for use with trace_phrase.py --network-json.

What it does
------------
  - Reads any number of network JSON files produced by network_map.py
  - Deduplicates nodes by username (first file's data wins for conflicts)
  - Deduplicates edges by (source, target, type)
  - Writes a merged JSON in the same format as network_map.py output so
    trace_phrase.py can consume it directly via --network-json

Usage
-----
    python merge_networks.py \\
        trump_network_map/realDonaldTrump_follow_network.json \\
        trump_network_map/DonaldJTrumpJr/DonaldJTrumpJr_follow_network.json \\
        trump_network_map/Jim_Jordan/Jim_Jordan_follow_network.json \\
        trump_network_map/kimguilfoyle/kimguilfoyle_follow_network.json \\
        trump_network_map/DanScavino/DanScavino_follow_network.json \\
        --output-json trump_network_map/merged_follow_network.json

    # Only keep nodes with at least N followers (filter noise):
    python merge_networks.py *.json --output-json merged.json --min-followers 1000

    # Dry run — show stats without writing:
    python merge_networks.py *.json --output-json merged.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge multiple network_map.py JSON files into a single network JSON "
            "for use with trace_phrase.py --network-json."
        )
    )
    parser.add_argument(
        "network_jsons",
        nargs="+",
        help="Paths to network JSON files produced by network_map.py.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to write the merged output JSON.",
    )
    parser.add_argument(
        "--min-followers",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Exclude nodes with fewer than N followers. "
            "Useful for filtering out noise/bot accounts. Default: 0 (keep all)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print merge stats without writing the output file.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file progress messages.",
    )
    return parser.parse_args()


def log(quiet: bool, msg: str) -> None:
    if not quiet:
        print(msg)


def load_network(path: Path, quiet: bool) -> tuple[list[dict], list[dict], str | None]:
    log(quiet, f"  Loading {path} …")
    payload = json.loads(path.read_text(encoding="utf-8"))
    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])
    seed_username = payload.get("seed_username")
    log(quiet, f"    → {len(nodes)} nodes, {len(edges)} edges  (seed: @{seed_username})")
    return nodes, edges, seed_username


def main() -> None:
    args = parse_args()

    input_paths = [Path(p) for p in args.network_jsons]
    missing = [p for p in input_paths if not p.exists()]
    if missing:
        sys.exit(f"Error: file(s) not found: {', '.join(str(p) for p in missing)}")

    print(f"Merging {len(input_paths)} network file(s) …\n")

    merged_nodes: dict[str, dict] = {}   # username → node dict
    merged_edges: dict[tuple, dict] = {}  # (source, target, type) → edge dict
    seed_usernames: list[str] = []
    per_file_stats: list[dict] = []

    for path in input_paths:
        nodes, edges, seed_username = load_network(path, args.quiet)

        new_nodes = 0
        skipped_followers = 0
        for node in nodes:
            username = node.get("username", "").strip()
            if not username:
                continue
            followers = node.get("followers_count") or 0
            if followers < args.min_followers:
                skipped_followers += 1
                continue
            if username not in merged_nodes:
                merged_nodes[username] = node
                new_nodes += 1

        new_edges = 0
        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            etype = edge.get("type", "")
            if not source or not target:
                continue
            # Only include edges where both endpoints survived the filter
            if source not in merged_nodes or target not in merged_nodes:
                continue
            key = (source, target, etype)
            if key not in merged_edges:
                merged_edges[key] = edge
                new_edges += 1

        if seed_username and seed_username not in seed_usernames:
            seed_usernames.append(seed_username)

        per_file_stats.append({
            "file": str(path),
            "seed": seed_username,
            "nodes_in_file": len(nodes),
            "new_nodes_added": new_nodes,
            "skipped_low_followers": skipped_followers,
            "edges_in_file": len(edges),
            "new_edges_added": new_edges,
        })

    nodes_out = sorted(merged_nodes.values(), key=lambda n: n.get("username", ""))
    edges_out = list(merged_edges.values())

    # Summary
    print(f"\n{'─' * 50}")
    print("Merge summary")
    print(f"{'─' * 50}")
    for stat in per_file_stats:
        print(
            f"  {Path(stat['file']).name:<50} "
            f"+{stat['new_nodes_added']:>4} nodes  "
            f"+{stat['new_edges_added']:>5} edges"
            + (f"  ({stat['skipped_low_followers']} skipped <{args.min_followers} followers)" if args.min_followers else "")
        )
    print(f"{'─' * 50}")
    print(f"  Total unique nodes : {len(nodes_out):>6}")
    print(f"  Total unique edges : {len(edges_out):>6}")
    print(f"  Seed accounts      : {', '.join(f'@{s}' for s in seed_usernames)}")
    if args.min_followers:
        print(f"  Min followers filter: {args.min_followers:,}")
    print(f"{'─' * 50}\n")

    if args.dry_run:
        print("Dry run — no file written.")
        return

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "merged_from": [str(p) for p in input_paths],
        "seed_usernames": seed_usernames,
        # trace_phrase.py reads seed_username (singular) for labelling
        "seed_username": seed_usernames[0] if seed_usernames else "",
        "min_followers_filter": args.min_followers,
        "node_count": len(nodes_out),
        "edge_count": len(edges_out),
        "nodes": nodes_out,
        "edges": edges_out,
    }

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Written → {output_path}")
    print(f"  {len(nodes_out)} nodes, {len(edges_out)} edges ready for trace_phrase.py\n")
    print("Next step:")
    print(
        f"  python xpoz/trace_phrase.py realDonaldTrump \"tylenol causes autism\" \\\n"
        f"    --network-json {output_path} \\\n"
        f"    --output-dir trump_phrase_trace \\\n"
        f"    --cache-db xpoz/xpoz_cache.db \\\n"
        f"    --include-retweets --debug"
    )


if __name__ == "__main__":
    main()
    
    