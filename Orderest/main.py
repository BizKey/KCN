import asyncio
import uvloop
from json import loads, dumps
from decouple import config
from base64 import b64encode
from loguru import logger
from decimal import Decimal
import hmac
import hashlib
import time
from urllib.parse import urljoin
from uuid import uuid1
import aiohttp

from datetime import datetime, timedelta

key = config("KEY", cast=str)
secret = config("SECRET", cast=str).encode("utf-8")
passphrase = config("PASSPHRASE", cast=str)
base_stable = config("BASE_STABLE", cast=str)
time_shift = config("TIME_SHIFT", cast=str)
base_stake = Decimal(config("BASE_STAKE", cast=int))
base_keep = Decimal(config("BASE_KEEP", cast=int))

ledger = {}

base_uri = "https://api.kucoin.com"


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
    uri_path = "/api/v1/orders"
    data_json = ""
    now_time = str(int(time.time()) * 1000)

    method = "GET"

    params = {"type": "limit", "tradeType": "MARGIN_TRADE", "status": "active"}

    strl = []
    for key in sorted(params):
        strl.append("{}={}".format(key, params[key]))
    data_json += "&".join(strl)
    uri += "?" + data_json
    uri_path = uri

    logger.info(data_json)

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
        orders = await get_order_list()

        logger.info(orders)

        # for item in orders["items"]:
        #     if datetime.fromtimestamp(int(time.time())) + timedelta(
        #         hours=1
        #     ) > datetime.fromtimestamp(item["createdAt"] / 1000):
        #         # order was claim more 1 hour ago
        #         await cancel_order_by_id(item["id"])

        await asyncio.sleep(60)


if __name__ == "__main__":
    uvloop.run(main())
