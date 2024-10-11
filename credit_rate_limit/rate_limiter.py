"""
Easily rate limit async requests to API using credits, computation unit per second (CUPS) or request units,
in addition to those just counting the number of requests per time unit

* Author: Elnaril (https://www.fiverr.com/elnaril, https://github.com/Elnaril).
* License: MIT.
* Doc: https://github.com/Elnaril/credit-rate-limit
"""
from abc import (
    ABC,
    abstractmethod,
)
import asyncio
from functools import wraps
import logging
import time
from typing import (
    Any,
    List,
    Optional,
    Protocol,
    Tuple,
    Union,
)
from uuid import uuid4


logger = logging.getLogger(__name__)


class AbstractRateLimiter(ABC):
    def __init__(self, retry: float = 0.1, name: Optional[str] = None) -> None:
        self.retry = retry
        self.name = uuid4() if name is None else name

    @abstractmethod
    async def __aenter__(self) -> "AbstractRateLimiter":
        ...

    @abstractmethod
    async def __aexit__(self, exception_type: Any, exception_val: Any, exception_traceback: Any) -> None:
        ...


class CreditRateLimiter(AbstractRateLimiter):
    def __init__(self, max_credits: int, interval: float, retry: float = 0.1, name: Optional[str] = None) -> None:
        """
        Configure a rate limit of max_credit per interval seconds (for API using credits, CUPS, request units, ...)
        :param max_credits: number of allowed credits per interval
        :param interval: duration in seconds on which is defined the rate limit.
        :param retry: check rate limit every "retry" seconds once max_credits is reached
        :param name: an optional name to easily identify the instance
        """
        super().__init__(retry=retry, name=name)
        self.max_credits = max_credits
        self.interval = interval
        self.timestamped_credits: List[Tuple[float, int]] = []
        self.request_credits: int = -1

    def credit_sum(self) -> int:
        return sum(map(lambda t: t[1], self.timestamped_credits))

    def __call__(self, request_credits: int) -> "CreditRateLimiter":
        self.request_credits = request_credits
        return self

    async def __aenter__(self) -> "CreditRateLimiter":
        while True:
            now = time.time()
            while self.timestamped_credits:
                if now - self.timestamped_credits[0][0] > self.interval:
                    current_credits = self.credit_sum()
                    self.timestamped_credits.pop(0)
                    if current_credits >= self.max_credits > self.credit_sum():
                        logging.debug(
                            f"Credit Rate Limiter {self.name} is back under its limit of "
                            f"{self.max_credits} credits per {self.interval} s"
                        )
                else:
                    break

            if self.credit_sum() < self.max_credits:
                break

            await asyncio.sleep(self.retry)

        current_credits = self.credit_sum()
        self.timestamped_credits.append((time.time(), self.request_credits))
        if current_credits < self.max_credits <= self.credit_sum():
            logging.debug(
                f"Credit Rate Limiter {self.name} has reached its limit of"
                f" {self.max_credits} credits per {self.interval} s"
            )
        return self

    async def __aexit__(self, exception_type: Any, exception_val: Any, exception_traceback: Any) -> None:
        self.request_credits = -1


class CountRateLimiter(AbstractRateLimiter):
    def __init__(self, max_count: int, interval: float, retry: float = 0.1, name: Optional[str] = None) -> None:
        """
        Configure a rate limit of max_count requests per interval seconds.
        :param max_count: number of allowed requests per interval
        :param interval: duration in seconds on which is defined the rate limit.
        :param retry: check rate limit every "retry" seconds once max_count is reached
        :param name: an optional name to easily identify the instance
        """
        super().__init__(retry=retry, name=name)
        self.max_count = max_count
        self.interval = interval
        self.timestamps: List[float] = []

    async def __aenter__(self) -> "CountRateLimiter":
        while True:
            now = time.time()
            while self.timestamps:
                if now - self.timestamps[0] > self.interval:
                    self.timestamps.pop(0)
                    if len(self.timestamps) == self.max_count - 1:
                        logging.debug(
                            f"Rate Limiter {self.name} is back under its limit of "
                            f"{self.max_count} requests per {self.interval} s"
                        )
                else:
                    break

            if len(self.timestamps) < self.max_count:
                break

            await asyncio.sleep(self.retry)

        self.timestamps.append(time.time())
        if len(self.timestamps) == self.max_count:
            logging.debug(
                f"Rate Limiter {self.name} has reached its limit of "
                f"{self.max_count} requests per {self.interval} s"
            )
        return self

    async def __aexit__(self, exception_type: Any, exception_val: Any, exception_traceback: Any) -> None:
        pass


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


def rate_limit(rate_limiter: CountRateLimiter) -> Any:
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


def rate_limit_with_attribute(attribute_name: str) -> Any:
    def decorator(func: DecoratedSignature) -> Any:
        @wraps(func)
        def wrapper(self_: CountRateLimiter, *args: Any, **kwargs: Any) -> Any:
            rate_limiter = getattr(self_, attribute_name)
            if not isinstance(rate_limiter, CountRateLimiter):
                raise ValueError(f"rate_limiter must be of type CountRateLimiter. Got {type(rate_limiter)}")
            return rate_limit(rate_limiter)(func)(self_, *args, **kwargs)
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
    :param attribute_name:
    :param request_credits:
    :return:
    """
    if isinstance(rate_limiter, CreditRateLimiter):
        if request_credits and attribute_name is None:
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
            return rate_limit(rate_limiter)
    elif rate_limiter is None and attribute_name is not None:
        if request_credits is None:
            return rate_limit_with_attribute(attribute_name)
        else:
            return credit_rate_limit_with_attribute(attribute_name, request_credits)
    else:
        raise ValueError("Wrong parameter(s): either 'rate_limiter' or 'attribute_name' must be provided")
