import logging
import time
from functools import wraps
from typing import Callable, Type

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    delay: float = 2.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    logger.warning(
                        "Attempt %d/%d failed for %s: %s",
                        attempt,
                        max_attempts,
                        func.__name__,
                        exc,
                    )
                    if attempt < max_attempts:
                        time.sleep(delay * attempt)
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator
