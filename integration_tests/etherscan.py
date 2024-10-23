import asyncio
import logging
import os
import time

from aiohttp import ClientSession

from credit_rate_limit import CountRateLimiter, throughput

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
api_key = os.environ["ETHERSCAN_API_KEY"]

# if the API complains about the rate limit, remove the 'adjustment' parameter
rate_limiter_1 = CountRateLimiter(max_count=5, interval=1, adjustment=0.1)
rate_limiter_2 = CountRateLimiter(max_count=5, interval=1, adjustment=1.0)


@throughput(rate_limiter=rate_limiter_1)
async def get_block_number_by_timestamp(session, timestamp):
    params = {
        "module": "block",
        "action": "getblocknobytime",
        "timestamp": timestamp,
        "closest": "before",
        "apikey": api_key,
    }
    async with session.get(url="https://api.etherscan.io/api", params=params) as resp:
        request_starts_at = time.perf_counter()
        logger.debug(f"Request starts at: {request_starts_at}")
        resp_body = await resp.json()
        request_ends_at = time.perf_counter()
        block_number = int(resp_body["result"])
        logger.info(
            f"Request ends at: {request_ends_at} - Duration: {request_ends_at - request_starts_at} - "
            f"Timestamp {timestamp} => Block number {block_number}"
        )


async def run_get_block_number(request_numbers: int):
    async with ClientSession() as session:
        coros = []
        for t in range(1729000000, 1729000000 + 100 * request_numbers, 100):
            coros.append(get_block_number_by_timestamp(session, t))
        await asyncio.gather(*coros)


@throughput(rate_limiter=rate_limiter_2)
async def get_tx_list(session, start_block, end_block):
    params = {
        "module": "account",
        "action": "txlist",
        "address": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
        "startblock": start_block,
        "endblock": end_block,
        "page": 1,
        "offset": 10_000,
        "sort": "asc",
        "apikey": api_key,
    }
    async with session.get(url="https://api.etherscan.io/api", params=params) as resp:
        request_starts_at = time.perf_counter()
        logger.debug(f"Request starts at: {request_starts_at}")
        resp_body = await resp.json()
        request_ends_at = time.perf_counter()
        trx_count = len(resp_body["result"])
        logger.info(
            f"Request ends at: {request_ends_at} - Duration: {request_ends_at - request_starts_at} - "
            f"Got {trx_count} transactions between block [{start_block}, {end_block}]"
        )


async def run_get_tx_list(request_numbers: int):
    async with ClientSession() as session:
        coros = []
        for i in range(request_numbers):
            block = 20600000 + 1000 * i
            coros.append(get_tx_list(session, block, block + 10000))
        await asyncio.gather(*coros)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    start = time.perf_counter()
    calls = 100
    logger.info(f"Running {calls} fast requests")
    loop.run_until_complete(run_get_block_number(calls))
    duration = time.perf_counter() - start
    logger.info(f"{duration=}\n")

    start = time.perf_counter()
    calls = 20
    logger.info(f"Running {calls} slower requests")
    loop.run_until_complete(run_get_tx_list(calls))
    duration = time.perf_counter() - start
    logger.info(f"{duration=}\n")
