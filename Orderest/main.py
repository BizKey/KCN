import asyncio
import uvloop
from json import loads, dumps
from decouple import config
from base64 import b64encode
from loguru import logger
from kucoin.client import Trade, Market
from decimal import Decimal
import hmac
import hashlib
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


async def get_order_list():
    """Get all active orders."""
    uri = "/api/v1/orders"
    uri_path = uri
    data_json = ""
    now_time = str(int(time.time()) * 1000)

    method = "GET"

    params = {"type": "limit", "tradeType": "MARGIN_TRADE", "status": "active"}

    strl = []
    for key_ in sorted(params):
        strl.append("{}={}".format(key_, params[key]))
    data_json += "&".join(strl)
    uri += "?" + data_json
    uri_path = uri

    logger.info(uri_path)

    async with (
        aiohttp.ClientSession() as session,
        session.get(
            urljoin(base_uri, uri),
            headers={
                "KC-API-SIGN": encrypted_msg(now_time + method + uri_path),
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
        if res["code"] != "200000":
            logger.warning(res)
        return res


async def cancel_order_by_id(id_: str):
    """Cancel order by ID."""
    method_uri = f"/api/v1/orders/{id_}"

    method = "DELETE"

    now_time = str(int(time.time()) * 1000)

    async with (
        aiohttp.ClientSession() as session,
        session.delete(
            urljoin(base_uri, method_uri),
            headers={
                "KC-API-SIGN": encrypted_msg(
                    now_time + method + method_uri + data_json
                ),
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
        logger.info(res)


async def main():
    while True:
        servertimestamp = market.get_server_timestamp()
        orders = trade.get_order_list(
            **{"type": "limit", "tradeType": "MARGIN_TRADE", "status": "active"}
        )

        for item in orders["items"]:
            if servertimestamp > item["createdAt"] + 3500000:
                # order was claim more 1 hour ago
                logger.warning(f"Need cancel:{item}")

                trade.cancel_order(item["id"])

        await asyncio.sleep(60)


if __name__ == "__main__":
    uvloop.run(main())
