"""Tools for Alertest."""

from time import time
from urllib.parse import urljoin

import aiohttp
import pendulum
from loguru import logger
from orjson import loads

from models import Access, Telegram


def get_data_json(params: dict) -> str:
    """Convert dict to url params."""
    data_json = ""

    data_json += "&".join([f"{key}={params[key]}" for key in sorted(params)])
    return data_json


async def request(
    url: str,
    method: str,
    headers: dict,
    *,
    data_json: str | None = None,
) -> dict:
    """Universal http reqponse."""
    async with (
        aiohttp.ClientSession(headers=headers) as session,
        session.request(method, url, data=data_json) as response,
    ):
        res = await response.read()  # bytes
        data = loads(res)  # dict ['code':str, 'data':dict]

        match data["code"]:
            case "200000":
                result = data["data"]
                logger.success(f"{response.status}:{method}:{url}")
            case _:
                logger.warning(f"{response.status}:{method}:{url}:{headers}")
                result = {}

        return result


def get_headers(
    access: Access = None,
    str_to_sign: str = "",
    now_time: str = "",
    *,
    auth: bool = True,
) -> dict:
    """Get headers for request."""
    if auth:
        result = {
            "KC-API-SIGN": access.encrypted(str_to_sign),
            "KC-API-TIMESTAMP": now_time,
            "KC-API-PASSPHRASE": access.encrypted(access.passphrase),
            "KC-API-KEY": access.key,
            "Content-Type": "application/json",
            "KC-API-KEY-VERSION": "2",
            "User-Agent": "kucoin-python-sdk/2",
        }
    else:
        result = {
            "User-Agent": "kucoin-python-sdk/2",
        }

    return result


async def get_symbol_list(
    access: Access,
    *,
    method: str = "GET",
    uri: str = "/api/v2/symbols",
) -> dict:
    """Get all tokens in excange."""
    logger.info("Run get_symbol_list")
    return await request(
        urljoin(access.base_uri, uri),
        method,
        get_headers(auth=False),
    )


async def get_margin_account(
    access: Access,
    params: dict,
    *,
    method: str = "GET",
    uri: str = "/api/v3/margin/accounts",
) -> dict:
    """Get margin account user data."""
    logger.info("Run get_margin_account")

    uri += "?" + get_data_json(params)
    now_time = str(int(time()) * 1000)

    return await request(
        urljoin(access.base_uri, uri),
        method,
        get_headers(
            access,
            f"{now_time}{method}{uri}",
            now_time,
        ),
    )


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


async def get_filled_order_list(
    access: Access,
    params: dict,
    *,
    method: str = "GET",
    uri: str = "/api/v1/orders",
) -> dict:
    """Get all active orders in excange."""
    logger.info("Run get_order_list")

    uri += "?" + get_data_json(params)
    now_time = str(int(time()) * 1000)

    return await request(
        urljoin(access.base_uri, uri),
        method,
        get_headers(
            access,
            f"{now_time}{method}{uri}",
            now_time,
        ),
    )
