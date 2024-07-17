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
from kucoin.client import WsToken, User, Market, Margin
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

all_currency = config("ALLCURRENCY", cast=Csv(str))  # Tokens for trade in bot
ignore_currency = config("IGNORECURRENCY", cast=Csv(str))  # Tokens for ignore

ledger = {}

base_uri = "https://api.kucoin.com"

trade = Trade(
    key=key,
    secret=secret,
    passphrase=passphrase,
)

margin = Margin(
    key=key,
    secret=secret,
    passphrase=passphrase,
)

user = User(
    key=key,
    secret=secret,
    passphrase=passphrase,
)

market = Market(url="https://api.kucoin.com")

telegram_url = f"https://api.telegram.org/bot{config('TELEGRAM_BOT_API_KEY', cast=str)}/sendMessage"


async def send_telegram_msg(text: str):
    """Отправка сообщения в телеграмм."""
    for chat_id in config("TELEGRAM_BOT_CHAT_ID", cast=Csv(str)):
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                telegram_url,
                json={
                    "chat_id": chat_id,
                    "parse_mode": "HTML",
                    "disable_notification": True,
                    "text": text,
                },
            ),
        ):
            pass


async def get_actual_token_stats():

    accept_tokens = []  # All tokens from exchange
    new_tokens = []  # New tokens, don't find in all_currency
    del_tokens = []  # Tokens what didn't in exchange

    avail_size = '0.0'
    borrow_size= '0.0'

    for token in market.get_symbol_list_v2():
        symbol = token["symbol"].replace("-USDT", "")
        if (
            token["isMarginEnabled"]
            and token["quoteCurrency"] == "USDT"
            and symbol not in ignore_currency
        ):
            accept_tokens.append(symbol)
            if symbol not in all_currency:
                new_tokens.append(symbol)

    for used in all_currency:
        if used not in accept_tokens:
            del_tokens.append(used)

    margin_intere = margin.get_cross_or_isolated_margin_interest_records(
        **{
            "isIsolated": False,
            "symbol": "USDT",
        }
    )
    logger.warning(margin_intere)

    for i in margin_intere["items"]:
        if i["currency"] == "USDT":
            borrow_size = i["interestAmount"]

    logger.warning(f"{borrow_size=}")

    avail_size = user.get_account_list(currency="USDT", account_type="margin")[0][
        "available"
    ]
    logger.warning(f"{avail_size=}")

    msg = f"""
USDT:{avail_size}
Borrowing USDT:{borrow_size}
All tokens:{len(accept_tokens)}
Used tokens({len(all_currency)})
Deleted({len(del_tokens)}):{",".join(del_tokens)}
New({len(new_tokens)}):{",".join(new_tokens)}
Ignore({len(ignore_currency)}):{",".join(ignore_currency)}
"""
    logger.warning(msg)
    await send_telegram_msg(msg)


async def main():
    while True:
        await get_actual_token_stats()
        await asyncio.sleep(60 * 60)


if __name__ == "__main__":
    uvloop.run(main())
