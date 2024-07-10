import asyncio
import nats
import uvloop
from json import loads, dumps
from decouple import config
from base64 import b64encode
from loguru import logger
import hmac
import hashlib
import time
from urllib.parse import urljoin
from uuid import uuid1
from decimal import Decimal, ROUND_DOWN
import aiohttp
from kucoin.client import Market, Trade, User, WsToken
from kucoin.ws_client import KucoinWsClient
from datetime import datetime


passphrase = config("PASSPHRASE", cast=str)
key = config("KEY", cast=str)
secret = config("SECRET", cast=str)

ledger = {}

base_uri = "https://api.kucoin.com"


def encrypted_msg(msg: str) -> str:
    """Шифрование сообщения для биржи."""
    return b64encode(
        hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest(),
    ).decode()


def get_payload(
    side: str,
    symbol: str,
    price: int,
    size: str,
    timeInForce: str,
    cancelAfter: int,
):
    return dumps(
        {
            "clientOid": "".join([each for each in str(uuid1()).split("-")]),
            "side": side,
            "type": "limit",
            "price": str(price),
            "symbol": symbol,
            "size": size,
            "timeInForce": timeInForce,
            "cancelAfter": cancelAfter,
            "autoBorrow": True,
            "autoRepay": True,
        },
    )


async def make_limit_order(
    side: str,
    price: int,
    symbol: str,
    size: str,
    timeInForce: str = "GTC",
    cancelAfter: int = 0,
    method: str = "POST",
    method_uri: str = "/api/v1/orders",
):
    """Make limit order by price."""

    now_time = int(time.time()) * 1000

    data_json = get_payload(
        side=side,
        symbol=symbol,
        price=price,
        size=size,
        timeInForce=timeInForce,
        cancelAfter=cancelAfter,
    )

    logger.debug(data_json)

    uri_path = method_uri + data_json
    str_to_sign = str(now_time) + method + uri_path

    headers = {
        "KC-API-SIGN": encrypted_msg(str_to_sign),
        "KC-API-TIMESTAMP": str(now_time),
        "KC-API-PASSPHRASE": encrypted_msg(passphrase),
        "KC-API-KEY": key,
        "Content-Type": "application/json",
        "KC-API-KEY-VERSION": "2",
        "User-Agent": "kucoin-python-sdk/2",
    }

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            urljoin(base_uri, method_uri),
            headers=headers,
            data=data_json,
        ) as response,
    ):
        res = await response.json()
        logger.debug(res)


async def main():
    nc = await nats.connect("nats")

    js = nc.jetstream()

    await js.add_stream(name="kcn", subjects=["candle", "balance"])

    async def candle(msg):
        symbol = loads(msg.data)

        logger.info(symbol)
        # new_price = Decimal(price_str)
        # l = ledger[symbol] * new_price

        # if balance > base_keep:
        #     total = balance - base_keep
        #     tokens_count = total / new_open_price
        #     side = 'sell'
        # elif balance < base_keep:
        #     total = base_keep - balance
        #     tokens_count = total / new_open_price
        #     side = 'buy'

        # await make_limit_order(
        #                 side=side,
        #                 price=str(new_open_price),
        #                 symbol=symbol,
        #                 size=str(
        #                     tokens_count.quantize(
        #                         order_book[data["symbol"]]["baseIncrement"],
        #                         ROUND_DOWN,
        #                     )
        #                 ),  # округление
        #                 timeInForce="GTT",
        #                 cancelAfter=60 * 60,  # ровно час
        #                 method_uri="/api/v1/margin/order",
        #             )

        await msg.ack()

    async def balance(msg):
        data = loads(msg.data)
        ledger.update(
            {
                data["symbol"]: {
                    "baseincrement": data["baseincrement"],
                    "available": data["available"],
                }
            }
        )
        await msg.ack()

    await js.subscribe("candle", "candle", cb=candle)
    await js.subscribe("balance", "balance", cb=balance)

    await asyncio.sleep(60 * 60 * 24 * 365)


if __name__ == "__main__":
    uvloop.run(main())
