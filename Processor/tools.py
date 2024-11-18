"""Tools for Processor."""

from time import time
from urllib.parse import urljoin
from uuid import uuid4

import aiohttp
from loguru import logger
from orjson import dumps, loads

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


async def margin_limit_order(
    access: Access,
    params: dict,
    *,
    method: str = "POST",
    uri: str = "/api/v1/margin/order",
) -> dict:
    """Get all active orders in excange."""
    logger.info("Run get_order_list")

    now_time = str(int(time()) * 1000)

    data_json = dumps(params).decode()

    return await request(
        urljoin(access.base_uri, uri),
        method,
        get_headers(
            access,
            f"{now_time}{method}{uri}{data_json}",
            now_time,
        ),
        data_json=data_json,
    )


async def make_margin_limit_order(
    access: Access,
    side: str,
    price: str,
    symbol: str,
    size: str,
) -> dict:
    """Make limit order by price."""
    logger.info(f"Run make_margin_limit_order:{side}:{symbol}")

    return await margin_limit_order(
        access,
        {
            "clientOid": str(uuid4()).replace("-", ""),
            "side": side,
            "symbol": symbol,
            "price": price,
            "size": size,
            "type": "limit",
            "timeInForce": "GTC",
            "autoBorrow": True,
            "autoRepay": True,
        },
    )
