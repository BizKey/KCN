import asyncio
import uvloop
from json import loads, dumps
from decouple import config, Csv
from base64 import b64encode
from loguru import logger
from kucoin.client import Trade, Market
from decimal import Decimal
import hmac
import hashlib
from kucoin.client import WsToken, User, Market
import time
from urllib.parse import urljoin
from uuid import uuid1
import aiohttp

from datetime import datetime, timedelta

key = config("KEY", cast=str)
secret = config("SECRET", cast=str)
passphrase = config("PASSPHRASE", cast=str)
base_stable = config("BASE_STABLE", cast=str)
time_shift = config("TIME_SHIFT", cast=str)
base_stake = Decimal(config("BASE_STAKE", cast=int))
base_keep = Decimal(config("BASE_KEEP", cast=int))


all_currency = config("ALLCURRENCY", cast=Csv(str)) # Tokens for trade in bot
ignore_currency = config("IGNORECURRENCY", cast=Csv(str)) # Tokens for ignore
accept_tokens = [] # All tokens from exchange
new_tokens = [] # New tokens, don't find in all_currency
del_tokens = [] # Tokens what didn't in exchange

ledger = {}

base_uri = "https://api.kucoin.com"

trade = Trade(
    key=key,
    secret=secret,
    passphrase=passphrase,
)

market = Market(url="https://api.kucoin.com")


def get_actual_token_stats():
    for tokens in market.get_symbol_list_v2():
        logger.info(tokens)
    # get all tokens from market.get_symbol_list_v2()
    # filter tokens
    # for item in d["data"]:
    # symbol = item["symbol"].replace("-USDT", "")
    #     if (
    #         item["isMarginEnabled"]
    #         and item["quoteCurrency"] == "USDT"
    #         and symbol not in ignore_currency
    #     ):
    #         print(item)
    #         accept_tokens.append(symbol)
    #         if symbol not in use_tokens:
    #             new_tokens.append(symbol)
    # for used in use_tokens:
    #     if used not in all_currency:
    #         del_tokens.append(used)


#     print(
#     f"""
# All tokens:{len(accept_tokens)}
# Used tokens({len(all_currency)})
# Deleted({len(del_tokens)}):{",".join(del_tokens)}
# New({len(new_tokens)}):{",".join(new_tokens)}
# Ignore({len(ignore_currency)}):{",".join(ignore_currency)}
# """
# )

async def main():
    while True:
        get_actual_token_stats()

        await asyncio.sleep(60)


if __name__ == "__main__":
    uvloop.run(main())