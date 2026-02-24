import time
from typing import Dict, List


# In-memory rate limit cache keyed by user_id
rate_limit_cache: Dict[str, List[float]] = {}


def check_and_update_rate_limit(user_id: str, max_requests: int = 10, window_seconds: int = 60) -> None:
    """Raise ValueError if user exceeded per-window request limit, otherwise update cache."""
    current_time = time.time()

    # Drop stale entries globally
    stale_cutoff = current_time - window_seconds
    for uid in list(rate_limit_cache.keys()):
        recent = [t for t in rate_limit_cache[uid] if t > stale_cutoff]
        if recent:
            rate_limit_cache[uid] = recent
        else:
            del rate_limit_cache[uid]

    user_requests = [t for t in rate_limit_cache.get(user_id, []) if t > stale_cutoff]
    if len(user_requests) >= max_requests:
        raise ValueError("Too many requests. Please wait before sending another message.")

    user_requests.append(current_time)
    rate_limit_cache[user_id] = user_requests


def clear_rate_limit_cache() -> None:
    rate_limit_cache.clear()
