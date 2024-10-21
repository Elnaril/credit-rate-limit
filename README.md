# Credit Rate Limiter

> Easily rate limit async requests to API using credits, computation unit per second (CUPS) or request units, and to those just counting the number of requests per time unit
 
---

#### Project Information
[![Tests & Lint](https://github.com/Elnaril/credit-rate-limit/actions/workflows/tests.yml/badge.svg)](https://github.com/Elnaril/credit-rate-limit/actions/workflows/tests.yml)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/credit-rate-limit)](https://pypi.org/project/credit-rate-limit/)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/Elnaril/credit-rate-limit)](https://github.com/Elnaril/credit-rate-limit/releases)
[![PyPi Repository](https://img.shields.io/badge/repository-pipy.org-blue)](https://pypi.org/project/credit-rate-limit/)
[![GitHub](https://img.shields.io/github/license/Elnaril/credit-rate-limit)](https://github.com/Elnaril/credit-rate-limit/blob/master/LICENSE)

#### Code Quality
[![CodeQL](https://github.com/elnaril/credit-rate-limit/workflows/CodeQL/badge.svg)](https://github.com/Elnaril/credit-rate-limit/actions/workflows/github-code-scanning/codeql)
[![Test Coverage](https://img.shields.io/badge/dynamic/json?color=blueviolet&label=coverage&query=%24.totals.percent_covered_display&suffix=%25&url=https%3A%2F%2Fraw.githubusercontent.com%2FElnaril%2Fcredit-rate-limit%2Fmaster%2Fcoverage.json)](https://github.com/Elnaril/credit-rate-limit/blob/master/coverage.json)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![Type Checker: mypy](https://img.shields.io/badge/%20type%20checker-mypy-%231674b1?style=flat&labelColor=ef8336)](https://mypy-lang.org/)
[![Linter: flake8](https://img.shields.io/badge/%20linter-flake8-%231674b1?style=flat&labelColor=ef8336)](https://flake8.pycqa.org/en/latest/)

---

## Overview

Some APIs enforce a rate limit based on credits (or computation unit per second (CUPS) or request units).
Meaning the call to an endpoint may not weigh as the call to another one.
For example, let's consider a "Compute Unit Costs" sample from an actual crypto related API:

| Method | Compute Units
| ------ | -------------
| eth_chainId | 0
| eth_blockNumber | 10
| eth_getTransactionReceipt | 15
| eth_getBalance | 19
| eth_call | 26
| eth_estimateGas | 87
| eth_sendRawTransaction | 250

It is clear that calling some methods will impact your rate limit more than some others!

This library aims to provide an easy way to limit the rate at which an `async` function or method can be called, considering its own credit cost and the credits already used for a given period.
It also supports rate limitation just based on number of calls.
Finally, you can "group" calls so requesting one API does not impact the rate limit of another one.

It works well for any request pace, but especially well if there are some bursts of fast requests, and it can be optimized for even better performances.

## Installation

```bash
pip install credit-rate-limit
```

## Usage
This library provides 2 "Rate Limiters":
- CreditRateLimiter: for APIs that use credits, computation unit per second (CUPS), request units ...
- CountRateLimiter: for APIs that just counts the number of calls per time unit.

Once the "Rate Limiter" is built, you just have to add the decorator `throughput` to the functions or methods you wish to limit.

### Examples

```python
from credit_rate_limit import CreditRateLimiter, throughput

credit_rate_limiter = CreditRateLimiter(200, 1)  # the API allows 200 credits per 1 second

@throughput(credit_rate_limiter, request_credits=40)  # this function costs 40 credits to call
async def request_api():
    ...

```

If you wish to define a "Rate Limiter" as an object attribute, just gives its name as a `str` to the decorator:

```python
from credit_rate_limit import CreditRateLimiter, throughput

class MyClass:
    def __init__(self):
        self.my_credit_rate_limiter = CreditRateLimiter(200, 1)

    # @throughput(self.my_credit_rate_limiter, request_credits=40)  /!\ Error: self is unknown here !!
    @throughput(attribute_name="my_credit_rate_limiter", request_credits=40)
    async def request_api(self):
        ...
```

`CountRateLimiter` can be used in the same way, albeit without `request_credits`. For example:

```python
from credit_rate_limit import CountRateLimiter, throughput

credit_rate_limiter = CountRateLimiter(5, 1)  # the API allows 5 requests per 1 second


@throughput(credit_rate_limiter)
async def request_api():
    ...

```

### Optimization
Both `CreditRateLimiter` and `CountRateLimiter` have the `adjustment` parameter that can be used to speed up the requests (to some extent)  
It can take any value between `0` (default) and `interval`. A higher value means better performances, but also a higher risk of being rate limited by the API.  
There is no right value: it depends on the API, the request speeds and the network state and would be discovered with tests. 
But if this parameter is correctly set, maybe with a re-try mechanism, it may give a nice performance improvement in some use cases.

```python
rate_limiter = CreditRateLimiter(max_credits=2000, interval=1, adjustment=0.1)
```
