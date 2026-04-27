import logging
from truthbrush import Api
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .config import MAX_RETRIES, BACKOFF_MIN_SECONDS, BACKOFF_MAX_SECONDS

logger = logging.getLogger(__name__)

class RateLimitException(Exception):
    pass

def handle_retry_error(retry_state):
    logger.error(f"Max retries reached: {retry_state.outcome.exception()}")
    raise retry_state.outcome.exception()

class TruthSocialClient:
    def __init__(self):
        # Api() automatically looks for TRUTHSOCIAL_USERNAME and TRUTHSOCIAL_PASSWORD
        # or TRUTHSOCIAL_TOKEN from the environment variables (loaded via dotenv in config).
        self.api = Api()
        
    @retry(
        retry=retry_if_exception_type(Exception), # Catch generic HTTP/RateLimit exceptions from truthbrush
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=BACKOFF_MIN_SECONDS, max=BACKOFF_MAX_SECONDS),
        retry_error_callback=handle_retry_error
    )
    def search_statuses(self, query):
        """
        Search for statuses with exponential backoff.
        Note: truthbrush API search method returns a generator.
        """
        logger.info(f"Searching for statuses with query: '{query}'")
        return list(self.api.search(query, searchType="statuses"))

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=BACKOFF_MIN_SECONDS, max=BACKOFF_MAX_SECONDS),
        retry_error_callback=handle_retry_error
    )
    def get_user_statuses(self, handle):
        """
        Pull a user's statuses with exponential backoff.
        """
        logger.info(f"Pulling statuses for user: '{handle}'")
        return list(self.api.pull_statuses(handle))

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=BACKOFF_MIN_SECONDS, max=BACKOFF_MAX_SECONDS),
        retry_error_callback=handle_retry_error
    )
    def get_post_likes(self, post_id):
        """Pull the list of users who liked an post"""
        # truthbrush doesn't have a direct Api method mapped purely for likes easily natively exposed 
        # as a function sometimes, typically you might have to call an internal method, but the CLI does it.
        # The Api has endpoints. Let's use standard truthbrush call or fallback.
        # Looking at CLI: truthbrush likes POST
        # Currently, Api provides `pull_likes(post_id)` usually.
        logger.info(f"Pulling likes for post: {post_id}")
        # The truthbrush API method might be named differently, trying pull_likes/likes if available.
        if hasattr(self.api, "likes"):
            return self.api.likes(post_id)
        elif hasattr(self.api, "pull_likes"):
            return list(self.api.pull_likes(post_id))
        else:
             # Manual fetch strategy just in case, but usually pull_likes or likes is exposed
            pass
        return []
