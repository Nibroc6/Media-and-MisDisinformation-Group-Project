# User Patching Tool

Standalone command-line utility to create stub records for missing users in the Truth Social network database.

## Problem

During scraping, edges (interactions) are created between users, but target users in replies and mentions may not have full user records in the database. This tool creates minimal stub records for those missing users, allowing network visualizations to work with complete edge sets.

## Stub Records

Stub records created by this tool include:
- **User ID** (from the edges table)
- **Auto-generated placeholder username** (e.g., `user_107834413`)
- **Follower count**: 0
- **Status count**: 0
- **No metadata** or display names

These records are sufficient for:
- Network graph visualizations
- Edge filtering in queries
- Relationship analysis

## Quick Start

```bash
# Create stubs for all missing users
python patch_users.py

# Preview what would be created (dry-run)
python patch_users.py --dry-run

# Create stubs for only first 100 missing users
python patch_users.py --limit 100

# See detailed logging
python patch_users.py --verbose
```

## Options

| Option | Description | Example |
|--------|-------------|---------|
| `--limit N` | Create stubs for only first N missing users | `--limit 50` |
| `--batch-size N` | Log progress every N users (default: 5) | `--batch-size 20` |
| `--dry-run` | Show what would be patched without making changes | |
| `--verbose` | Enable debug logging | |

## How It Works

1. **Detect Missing Users**: Queries the database for user IDs in the `edges` table that don't exist in the `users` table
2. **Create Stubs**: For each missing user, inserts a minimal record with:
   - The target user ID
   - Placeholder username
   - Zero followers/statuses
3. **Report**: Displays statistics on created records

## Examples

### Basic Usage
```bash
python patch_users.py
```
Output:
```
2026-04-28 14:32:10 - INFO - Starting user patching process...
2026-04-28 14:32:10 - INFO - Current stats: 4053 users, 9411 edges
2026-04-28 14:32:10 - INFO - Found 1683 missing user(s) in edges table
2026-04-28 14:32:15 - INFO - Progress: 100/1683 users patched
...
2026-04-28 14:33:42 - INFO - Patching complete!
2026-04-28 14:33:42 - INFO -   Patched: 1683
2026-04-28 14:33:42 - INFO -   New stats: 5736 users, 9411 edges
```

### Dry Run to Preview
```bash
python patch_users.py --dry-run
```
Shows which users would be created without making database changes.

### Batch Processing with Limit
```bash
python patch_users.py --limit 100 --batch-size 20
```
Creates stub records for first 100 missing users, showing progress every 20 users.

### Verbose Debugging
```bash
python patch_users.py --limit 10 --verbose
```
Shows detailed debug logs for each database operation.

## Exit Codes

- `0`: Success (all stubs created or dry-run completed)
- `1`: Error occurred during patching
- `130`: User cancelled with Ctrl+C

## Performance Notes

- Creates records sequentially with minimal overhead
- Fast operation (typically <5 seconds for 1000+ records)
- Can be safely interrupted with Ctrl+C and resumed later
- Database operations use INSERT OR IGNORE to prevent duplicates

## Getting Full User Data

To get complete user metadata for stub records:

1. **During scraping**: The main scraper upserts user data when mentions/replies appear in newly-discovered posts
2. **API limitations**: The Truth Social API doesn't support direct user ID lookups, so full enrichment requires data to flow through normal scraping

This tool is designed to "fill the gaps" in the network graph while full user data is discovered through normal scraping activity.

## Requirements

- Database with existing `users` and `edges` tables
- Write access to the database

## See Also

- [Main Scraper](main.py): Primary data collection tool
- [Database](db.py): Database operations

