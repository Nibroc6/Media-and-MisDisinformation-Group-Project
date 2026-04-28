import logging
import requests
from truthbrush import Api
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from config import MAX_RETRIES, BACKOFF_MIN_SECONDS, BACKOFF_MAX_SECONDS, SEARCH_LIMIT
from headers import HEADERS

logger = logging.getLogger(__name__)

# Monkey-patch requests.Session to inject custom headers
original_init = requests.Session.__init__

def patched_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    self.headers.update(HEADERS)
    logger.debug(f"Applied custom headers to requests.Session: {list(HEADERS.keys())}")

requests.Session.__init__ = patched_init

class RateLimitException(Exception):
    pass

def handle_retry_error(retry_state):
    logger.error(f"Max retries reached: {retry_state.outcome.exception()}", exc_info=retry_state.outcome.exception())
    raise retry_state.outcome.exception()

class TruthSocialClient:
    def __init__(self):
        # Api() automatically looks for TRUTHSOCIAL_USERNAME and TRUTHSOCIAL_PASSWORD
        # or TRUTHSOCIAL_TOKEN from the environment variables (loaded via dotenv in config).
        # User agent is injected globally via monkey-patch to bypass Cloudflare bot detection
        self.api = Api()
        logger.debug("TruthSocialClient initialized with truthbrush Api")
        
    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=BACKOFF_MIN_SECONDS, max=BACKOFF_MAX_SECONDS),
        before_sleep=before_sleep_log(logger, logging.DEBUG),
        retry_error_callback=handle_retry_error
    )
    def _execute_search(self, query, start_date=None, end_date=None):
        """Helper to collect results, to allow retry to work properly on the generator iteration."""
        results = []
        logger.debug(f"Executing search API call for '{query}' with start_date={start_date}, end_date={end_date}...")
        count = 0
        # Pass start_date and end_date to the API for date-based filtering
        search_kwargs = {"searchtype": "statuses", "query": query, "limit": SEARCH_LIMIT}
        if start_date:
            search_kwargs["start_date"] = start_date
        if end_date:
            search_kwargs["end_date"] = end_date
        
        for item in self.api.search(**search_kwargs):
            results.append(item)
            count += 1
            if count % 10 == 0:
                logger.debug(f"Retrieved {count} items for query '{query}' so far...")
                
        logger.debug(f"Finished executing search API call for '{query}'. Total items retrieved: {len(results)}")
        return results

    def search_statuses(self, query, start_date=None, end_date=None):
        """
        Search for statuses with exponential backoff and date filtering via API.
        """
        logger.info(f"Searching for statuses with query: '{query}'")
        try:
            return self._execute_search(query, start_date=start_date, end_date=end_date)
        except Exception as e:
            logger.exception(f"Error executing search for '{query}': {e}")
            raise

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=BACKOFF_MIN_SECONDS, max=BACKOFF_MAX_SECONDS),
        retry_error_callback=handle_retry_error
    )
    def _execute_get_user_statuses(self, handle):
        results = []
        for item in self.api.pull_statuses(handle):
            results.append(item)
        return results

    def get_user_statuses(self, handle):
        """
        Pull a user's statuses with exponential backoff.
        """
        logger.info(f"Pulling statuses for user: '{handle}'")
        try:
            return self._execute_get_user_statuses(handle)
        except Exception as e:
            logger.exception(f"Error pulling statuses for user: '{handle}': {e}")
            raise

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=BACKOFF_MIN_SECONDS, max=BACKOFF_MAX_SECONDS),
        retry_error_callback=handle_retry_error
    )
    def _execute_get_post_likes(self, post_id):
        results = []
        # Note: truthbrush Api doesn't have a method to get likes on a post
        # Only has user_likes() which gets a user's liked posts
        logger.debug(f"Likes fetching not available in truthbrush API")
        return results

    def get_post_likes(self, post_id):
        """Pull the list of users who liked an post"""
        logger.info(f"Pulling likes for post: {post_id}")
        try:
            return self._execute_get_post_likes(post_id)
        except Exception as e:
            logger.exception(f"Error pulling likes for post '{post_id}': {e}")
            raise

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=BACKOFF_MIN_SECONDS, max=BACKOFF_MAX_SECONDS),
        retry_error_callback=handle_retry_error
    )
    def _execute_get_post_context(self, post_id):
        """Get comments/replies for a post."""
        results = []
        
        if hasattr(self.api, "pull_comments"):
            logger.debug(f"Using api.pull_comments() for post {post_id}")
            try:
                for comment in self.api.pull_comments(post_id):
                    results.append(comment)
            except Exception as e:
                logger.debug(f"Error pulling comments for post {post_id}: {e}")
        else:
            logger.warning(f"truthbrush Api has no pull_comments() method")
        
        return results

    def get_post_context(self, post_id):
        """Get replies/comments for a post."""
        logger.info(f"Pulling comments for post: {post_id}")
        try:
            return self._execute_get_post_context(post_id)
        except Exception as e:
            logger.warning(f"Could not fetch comments for post '{post_id}': {e}")
            return []

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=BACKOFF_MIN_SECONDS, max=BACKOFF_MAX_SECONDS),
        retry_error_callback=handle_retry_error
    )
    def _execute_get_post_reblogs(self, post_id):
        """Get the list of users who reblogged a post."""
        results = []
        # Note: truthbrush Api doesn't have a method to get reblogs on a post
        logger.debug(f"Reblogs fetching not available in truthbrush API")
        return results

    def get_post_reblogs(self, post_id):
        """Get the list of users who reblogged a post."""
        logger.info(f"Pulling reblogs for post: {post_id}")
        try:
            return self._execute_get_post_reblogs(post_id)
        except Exception as e:
            logger.warning(f"Could not fetch reblogs for post '{post_id}': {e}")
            return []
