import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', force=True)

from config import KEYWORDS, START_DATE_STR, END_DATE_STR, SEARCH_SOURCE_TAG
from db import init_db, upsert_user, upsert_post, insert_edge, post_exists
from api import TruthSocialClient

logger = logging.getLogger(__name__)

def process_post(post, source_tag=None):
    """
    Processes a single post:
    1. Upserts the author
    2. Upserts the post
    3. Handles reblogs/reposts (creating edges)
    """
    author = post.get("account", {})
    if not author:
        logger.debug(f"Skipping post {post.get('id')} - no author found.")
        return

    author_username = author.get('username')
    logger.debug(f"Processing post {post.get('id')} by @{author_username}")

    # Upsert Author
    upsert_user(author)
    author_id = author.get("id")

    # Upsert Post
    upsert_post(post, author_id, source_tag=source_tag)
    post_id = post.get("id")

    # If this is a reblog/repost, we need to process the original post and map the interaction edge
    reblog = post.get("reblog")
    if reblog:
        logger.debug(f"Post {post_id} is a repost. Processing original post.")
        # Recursively process the original post
        process_post(reblog, source_tag=source_tag)
        
        # Create an edge: User X (author) REPOSTED User Y (original author)
        original_author_id = reblog.get("account", {}).get("id")
        if original_author_id:
            logger.debug(f"Creating REPOST edge: @{author_username} -> original author {original_author_id}")
            insert_edge(
                source_user_id=author_id,
                target_user_id=original_author_id,
                post_id=post_id,
                interaction_type="repost",
                source_tag=source_tag
            )
            
    # Reply tracking (if it replies to an account, create an edge)
    in_reply_to_account_id = post.get("in_reply_to_account_id")
    if in_reply_to_account_id:
        logger.debug(f"Creating REPLY edge: @{author_username} -> {in_reply_to_account_id}")
        insert_edge(
            source_user_id=author_id,
            target_user_id=in_reply_to_account_id,
            post_id=post_id,
            interaction_type="reply",
            source_tag=source_tag
        )
        
    # Mention tracking
    mentions = post.get("mentions", [])
    for mention in mentions:
        mentioned_user_id = mention.get("id")
        if mentioned_user_id:
             logger.debug(f"Creating MENTION edge: @{author_username} -> {mentioned_user_id}")
             insert_edge(
                source_user_id=author_id,
                target_user_id=mentioned_user_id,
                post_id=post_id,
                interaction_type="mention",
                source_tag=source_tag
            )

def main():
    logger.info("Initializing database...")
    init_db()

    client = TruthSocialClient()

    for keyword in KEYWORDS:
        logger.info(f"Starting scrape for keyword: {keyword}")
        
        try:
            # Pass date range to API for server-side filtering
            results = client.search_statuses(keyword, start_date=START_DATE_STR, end_date=END_DATE_STR)
            posts_processed = 0
            posts_skipped = 0
            
            for item in results:
                # The item could be a dictionary with 'statuses' or the status itself
                statuses = item.get("statuses", []) if isinstance(item, dict) else [item]
                logger.debug(f"Retrieved {len(statuses)} statuses from search result item.")
                
                for post in statuses:
                    if not isinstance(post, dict):
                        continue
                        
                    post_id = post.get("id")
                    if post_id and post_exists(post_id):
                        logger.debug(f"Post {post_id} already exists in database. Skipping.")
                        posts_skipped += 1
                        continue
                    
                    # Save all posts we receive (API already filtered by date)
                    process_post(post, source_tag=SEARCH_SOURCE_TAG)
                    posts_processed += 1
                    
            logger.info(f"Finished scrape for keyword '{keyword}'. Processed: {posts_processed}, Skipped: {posts_skipped}")
            
        except Exception as e:
            logger.error(f"Error scraping keyword '{keyword}': {e}")

if __name__ == "__main__":
    main()
