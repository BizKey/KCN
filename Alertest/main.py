"""Alertest."""

import asyncio
import hashlib
import hmac
from base64 import b64encode
from decimal import Decimal
from time import time
from urllib.parse import urljoin

import aiohttp
import pendulum
import uvloop
from decouple import Csv, config
from loguru import logger

from models import Access, Token

telegram_bot_key = config("TELEGRAM_BOT_API_KEY", cast=str)

MAX_HOUR = 23


def check_max_hour(start: pendulum.datetime.DateTime) -> int:
    """Check if hour is more when MAX_HOUR."""
    hour = start.hour + 1

    if start.hour == MAX_HOUR:
        start = pendulum.tomorrow()
        hour = 0

    return start, hour


def get_seconds_to_next_minutes(minutes: int) -> int:
    """Get next 10:00 minutes."""
    logger.info("Run get_seconds_to_next_minutes")

    start = pendulum.now("Europe/Moscow")

    hour = start.hour
    if start.minute >= minutes:
        start, hour = check_max_hour(start)

    return (start.at(minute=minutes, hour=hour) - start).in_seconds()


base_uri = "https://api.kucoin.com"

telegram_url = f"https://api.telegram.org/bot{telegram_bot_key}/sendMessage"


def encrypted_msg(msg: str) -> str:
    """Шифрование сообщения для биржи."""
    return b64encode(
        hmac.new(
            secret,
            msg.encode("utf-8"),
            hashlib.sha256,
        ).digest(),
    ).decode()


async def get_symbol_list() -> list:
    """Get all tokens in excange."""
    logger.info("Run get_symbol_list")

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            urljoin(base_uri, "/api/v2/symbols"),
            headers={"User-Agent": "kucoin-python-sdk/2"},
        ) as response,
    ):
        return await response.json()


async def get_margin_account(access: Access) -> list:
    """Get margin account user data."""
    logger.info("Run get_margin_account")

    uri = "/api/v3/margin/accounts"
    data_json = ""
    params = {"quoteCurrency": "USDT"}
    strl = [f"{key}={params[key]}" for key in sorted(params)]
    data_json += "&".join(strl)
    uri += "?" + data_json
    uri_path = uri

    now_time = str(int(time()) * 1000)
    str_to_sign = str(now_time) + "GET" + uri_path

    async with (
        aiohttp.ClientSession() as session,
        session.get(
            urljoin(base_uri, uri),
            headers={
                "KC-API-SIGN": access.encrypted(str_to_sign),
                "KC-API-TIMESTAMP": now_time,
                "KC-API-PASSPHRASE": access.encrypted(access.passphrase),
                "KC-API-KEY": access.key,
                "Content-Type": "application/json",
                "KC-API-KEY-VERSION": "2",
                "User-Agent": "kucoin-python-sdk/2",
            },
            data=data_json,
        ) as response,
    ):
        return await response.json()


async def send_telegram_msg(text: str) -> None:
    """Send msg to telegram."""
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


def get_telegram_msg(
    available_funds: dict,
    tokens: dict,
    ignore_currency: list,  # Ignore token for trade
) -> str:
    """Prepare telegram msg."""
    borrow = available_funds["borrow_size"] - available_funds["avail_size"]
    len_all_currency = len(all_currency)
    percent_borrow = borrow * 100 / (len_all_currency * float(base_keep))

    return f"""<b>KuCoin</b>

              <i>KEEP</i>:{base_keep}
              <i>USDT</i>:{available_funds['avail_size']:.2f}
              <i>BORROWING USDT</i>:{borrow:.2f} ({percent_borrow:.2f}%)
              <i>ALL TOKENS</i>:{len(tokens['accept_tokens'])}
              <i>USED TOKENS</i>({len_all_currency})
              <i>DELETED</i>({len(tokens['del_tokens'])}):{",".join(tokens['del_tokens'])}
              <i>NEW</i>({len(tokens['new_tokens'])}):{",".join(tokens['new_tokens'])}
              <i>IGNORE</i>({len(ignore_currency)}):{",".join(ignore_currency)}"""


async def get_available_funds(access: Access) -> dict:
    """Get available funds in excechge."""
    logger.info("Run get_available_funds")
    avail_size = 0.0
    borrow_size = 0.0

    margin_account = await get_margin_account(access)["accounts"]

    for i in [i for i in margin_account if i["currency"] == "USDT"]:
        borrow_size = float(i["liability"])
        avail_size = float(i["available"])

    return {"avail_size": avail_size, "borrow_size": borrow_size}


def get_accept_tokens(symbol_list: list) -> list:
    """Get all accepted token from excenga."""
    logger.info("Run get_accept_tokens")
    return [
        token["symbol"].replace("-USDT", "")
        for token in symbol_list
        if token["isMarginEnabled"]
        and token["quoteCurrency"] == "USDT"
        and token["symbol"].replace("-USDT", "") not in ignore_currency
    ]


def get_new_tokens(symbol_list: list) -> list:
    """Get new tokens from excenge."""
    return [
        token["symbol"].replace("-USDT", "")
        for token in symbol_list
        if token["isMarginEnabled"]
        and token["quoteCurrency"] == "USDT"
        and token["symbol"].replace("-USDT", "") not in ignore_currency
        and token["symbol"].replace("-USDT", "") not in all_currency
    ]


async def get_tokens() -> dict:
    """Get available tokens."""
    logger.info("Run get_tokens")
    symbol_list = await get_symbol_list()

    accept_tokens = get_accept_tokens(symbol_list)  # All tokens from exchange

    return {
        "accept_tokens": accept_tokens,
        "new_tokens": get_new_tokens(symbol_list),
        "del_tokens": [used for used in all_currency if used not in accept_tokens],
    }


async def get_actual_token_stats(access: Access) -> None:
    """Get actual all tokens stats."""
    logger.info("Run get_actual_token_stats")
    available_funds = await get_available_funds(access)
    tokens = await get_tokens()

    msg = get_telegram_msg(
        available_funds,
        tokens,
        ignore_currency,
    )
    logger.warning(msg)
    await send_telegram_msg(msg)


async def main() -> None:
    """Main func in microservice.

    wait second to next time with 10:00 minutes equals
    in infinity loop to run get_actual_token_stats
    """
    logger.info("Run Alertest microservice")
    access = Access(
        key=config("KEY", cast=str),
        secret=config("SECRET", cast=str),
        passphrase=config("PASSPHRASE", cast=str),
    )
    token = Token(
        currency=config("ALLCURRENCY", cast=Csv(str)),
        ignore_currency=config("IGNORECURRENCY", cast=Csv(str)),
        base_keep=Decimal(config("BASE_KEEP", cast=int)),
    )

    while True:
        wait_seconds = get_seconds_to_next_minutes(10)

        logger.info(f"Wait {wait_seconds} to run get_actual_token_stats")
        await asyncio.sleep(wait_seconds)

        await get_actual_token_stats(access)


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        runner.run(main())
