# Truth Social Misinformation Tracker

An academic ingestion tool built on top of `truthbrush` to archive Truth Social posts, users, and interaction networks.

## Features
- **Appends-only SQLite database**: Ensures no data is ever lost. Stores raw JSON for future schema updates.
- **Configurable searches**: Adjust keywords and timeframe in `scraper/config.py` and `.env`.
- **Relational Edges**: Automatically graphs Reblogs (reposts), replies, and mentions for network mapping.
- **Resiliency**: Built-in exponential backoff via `tenacity` handles API rate limits gracefully.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure your `.env` file:**
   Copy `.env.example` to `.env` and fill out your credentials.
   ```bash
   cp .env.example .env
   ```

3. **Adjust Config:**
   Open `scraper/config.py` to add your desired keywords (e.g., `'vaccine'`, `'autism'`) and update your date range (`START_DATE` / `END_DATE`).

## Running

Execute the main scraper script from the root of the project:

```bash
python -m scraper.main
```

The scraper will generate a `cache.db` file in your root folder.

## Database Querying
You can extract JSON natively using SQLite:

```sql
-- Find total number of unique users recorded
SELECT COUNT(*) FROM users;

-- Find who reposted who
SELECT source_user_id, target_user_id, interaction_type FROM edges;

-- Extract raw data metrics examples:
SELECT json_extract(raw_data, '$.content') FROM posts LIMIT 5;
```
