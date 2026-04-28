#!/usr/bin/env python3
"""
Standalone tool to patch missing users in the database.

This tool identifies users referenced in the edges table that don't exist in the users table,
and creates stub records for them. This allows the network visualization to work with complete
edge sets, even if user metadata isn't available.

Usage:
    python patch_users.py                    # Create stubs for all missing users
    python patch_users.py --limit 100        # Create stubs for first 100 missing users
    python patch_users.py --dry-run          # Show what would be patched without making changes
    python patch_users.py --batch-size 10    # Log progress every 10 users
"""

import argparse
import logging
import sys
from db import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_missing_user_ids(limit=None):
    """
    Query the database for user IDs in edges that don't exist in users table.
    
    Args:
        limit: Maximum number of missing user IDs to return (None = all)
    
    Returns:
        List of missing user IDs
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT DISTINCT e.target_user_id
    FROM edges e
    LEFT JOIN users u ON e.target_user_id = u.id
    WHERE u.id IS NULL
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    missing_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return missing_ids


def create_stub_user(user_id):
    """
    Create a minimal stub user record for a missing user ID.
    
    Args:
        user_id: The user ID to create a stub for
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR IGNORE INTO users (
            id, username, display_name, created_at, 
            followers_count, following_count, statuses_count, raw_data
        ) VALUES (?, ?, ?, NULL, 0, 0, 0, NULL)
    """, (
        user_id,
        f"user_{user_id[:8]}",  # Placeholder username
        None  # display_name
    ))
    
    conn.commit()
    conn.close()


def get_user_count():
    """Get total count of users in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_edge_count():
    """Get total count of edges in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM edges")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def patch_missing_users(limit=None, batch_size=5, dry_run=False):
    """
    Create stub records for missing users.
    
    Args:
        limit: Maximum number of users to patch (None = all)
        batch_size: Number of users to log progress after
        dry_run: If True, don't actually create stub records
    
    Returns:
        Tuple of (patched_count, skipped_count)
    """
    logger.info("Starting user patching process...")
    logger.info(f"Current stats: {get_user_count()} users, {get_edge_count()} edges")
    
    # Find missing users
    missing_ids = get_missing_user_ids(limit=limit)
    logger.info(f"Found {len(missing_ids)} missing user(s) in edges table")
    
    if not missing_ids:
        logger.info("No missing users to patch. Database is complete!")
        return 0, 0
    
    if dry_run:
        logger.info("[DRY RUN] Would create stub records for the following missing user IDs:")
        for uid in missing_ids[:10]:
            logger.info(f"  - {uid} (username: user_{uid[:8]})")
        if len(missing_ids) > 10:
            logger.info(f"  ... and {len(missing_ids) - 10} more")
        return 0, len(missing_ids)
    
    patched_count = 0
    
    for i, user_id in enumerate(missing_ids, 1):
        try:
            logger.debug(f"Creating stub user {i}/{len(missing_ids)}: {user_id}")
            create_stub_user(user_id)
            patched_count += 1
            
            if i % batch_size == 0:
                logger.info(f"Progress: {i}/{len(missing_ids)} users patched")
                
        except Exception as e:
            logger.warning(f"Error creating stub for user {user_id}: {e}")
    
    logger.info(f"\nPatching complete!")
    logger.info(f"  Patched: {patched_count}")
    logger.info(f"  New stats: {get_user_count()} users, {get_edge_count()} edges")
    
    return patched_count, 0


def main():
    parser = argparse.ArgumentParser(
        description="Create stub records for missing users in the Truth Social network database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This tool creates minimal user records for IDs that exist in the edges table but not in the users table.
This allows network visualizations to work with complete edge sets, even if full user metadata isn't available.

Stub records have:
  - User ID (from edges table)
  - Auto-generated placeholder username (e.g., user_107834413)
  - Zero followers/statuses
  - No display name or metadata

Note: To get full user data, use the main scraper with the updated process_post() function
that automatically fetches user data for mentioned/replied-to users.

Examples:
  python patch_users.py                    # Create stubs for all missing users
  python patch_users.py --limit 50         # Create stubs for first 50 missing users
  python patch_users.py --dry-run          # Preview without making changes
  python patch_users.py --batch-size 20    # Log progress every 20 users
        """
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum number of missing users to patch (default: all)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='Number of users to process before logging progress (default: 5)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be patched without making changes'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        patched, skipped = patch_missing_users(
            limit=args.limit,
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )
        
        if args.dry_run:
            logger.info(f"[DRY RUN] Would create stub records for {skipped} users")
            return 0
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("\nPatching cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
