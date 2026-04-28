import json
import logging
from datetime import datetime
from pathlib import Path
from config import SEARCH_LIMIT, START_DATE_STR, END_DATE_STR, TRUMP_JSON_PATH, TRUMP_USER_ID, TRUMP_LOADER_MAX_POSTS, TRUMP_SOURCE_TAG, TRUMP_FILTER_BY_KEYWORDS, KEYWORDS
from db import init_db, upsert_user, upsert_post, insert_edge, post_exists
from api import TruthSocialClient

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', force=True)
logger = logging.getLogger(__name__)


def post_contains_keywords(post_content: str, keywords: list) -> bool:
    """
    Check if a post contains at least one of the specified keywords (case-insensitive).
    
    Args:
        post_content: The content of the post to check
        keywords: List of keywords to search for
    
    Returns:
        True if post contains at least one keyword, False otherwise
    """
    if not post_content or not keywords:
        return False
    
    content_lower = post_content.lower()
    for keyword in keywords:
        if keyword.lower() in content_lower:
            return True
    return False


def load_trump_posts_from_json(json_path: str, start_date: str = None, end_date: str = None, max_posts: int = None, filter_keywords: bool = False, keywords: list = None):
    """
    Load Trump's posts from a JSON file.
    
    Args:
        json_path: Path to the JSON file containing Trump's posts
        start_date: ISO format date string to filter posts (e.g., "2026-01-01T00:00:00Z")
        end_date: ISO format date string to filter posts
        max_posts: Maximum number of posts to keep (applied AFTER all filtering)
        filter_keywords: If True, only keep posts containing at least one keyword
        keywords: List of keywords to filter by (if filter_keywords is True)
    
    Returns:
        List of posts (already filtered by date and keywords if specified)
    """
    logger.info(f"Loading Trump posts from {json_path}")
    
    if not Path(json_path).exists():
        logger.error(f"File not found: {json_path}")
        raise FileNotFoundError(f"File not found: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        posts = json.load(f)
    
    logger.info(f"Loaded {len(posts)} posts from JSON file")
    
    # Filter by date and keywords if specified
    filtered_posts = []
    posts_filtered_by_date = 0
    posts_filtered_by_keyword = 0
    
    for post in posts:
        try:
            created_at = datetime.fromisoformat(post.get("created_at", "").replace("Z", "+00:00"))
            
            if start_date:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                if created_at < start_dt:
                    posts_filtered_by_date += 1
                    continue
            
            if end_date:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                if created_at > end_dt:
                    posts_filtered_by_date += 1
                    continue
            
            # Filter by keywords if enabled (BEFORE applying max_posts limit)
            if filter_keywords and keywords:
                if not post_contains_keywords(post.get("content", ""), keywords):
                    posts_filtered_by_keyword += 1
                    continue
            
            filtered_posts.append(post)
                
        except ValueError as e:
            logger.debug(f"Skipping post with invalid date {post.get('created_at')}: {e}")
            continue
    
    # Apply max_posts limit AFTER all filtering
    if max_posts and len(filtered_posts) > max_posts:
        logger.info(f"Applying max_posts limit of {max_posts} to {len(filtered_posts)} filtered posts")
        filtered_posts = filtered_posts[:max_posts]
    
    if filter_keywords:
        logger.info(f"After filtering: {len(filtered_posts)} posts (by date: {posts_filtered_by_date}, by keywords: {posts_filtered_by_keyword})")
    else:
        logger.info(f"After filtering: {len(filtered_posts)} posts (by date: {posts_filtered_by_date})")
    return filtered_posts


def process_trump_post(post_data: dict, author_id: str):
    """
    Process a Trump post:
    1. Upsert the post
    2. Store metadata (replies_count, reblogs_count, favourites_count)
    """
    post_id = post_data.get("id")
    logger.debug(f"Processing Trump post {post_id}")
    
    upsert_post(post_data, author_id, source_tag=TRUMP_SOURCE_TAG)
    logger.debug(f"Upserted post {post_id}")


def fetch_and_store_interactions(client: TruthSocialClient, post_id: str, author_id: str, trump_user_id: str = None):
    """
    Fetch interactions (replies/comments) for a Trump post and create edges.
    
    Args:
        client: TruthSocialClient instance
        post_id: ID of the post to fetch interactions for
        author_id: User ID of the post author (Trump)
        trump_user_id: Optional Trump's user ID (for efficiency)
    """
    logger.debug(f"Fetching interactions for post {post_id}")
    
    # Fetch replies/comments
    try:
        comments = client.get_post_context(post_id)
        logger.debug(f"Found {len(comments) if comments else 0} comments for post {post_id}")
        
        if comments:
            for comment_post in comments:
                if isinstance(comment_post, dict):
                    comment_account = comment_post.get("account", {})
                    if comment_account:
                        commenter_id = comment_account.get("id")
                        if commenter_id and commenter_id != author_id:  # Don't create self-reply edges
                            # Store the commenter's user data
                            upsert_user(comment_account)
                            # Create a "reply" edge from commenter to Trump (author)
                            insert_edge(
                                source_user_id=commenter_id,
                                target_user_id=author_id,
                                post_id=post_id,
                                interaction_type="reply",
                                source_tag=TRUMP_SOURCE_TAG
                            )
                            logger.debug(f"Created REPLY edge: {commenter_id} -> {author_id}")
    
    except Exception as e:
        logger.warning(f"Error fetching comments for post {post_id}: {e}")
    
    logger.debug(f"Completed interaction processing for post {post_id}")


def main():
    """
    Main workflow:
    1. Initialize database
    2. Load Trump posts from JSON
    3. Insert Trump posts into DB
    4. Fetch and store interactions for each post
    """
    
    logger.info("=" * 80)
    logger.info("TRUMP POSTS LOADER - Initializing")
    logger.info("=" * 80)
    
    # Initialize database
    logger.info("Initializing database...")
    init_db()
    
    # Load posts from JSON
    try:
        max_posts = TRUMP_LOADER_MAX_POSTS if TRUMP_LOADER_MAX_POSTS > 0 else None
        if TRUMP_FILTER_BY_KEYWORDS:
            logger.info(f"Keyword filtering enabled. Will only load Trump posts containing: {KEYWORDS}")
        posts = load_trump_posts_from_json(
            TRUMP_JSON_PATH,
            start_date=START_DATE_STR,
            end_date=END_DATE_STR,
            max_posts=max_posts,
            filter_keywords=TRUMP_FILTER_BY_KEYWORDS,
            keywords=KEYWORDS
        )
    except FileNotFoundError as e:
        logger.error(f"Cannot proceed without Trump posts JSON file: {e}")
        logger.error(f"Please set TRUMP_JSON_PATH environment variable or update config.py")
        return
    
    if not posts:
        logger.warning("No posts to process after filtering")
        return
    
    # Insert Trump's user data
    logger.info("Upserting Trump user data...")
    trump_user_data = {
        "id": TRUMP_USER_ID,
        "username": "realDonaldTrump",
        "display_name": "Donald J. Trump",
    }
    upsert_user(trump_user_data)
    
    # Process posts
    client = TruthSocialClient()
    posts_processed = 0
    posts_skipped = 0
    
    logger.info(f"Processing {len(posts)} posts...")
    
    for i, post in enumerate(posts, 1):
        post_id = post.get("id")
        
        if not post_id:
            logger.warning(f"Skipping post without ID at index {i}")
            posts_skipped += 1
            continue
        
        if post_exists(post_id):
            logger.debug(f"Post {post_id} already exists. Skipping.")
            posts_skipped += 1
            continue
        
        try:
            # Process the post
            process_trump_post(post, TRUMP_USER_ID)
            posts_processed += 1
            
            # Fetch interactions for this post
            try:
                fetch_and_store_interactions(client, post_id, TRUMP_USER_ID, trump_user_id=TRUMP_USER_ID)
            except Exception as e:
                logger.warning(f"Error fetching interactions for post {post_id}: {e}")
            
            if i % 100 == 0:
                logger.info(f"Progress: {i}/{len(posts)} posts processed...")
        
        except Exception as e:
            logger.error(f"Error processing post {post_id}: {e}")
            posts_skipped += 1
    
    logger.info("=" * 80)
    logger.info(f"COMPLETED - Processed: {posts_processed}, Skipped: {posts_skipped}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
