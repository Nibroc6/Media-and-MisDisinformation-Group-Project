import os
from datetime import datetime, timezone
import random
from dotenv import load_dotenv

load_dotenv()

# Authentication
TRUTHSOCIAL_USERNAME = os.getenv("TRUTHSOCIAL_USERNAME")
TRUTHSOCIAL_PASSWORD = os.getenv("TRUTHSOCIAL_PASSWORD")
TRUTHSOCIAL_TOKEN = os.getenv("TRUTHSOCIAL_TOKEN")

# Database
DB_PATH = os.getenv("DB_PATH", "cache.db")

# Scraping Configuration
SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", 100))
SEARCH_SOURCE_TAG = os.getenv("SEARCH_SOURCE_TAG", "keyword_search")  # Tag for keyword search results

# Provide an array of keywords or hashtags to search for
KEYWORDS = [
    #"autism",
        
    "tylenol",
]
random.shuffle(KEYWORDS) # Shuffle keywords to avoid hitting rate limits on the same keyword repeatedly
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
MAX_RETRIES = 10
BACKOFF_MIN_SECONDS = 15
BACKOFF_MAX_SECONDS = 300

# Trump Posts Loader Configuration
TRUMP_JSON_PATH = os.getenv("TRUMP_JSON_PATH", "trump_posts.json")
TRUMP_USER_ID = os.getenv("TRUMP_USER_ID", "109382855642675251")
TRUMP_LOADER_MAX_POSTS = int(os.getenv("TRUMP_LOADER_MAX_POSTS", 0))  # 0 = load all
TRUMP_SOURCE_TAG = os.getenv("TRUMP_SOURCE_TAG", "trump_json")  # Tag to identify source of data
TRUMP_FILTER_BY_KEYWORDS = os.getenv("TRUMP_FILTER_BY_KEYWORDS", "true").lower() == "true"  # Filter Trump posts by KEYWORDS
