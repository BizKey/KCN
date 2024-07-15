import asyncio
from nats.aio.client import Client
import uvloop
from json import loads, dumps
from decouple import config
from base64 import b64encode
from loguru import logger
from decimal import Decimal, ROUND_DOWN
import hmac
import hashlib
import time
from urllib.parse import urljoin
from uuid import uuid1
import aiohttp


key = config("KEY", cast=str)
secret = config("SECRET", cast=str).encode("utf-8")
passphrase = config("PASSPHRASE", cast=str)
base_stable = config("BASE_STABLE", cast=str)
time_shift = config("TIME_SHIFT", cast=str)
base_stake = Decimal(config("BASE_STAKE", cast=int))
base_keep = Decimal(config("BASE_KEEP", cast=int))

ledger = {}

base_uri = "https://api.kucoin.com"


async def disconnected_cb(*args: list) -> None:
    """CallBack на отключение от nats."""
    logger.error(f"Got disconnected... {args}")


async def reconnected_cb(*args: list) -> None:
    """CallBack на переподключение к nats."""
    logger.error(f"Got reconnected... {args}")


async def error_cb(excep: Exception) -> None:
    """CallBack на ошибку подключения к nats."""
    logger.error(f"Error ... {excep}")


async def closed_cb(*args: list) -> None:
    """CallBack на закрытие подключения к nats."""
    logger.error(f"Closed ... {args}")


def encrypted_msg(msg: str) -> str:
    """Шифрование сообщения для биржи."""
    return b64encode(
        hmac.new(
            secret,
            msg.encode("utf-8"),
            hashlib.sha256,
        ).digest(),
    ).decode()


async def make_margin_limit_order(
    side: str,
    price: str,
    symbol: str,
    size: str,
    method: str = "POST",
    method_uri: str = "/api/v1/margin/order",
):
    """Make limit order by price."""

    now_time = str(int(time.time()) * 1000)

    data_json = dumps(
        {
            "clientOid": "".join([each for each in str(uuid1()).split("-")]),
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

    async with (
        aiohttp.ClientSession() as session,
        session.post(
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
        if res["code"] != "200000":
            logger.warning(f"{res}:{data_json}")


async def main():
    nc = Client()

    await nc.connect(
        servers="nats",
        max_reconnect_attempts=-1,
        reconnected_cb=reconnected_cb,
        disconnected_cb=disconnected_cb,
        error_cb=error_cb,
        closed_cb=closed_cb,
    )

    js = nc.jetstream()

    await js.add_stream(name="kcn", subjects=["candle", "balance"])

    async def candle(msg):
        symbol, price_str = loads(msg.data).popitem()
        price = Decimal(price_str)
        new_balance = price * ledger[symbol]["available"]

        if new_balance > base_keep:
            tokens_count = (new_balance - base_keep) / price
            side = "sell"

        elif base_keep > new_balance:
            tokens_count = (base_keep - new_balance) / price
            side = "buy"

        else:
            return

        size = str(
            tokens_count.quantize(
                ledger[symbol]["baseincrement"],
                ROUND_DOWN,
            )
        )  # around

        if float(size) != 0.0:
            await make_margin_limit_order(
                side=side,
                price=price_str,
                symbol=symbol,
                size=size,
            )

        await msg.ack()

    async def balance(msg):
        data = loads(msg.data)
        logger.info(
            f"Change balance:{data['symbol']}\t{ledger.get(data['symbol'],{'available':'0'})['available']} \t-> {data['available']}"
        )
        ledger.update(
            {
                data["symbol"]: {
                    "baseincrement": Decimal(data["baseincrement"]),
                    "available": Decimal(data["available"]),
                }
            }
        )
        await msg.ack()

    await js.subscribe("candle", "candle", cb=candle)
    await js.subscribe("balance", "balance", cb=balance)

    await asyncio.sleep(60 * 60 * 24 * 365)


if __name__ == "__main__":
    uvloop.run(main())
