import logging
from datetime import datetime
from .config import KEYWORDS, START_DATE, END_DATE
from .db import init_db, upsert_user, upsert_post, insert_edge
from .api import TruthSocialClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_date(date_string):
    """Parse truth social date string (ISO format)."""
    if not date_string:
        return None
    try:
        return datetime.fromisoformat(date_string.replace("Z", "+00:00"))
    except Exception:
        return None

def process_post(post):
    """
    Processes a single post:
    1. Upserts the author
    2. Upserts the post
    3. Handles reblogs/reposts (creating edges)
    """
    author = post.get("account", {})
    if not author:
        return

    # Upsert Author
    upsert_user(author)
    author_id = author.get("id")

    # Upsert Post
    upsert_post(post, author_id)
    post_id = post.get("id")

    # If this is a reblog/repost, we need to process the original post and map the interaction edge
    reblog = post.get("reblog")
    if reblog:
        # Recursively process the original post
        process_post(reblog)
        
        # Create an edge: User X (author) REPOSTED User Y (original author)
        original_author_id = reblog.get("account", {}).get("id")
        if original_author_id:
            insert_edge(
                source_user_id=author_id,
                target_user_id=original_author_id,
                post_id=post_id,
                interaction_type="repost"
            )
            
    # Reply tracking (if it replies to an account, create an edge)
    in_reply_to_account_id = post.get("in_reply_to_account_id")
    if in_reply_to_account_id:
        insert_edge(
            source_user_id=author_id,
            target_user_id=in_reply_to_account_id,
            post_id=post_id,
            interaction_type="reply"
        )
        
    # Mention tracking
    mentions = post.get("mentions", [])
    for mention in mentions:
        mentioned_user_id = mention.get("id")
        if mentioned_user_id:
             insert_edge(
                source_user_id=author_id,
                target_user_id=mentioned_user_id,
                post_id=post_id,
                interaction_type="mention"
            )

def main():
    logger.info("Initializing database...")
    init_db()

    client = TruthSocialClient()

    for keyword in KEYWORDS:
        logger.info(f"Starting scrape for keyword: {keyword}")
        
        try:
            results = client.search_statuses(keyword)
            # The structure of search results is typically a dictionary or response object.
            # Assuming it yields a list of statuses or a dict with a 'statuses' key based on Truthbrush docs
            if isinstance(results, list):
                # Sometimes it returns [ {statuses: [...]}, ... ] or just statuses
                for item in results:
                    statuses = item.get("statuses", []) if isinstance(item, dict) else [item]
                    for post in statuses:
                        if not isinstance(post, dict):
                            # Skip if not a dictionary
                            continue
                            
                        # Filter by Date boundaries
                        created_at_str = post.get("created_at")
                        post_date = parse_date(created_at_str)
                        
                        if post_date:
                            if START_DATE and post_date < START_DATE:
                                continue
                            if END_DATE and post_date > END_DATE:
                                continue

                        process_post(post)
        except Exception as e:
            logger.error(f"Error scraping keyword '{keyword}': {e}")

if __name__ == "__main__":
    main()
