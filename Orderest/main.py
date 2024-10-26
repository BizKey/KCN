"""Orderest."""

import asyncio
import hashlib
import hmac
import time
from base64 import b64encode
from urllib.parse import urljoin

import aiohttp
import uvloop
from decouple import config
from kucoin.client import Market, Trade
from loguru import logger

key = config("KEY", cast=str)
secret = config("SECRET", cast=str)
passphrase = config("PASSPHRASE", cast=str)

ledger = {}

base_uri = "https://api.kucoin.com"

trade = Trade(
    key=key,
    secret=secret,
    passphrase=passphrase,
)

market = Market(url="https://api.kucoin.com")


def encrypted_msg(msg: str) -> str:
    """Шифрование сообщения для биржи."""
    return b64encode(
        hmac.new(
            secret,
            msg.encode("utf-8"),
            hashlib.sha256,
        ).digest(),
    ).decode()


async def get_order_list() -> dict:
    """Get all active orders in excange."""
    uri = "/api/v1/orders"
    data_json = ""
    params = {"type": "limit", "tradeType": "MARGIN_TRADE", "status": "active"}
    strl = [f"{key}={params[key]}" for key in sorted(params)]
    data_json += "&".join(strl)
    uri += "?" + data_json
    uri_path = uri

    now_time = str(int(time.time()) * 1000)
    str_to_sign = str(now_time) + "GET" + uri_path

    async with (
        aiohttp.ClientSession() as session,
        session.get(
            urljoin(base_uri, uri),
            headers={
                "KC-API-SIGN": encrypted_msg(str_to_sign),
                "KC-API-TIMESTAMP": now_time,
                "KC-API-PASSPHRASE": encrypted_msg(passphrase),
                "KC-API-KEY": key,
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


async def get_server_timestamp() -> dict:
    """Get timestamp from excange server."""
    uri = "/api/v1/timestamp"
    data_json = ""
    uri_path = uri
    now_time = str(int(time.time()) * 1000)
    str_to_sign = str(now_time) + "GET" + uri_path

    async with (
        aiohttp.ClientSession() as session,
        session.get(
            urljoin(base_uri, uri),
            headers={
                "KC-API-SIGN": encrypted_msg(str_to_sign),
                "KC-API-TIMESTAMP": now_time,
                "KC-API-PASSPHRASE": encrypted_msg(passphrase),
                "KC-API-KEY": key,
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


async def cancel_order(orderid: str) -> None:
    """Cancel order by number."""
    uri = f"/api/v1/orders/{orderid}"
    data_json = ""
    uri_path = uri

    now_time = str(int(time.time()) * 1000)
    str_to_sign = str(now_time) + "DELETE" + uri_path

    async with (
        aiohttp.ClientSession() as session,
        session.get(
            urljoin(base_uri, uri),
            headers={
                "KC-API-SIGN": encrypted_msg(str_to_sign),
                "KC-API-TIMESTAMP": now_time,
                "KC-API-PASSPHRASE": encrypted_msg(passphrase),
                "KC-API-KEY": key,
                "Content-Type": "application/json",
                "KC-API-KEY-VERSION": "2",
                "User-Agent": "kucoin-python-sdk/2",
            },
            data=data_json,
        ) as response,
    ):
        return await response.json()


async def check_need_cancel(servertimestamp: int, item: dict) -> None:
    """Check if datetime of create order more when 1 hour."""
    if servertimestamp > item["createdAt"] + 3500000:
        # order was claim more 1 hour ago
        logger.warning(f"Need cancel:{item}")
        await cancel_order(item["id"])


async def brute_orders(servertimestamp: int, orders: dict) -> None:
    """Brute order by create time more when 1 hour."""
    for item in orders["items"]:
        await check_need_cancel(servertimestamp, item)


async def main() -> None:
    """Main func in microservice."""
    while True:
        servertimestamp = await get_server_timestamp()
        orders = await get_order_list()
        await brute_orders(servertimestamp, orders)
        await asyncio.sleep(60)


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        runner.run(main())
