"""Tools for Orderest."""

from time import time
from urllib.parse import urljoin

import aiohttp
from loguru import logger

from models import Access


async def get_server_timestamp(access: Access) -> dict:
    """Get timestamp from excange server."""
    uri = "/api/v1/timestamp"
    data_json = ""
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
        res = await response.json()
        match res["code"]:
            case "200000":
                result = res
            case _:
                logger.warning(res)
                result = {}

        return result


async def cancel_order(access: Access, orderid: str) -> None:
    """Cancel order by number."""
    uri = f"/api/v1/orders/{orderid}"
    data_json = ""
    uri_path = uri

    now_time = str(int(time()) * 1000)
    str_to_sign = str(now_time) + "DELETE" + uri_path

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


async def get_order_list(access: Access) -> dict:
    """Get all active orders in excange."""
    uri = "/api/v1/orders"
    data_json = ""
    params = {"type": "limit", "tradeType": "MARGIN_TRADE", "status": "active"}
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
        res = await response.json()
        match res["code"]:
            case "200000":
                result = res
            case _:
                logger.warning(res)
                result = {}

        return result
