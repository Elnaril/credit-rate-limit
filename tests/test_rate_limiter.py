import asyncio
import logging
import time

import pytest

from credit_rate_limit import (
    CountRateLimiter,
    CreditRateLimiter,
    throughput,
)
from credit_rate_limit.rate_limiter import (
    count_rate_limit_with_attribute,
    credit_rate_limit_with_attribute,
)


@pytest.mark.parametrize(
    "name, adjustment, calls, expected_logs, unexpected_logs, expected_duration",
    (
        ("RL 1", 0, 4, [], ["Rate Limiter RL 1 has reached its limit of 5 calls per 1 s", "Rate Limiter RL 1 has reached its limit of 5 calls per 1 s"], 1),  # noqa
        ("RL 2", 0, 5, ["Rate Limiter RL 2 has reached its limit of 5 calls per 1 s", ], ["Rate Limiter RL 2 is back under its limit of 200 credits per 1 s"], 1),  # noqa
        ("RL 3", 0.9, 6, ["Rate Limiter RL 3 has reached its limit of 5 calls per 1 s", "Rate Limiter RL 3 has reached its limit of 5 calls per 1 s"], [], 2),  # noqa
    )
)
async def test_rate_limiter(name, adjustment, calls, expected_logs, unexpected_logs, expected_duration, caplog):
    rate_limiter = CountRateLimiter(5, 1, name=name, adjustment=adjustment)
    caplog.set_level(logging.DEBUG)

    # @count_rate_limit(rate_limiter=rate_limiter)
    @throughput(rate_limiter=rate_limiter)
    async def simulate_api_call():
        await asyncio.sleep(1)

    coros = [simulate_api_call() for _ in range(calls)]
    start = time.time()
    await asyncio.gather(*coros)
    duration = time.time() - start
    print("Duration: ", duration, " / ", "Expected: ", expected_duration)
    assert expected_duration * 0.9 < duration < expected_duration * 1.1

    for log in expected_logs:
        assert log in caplog.text


@pytest.mark.parametrize(
    "name, adjustment, calls, expected_logs, unexpected_logs, expected_duration",
    (
        ("CRL 1", 0.5, 4, [], ["Credit Rate Limiter CRL 3 is using more than 90% of its 200 credits per 1 s", "Credit Rate Limiter CRL 1 is back under its limit of 200 credits per 1 s"], 1),  # noqa
        ("CRL 2", 0.5, 5, ["Credit Rate Limiter CRL 2 is using more than 90% of its 200 credits per 1 s"], ["Credit Rate Limiter CRL 2 is back under its limit of 200 credits per 1 s"], 1),  # noqa
        ("CRL 3", 1, 6, ["Credit Rate Limiter CRL 3 is using more than 90% of its 200 credits per 1 s", "Credit Rate Limiter CRL 3 is back under its limit of 200 credits per 1 s"], [], 2),  # noqa
    )
)
async def test_credit_rate_limiter(name, adjustment, calls, expected_logs, unexpected_logs, expected_duration, caplog):
    rate_limiter = CreditRateLimiter(200, 1, name=name, adjustment=adjustment)
    caplog.set_level(logging.DEBUG)

    # @credit_rate_limit(rate_limiter=rate_limiter, request_credits=40)
    @throughput(rate_limiter, request_credits=40)
    async def simulate_api_call():
        await asyncio.sleep(1)

    coros = [simulate_api_call() for _ in range(calls)]
    start = time.time()
    await asyncio.gather(*coros)
    duration = time.time() - start
    print("Duration: ", duration, " / ", "Expected: ", expected_duration)
    assert expected_duration * 0.9 < duration < expected_duration * 1.1

    for log in expected_logs:
        assert log in caplog.text

    for log in unexpected_logs:
        assert log not in caplog.text


async def test_attribute_credit_rate_limiter():
    class MyClass:
        def __init__(self):
            self.my_credit_rate_limiter = CreditRateLimiter(200, 1, name="CRL as attribute", adjustment=1)

        # @credit_rate_limit_with_attribute("my_credit_rate_limiter", 40)
        @throughput(attribute_name="my_credit_rate_limiter", request_credits=40)
        async def simulate_api_call(self):
            await asyncio.sleep(1)

        @count_rate_limit_with_attribute(attribute_name="my_credit_rate_limiter")
        async def simulate_api_call_wrong_rate_limiter(self):
            pass  # pragma: no cover

    my_class = MyClass()
    coros = [my_class.simulate_api_call() for _ in range(6)]
    start = time.time()
    await asyncio.gather(*coros)
    duration = time.time() - start
    print("Duration: ", duration, " / ", "Expected: ", 2)
    assert 2 * 0.9 < duration < 2 * 1.1

    with pytest.raises(ValueError):
        await my_class.simulate_api_call_wrong_rate_limiter()


async def test_attribute_rate_limiter():
    class MyClass:
        def __init__(self):
            self.my_rate_limiter = CountRateLimiter(5, 1, name="RL as attribute", adjustment=0.9)

        # @rate_limit_with_attribute("my_rate_limiter")
        @throughput(attribute_name="my_rate_limiter")
        async def simulate_api_call(self):
            await asyncio.sleep(1)

        @credit_rate_limit_with_attribute(attribute_name="my_rate_limiter", request_credits=1)
        async def simulate_api_call_wrong_rate_limiter(self):
            pass  # pragma: no cover

    my_class = MyClass()
    coros = [my_class.simulate_api_call() for _ in range(6)]
    start = time.time()
    await asyncio.gather(*coros)
    duration = time.time() - start
    print("Duration: ", duration, " / ", "Expected: ", 2)
    assert 2 * 0.9 < duration < 2 * 1.1

    with pytest.raises(ValueError):
        await my_class.simulate_api_call_wrong_rate_limiter()


def test_exceptions():
    with pytest.raises(ValueError):
        throughput(rate_limiter=CreditRateLimiter(200, 1))

    with pytest.raises(ValueError):
        throughput(rate_limiter=CreditRateLimiter(200, 1), attribute_name="rate_limiter")

    with pytest.raises(ValueError):
        throughput(rate_limiter=CountRateLimiter(5, 1), attribute_name="rate_limiter")

    with pytest.raises(ValueError):
        throughput(rate_limiter=CountRateLimiter(5, 1), request_credits=1)

    with pytest.raises(ValueError):
        throughput()

    with pytest.raises(ValueError):
        throughput(request_credits=10)
