import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Authentication
TRUTHSOCIAL_USERNAME = os.getenv("TRUTHSOCIAL_USERNAME", "bobjoe666")
TRUTHSOCIAL_PASSWORD = os.getenv("TRUTHSOCIAL_PASSWORD", "0g&7HaD!k7s@@UG")
TRUTHSOCIAL_TOKEN = os.getenv("TRUTHSOCIAL_TOKEN", "nYVjSWkEpJZF4U9NtJPD8JZDTTrgb1PYga2J7Hrd_Ks")

# Database
DB_PATH = os.getenv("DB_PATH", "cache.db")

# Scraping Configuration
# Provide an array of keywords or hashtags to search for
KEYWORDS = [
    "vaccine", 
    "autism"
]

# Timeframe Filtering
# ISO format date strings. If None, won't filter by date.
START_DATE_STR = os.getenv("START_DATE", "2021-01-01T00:00:00Z")
END_DATE_STR = os.getenv("END_DATE", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

try:
    START_DATE = datetime.fromisoformat(START_DATE_STR.replace("Z", "+00:00")) if START_DATE_STR else None
    END_DATE = datetime.fromisoformat(END_DATE_STR.replace("Z", "+00:00")) if END_DATE_STR else None
except ValueError:
    print("Warning: Invalid date format in config. Using defaults.")
    START_DATE = None
    END_DATE = None

# Rate limiting / Backoff Configurations
MAX_RETRIES = 5
BACKOFF_MIN_SECONDS = 2
BACKOFF_MAX_SECONDS = 60
