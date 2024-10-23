import asyncio
import logging
import os
import time

from web3 import AsyncWeb3

from credit_rate_limit import CreditRateLimiter, throughput

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("web3").setLevel(logging.WARNING)

# if the API complains about the rate limit, remove the 'adjustment' parameter
rate_limiter = CreditRateLimiter(max_credits=2000, interval=1, adjustment=0.3)

aw3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(os.environ["WEB3_HTTP_PROVIDER_URL_ETHEREUM_MAINNET"]))


@throughput(rate_limiter=rate_limiter, request_credits=80)
async def get_block_by_number(block_number):
    request_starts_at = time.perf_counter()
    logger.debug(f"Request starts at: {request_starts_at}")
    block = await aw3.eth.get_block(block_number)
    request_ends_at = time.perf_counter()
    logger.info(
        f"Request ends at: {request_ends_at} - Duration: {request_ends_at - request_starts_at} - "
        f"block_number: {block['number']}/{block_number}"
    )


async def run_block_by_number(request_numbers: int):
    coros = []
    for i in range(request_numbers):
        coros.append(get_block_by_number(21000000 + i))
    await asyncio.gather(*coros)


@throughput(rate_limiter=rate_limiter, request_credits=1000)
async def get_block_receipts(block_number):
    request_starts_at = time.perf_counter()
    logger.debug(f"Request starts at: {request_starts_at}")
    receipt = await aw3.eth.get_block_receipts(block_number)
    request_ends_at = time.perf_counter()
    logger.info(
        f"Request ends at: {request_ends_at} - Duration: {request_ends_at - request_starts_at} - "
        f"block_number: {receipt[0]['blockNumber']}/{block_number}"
    )


async def run_block_receipts(request_numbers: int):
    coros = []
    for i in range(request_numbers):
        coros.append(get_block_receipts(21000000 + i))
    await asyncio.gather(*coros)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    start = time.perf_counter()
    calls = 100
    logger.info(f"Running {calls} fast requests")
    loop.run_until_complete(run_block_by_number(calls))
    duration = time.perf_counter() - start
    logger.info(f"{duration=}\n")

    start = time.perf_counter()
    calls = 20
    logger.info(f"Running {calls} more expensive requests")
    loop.run_until_complete(run_block_receipts(calls))
    duration = time.perf_counter() - start
    logger.info(f"{duration=}\n")
