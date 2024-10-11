# Credit Rate Limiter

> Easily rate limit async requests to API using credits, computation unit per second (CUPS) or request units, in addition to those just counting the number of requests per time unit
 
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

If you wish to define a "Rate Limiter" as a class attribute, just gives its name as a `str` to the decorator:

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
