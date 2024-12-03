"""Tools for Orderest."""

from datetime import UTC, datetime
from time import time
from urllib.parse import urljoin

import aiohttp
from loguru import logger
from orjson import loads

from models import Access


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


async def cancel_order(
    access: Access,
    uri: str,
    *,
    method: str = "DELETE",
) -> None:
    """Cancel order by number."""
    logger.info("Run cancel_order")

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


async def get_order_list(
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


def get_seconds_to_next_minutes(minutes: int) -> int:
    """Get next 10:00 minutes."""
    logger.info("Run get_seconds_to_next_minutes")

    now = datetime.now(tz=UTC)

    if now.minute > minutes:
        result_minute = 60 - now.minute + minutes
    elif now.minute < minutes:
        result_minute = minutes - now.minute
    else:
        result_minute = minutes

    return result_minute * 60
