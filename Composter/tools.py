"""Tools for Composter."""

from collections.abc import Generator

import aiohttp
from loguru import logger
from orjson import loads

from models import Access


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


def divide_chunks(length: list, number: int) -> Generator:
    """Функция разбиения словаря на подсловари по number значений."""
    for itr in range(0, len(length), number):
        yield length[itr : itr + number]


async def get_public_token(
    method: str = "POST",
    url: str = "https://api.kucoin.com/api/v1/bullet-public",
) -> dict:
    """Get auth data for create websocket connection."""
    return await request(
        url,
        method,
        get_headers(auth=False),
    )
