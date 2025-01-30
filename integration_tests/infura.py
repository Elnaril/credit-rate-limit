import asyncio
import logging
import os
import time

import web3
from web3 import AsyncWeb3
from web3.middleware import validation
from web3.types import RPCEndpoint

from credit_rate_limit import CreditRateLimiter, throughput

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("web3").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

# if the API complains about the rate limit, remove the 'adjustment' parameter
rate_limiter = CreditRateLimiter(max_credits=500, interval=1, adjustment=0.3)

aw3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(os.environ["WEB3_HTTP_PROVIDER_URL_ETHEREUM_MAINNET"]))

NO_VALIDATION_METHODS = [RPCEndpoint("eth_call")]  # to avoid unnecessary eth_chainId requests
for method in NO_VALIDATION_METHODS:
    if method in validation.METHODS_TO_VALIDATE:
        logger.debug(f"Removing {method} from web3.middleware.validation.METHODS_TO_VALIDATE")
        validation.METHODS_TO_VALIDATE.remove(method)

symbol_abi = '[{"constant": true, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "payable": false, "stateMutability": "view", "type": "function"}]'  # noqa

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


@throughput(rate_limiter=rate_limiter, request_credits=255)
async def get_logs(block_number):
    request_starts_at = time.perf_counter()
    logger.debug(f"Request starts at: {request_starts_at}")
    address = web3.Web3.to_checksum_address('0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f')
    logs = await aw3.eth.get_logs(
        {
            'fromBlock': block_number,
            'toBlock': block_number + 100,
            'address': address,
        }
    )
    request_ends_at = time.perf_counter()
    logger.info(
        f"Request ends at: {request_ends_at} - Duration: {request_ends_at - request_starts_at} - "
        f"address: {logs[0]['address']} == {address} => {logs[0]['address'] == address}"
    )


async def run_logs(request_numbers: int):
    coros = []
    for i in range(request_numbers):
        coros.append(get_logs(21000000 + i))
    await asyncio.gather(*coros)


@throughput(rate_limiter=rate_limiter, request_credits=80)
async def get_token_symbol(contract):
    request_starts_at = time.perf_counter()
    logger.debug(f"Request starts at: {request_starts_at}")
    symbol = await contract.functions.symbol().call({"chainId": 1})
    request_ends_at = time.perf_counter()
    logger.info(
        f"Request ends at: {request_ends_at} - Duration: {request_ends_at - request_starts_at} - "
        f"symbol: {symbol} == WETH => {symbol == 'WETH'}"
    )


async def run_token_symbol(request_numbers: int):
    weth_address = web3.Web3.to_checksum_address('0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2')
    contract = aw3.eth.contract(weth_address, abi=symbol_abi)
    coros = []
    for i in range(request_numbers):
        coros.append(get_token_symbol(contract))
    await asyncio.gather(*coros)


async def launch():
    start = time.perf_counter()
    calls = 100
    logger.info(f"Running {calls} fast requests")
    await run_block_by_number(calls)
    duration = time.perf_counter() - start
    logger.info(f"{duration=}\n")

    start = time.perf_counter()
    calls = 20
    logger.info(f"Running {calls} more expensive requests")
    await run_logs(calls)
    duration = time.perf_counter() - start
    logger.info(f"{duration=}\n")

    start = time.perf_counter()
    calls = 100
    logger.info(f"Running {calls} contract calls")
    await run_token_symbol(calls)
    duration = time.perf_counter() - start
    logger.info(f"{duration=}\n")

if __name__ == "__main__":
    asyncio.run(launch())
