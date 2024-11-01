"""Tools for Alertest."""

from time import time
from urllib.parse import urljoin

import aiohttp
import pendulum
from loguru import logger

from models import Access, Telegram


async def get_symbol_list(access: Access) -> list:
    """Get all tokens in excange."""
    logger.info("Run get_symbol_list")

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            urljoin(access.base_uri, "/api/v2/symbols"),
            headers={"User-Agent": "kucoin-python-sdk/2"},
        ) as response,
    ):
        return await response.json()


async def get_margin_account(
    access: Access,
) -> list:
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
            urljoin(access.base_uri, uri),
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


async def send_telegram_msg(telegram: Telegram, text: str) -> None:
    """Send msg to telegram."""
    for chat_id in telegram.get_bot_chat_id():
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                telegram.get_telegram_url(),
                json={
                    "chat_id": chat_id,
                    "parse_mode": "HTML",
                    "disable_notification": True,
                    "text": text,
                },
            ),
        ):
            pass


MAX_HOUR = 23


def check_max_hour(start: pendulum.datetime) -> int:
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
