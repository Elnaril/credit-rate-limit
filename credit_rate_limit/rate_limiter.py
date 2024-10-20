"""
Easily rate limit async requests to API using credits, computation unit per second (CUPS) or request units,
in addition to those just counting the number of requests per time unit

* Author: Elnaril (https://www.fiverr.com/elnaril, https://github.com/Elnaril).
* License: MIT.
* Doc: https://github.com/Elnaril/credit-rate-limit
"""
import asyncio
from dataclasses import dataclass
from functools import wraps
import logging
from typing import (
    Any,
    Optional,
    Protocol,
    Union,
)
from uuid import uuid4


logger = logging.getLogger(__name__)


@dataclass
class CreditState:
    name: str
    available: int
    max: int
    interval: float
    delay: float


class CreditContextManager:
    def __init__(self, request_credits: int, credit_state: CreditState) -> None:
        self.request_credits = request_credits
        self.credit_state = credit_state

    async def __aenter__(self) -> "CreditContextManager":
        while True:
            if self.credit_state.available >= self.request_credits:
                self.credit_state.available -= self.request_credits
                if self.credit_state.available <= 0.1 * self.credit_state.max:
                    logger.debug(
                        f"Credit Rate Limiter {self.credit_state.name} is using more than 90% of its "
                        f"{self.credit_state.max} credits per {self.credit_state.interval} s"
                    )
                break
            await asyncio.sleep(0.1)
        return self

    async def __aexit__(self, exception_type: Any, exception_val: Any, exception_traceback: Any) -> None:
        loop = asyncio.get_running_loop()
        loop.call_later(self.credit_state.delay, self.release_credits)

    def release_credits(self) -> None:
        self.credit_state.available += self.request_credits
        if self.credit_state.available == self.credit_state.max:
            logger.debug(
                f"Credit Rate Limiter {self.credit_state.name} is back under its limit of "
                f"{self.credit_state.max} credits per {self.credit_state.interval} s"
            )


class CreditRateLimiter:
    def __init__(self, max_credits: int, interval: float, adjustment: float = 0., name: Optional[str] = None) -> None:
        """
        Configure a rate limit of max_credit per interval seconds (for API using credits, CUPS, request units, ...)
        :param max_credits: number of allowed credits per interval
        :param interval: duration in seconds on which is defined the rate limit.
        :param adjustment: optimisation parameter
        :param name: an optional name to easily identify the instance
        """
        self.credit_state = CreditState(
            name=str(uuid4()) if name is None else name,
            available=max_credits,
            max=max_credits,
            interval=interval,
            delay=max(0.0, interval - adjustment)
        )

    def __call__(self, request_credits: int) -> CreditContextManager:
        return CreditContextManager(request_credits, self.credit_state)


class CountRateLimiter:
    def __init__(self, max_count: int, interval: float, adjustment: float = 0., name: Optional[str] = None) -> None:
        """
        Configure a rate limit of max_count requests per interval seconds.
        :param max_count: number of allowed requests per interval
        :param interval: duration in seconds on which is defined the rate limit.
        :param adjustment: optimisation parameter
        :param name: an optional name to easily identify the instance
        """
        self.name = uuid4() if name is None else name
        self.max_count = max_count
        self.interval = interval
        self.semaphore = asyncio.Semaphore(self.max_count)
        self.delay = max(0.0, self.interval - adjustment)

    async def __aenter__(self) -> "CountRateLimiter":
        await self.semaphore.acquire()
        if self.semaphore.locked():
            logger.debug(
                f"Rate Limiter {self.name} has reached its limit of {self.max_count} calls per {self.interval} s"
            )
        return self

    async def __aexit__(self, exception_type: Any, exception_val: Any, exception_traceback: Any) -> None:
        loop = asyncio.get_running_loop()
        loop.call_later(self.delay, self.release_semaphore)

    def release_semaphore(self) -> None:
        if self.semaphore.locked():
            logger.debug(
                f"Rate Limiter {self.name} is back under its limit of {self.max_count} calls per {self.interval} s"
            )
        self.semaphore.release()


class DecoratedSignature(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


def credit_rate_limit(rate_limiter: CreditRateLimiter, request_credits: int) -> Any:
    def decorator(func: DecoratedSignature) -> Any:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with rate_limiter(request_credits):
                return await func(*args, **kwargs)
        return wrapper
    return decorator


def count_rate_limit(rate_limiter: CountRateLimiter) -> Any:
    def decorator(func: DecoratedSignature) -> Any:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with rate_limiter:
                return await func(*args, **kwargs)
        return wrapper
    return decorator


def credit_rate_limit_with_attribute(attribute_name: str, request_credits: int) -> Any:
    def decorator(func: DecoratedSignature) -> Any:
        @wraps(func)
        def wrapper(self_: CreditRateLimiter, *args: Any, **kwargs: Any) -> Any:
            credit_rate_limiter = getattr(self_, attribute_name)
            if not isinstance(credit_rate_limiter, CreditRateLimiter):
                raise ValueError(
                    f"credit_rate_limiter must be of type CreditRateLimiter. Got {type(credit_rate_limiter)}"
                )
            return credit_rate_limit(credit_rate_limiter, request_credits)(func)(self_, *args, **kwargs)
        return wrapper
    return decorator


def count_rate_limit_with_attribute(attribute_name: str) -> Any:
    def decorator(func: DecoratedSignature) -> Any:
        @wraps(func)
        def wrapper(self_: CountRateLimiter, *args: Any, **kwargs: Any) -> Any:
            rate_limiter = getattr(self_, attribute_name)
            if not isinstance(rate_limiter, CountRateLimiter):
                raise ValueError(f"rate_limiter must be of type CountRateLimiter. Got {type(rate_limiter)}")
            return count_rate_limit(rate_limiter)(func)(self_, *args, **kwargs)
        return wrapper
    return decorator


def throughput(
    rate_limiter: Optional[Union[CreditRateLimiter, CountRateLimiter]] = None,
    attribute_name: Optional[str] = None,
    request_credits: Optional[int] = None,
) -> Any:
    """
    Async decorator specifying the Rate Limiter to use, and the credits if any, for any async function or method.
    :param rate_limiter: an instance of CreditRateLimiter or CountRateLimiter
    :param attribute_name: for when the rate limiter is an object attribute
    :param request_credits: the request cost in credits
    :return: the decorated function returned value
    """
    if isinstance(rate_limiter, CreditRateLimiter):
        if request_credits is not None and attribute_name is None:
            return credit_rate_limit(rate_limiter, request_credits)
        else:
            raise ValueError(
                "Wrong parameter(s): when using CreditRateLimiter, 'request_credits' is needed, "
                "while 'attribute_name' must be None"
            )
    elif isinstance(rate_limiter, CountRateLimiter):
        if attribute_name or request_credits:
            raise ValueError(
                "Wrong parameter(s): when using CountRateLimiter, 'request_credits' and 'attribute_name' must be None"
            )
        else:
            return count_rate_limit(rate_limiter)
    elif rate_limiter is None and attribute_name is not None:
        if request_credits is None:
            return count_rate_limit_with_attribute(attribute_name)
        else:
            return credit_rate_limit_with_attribute(attribute_name, request_credits)
    else:
        raise ValueError("Wrong parameter(s): either 'rate_limiter' or 'attribute_name' must be provided")
