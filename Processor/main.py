"""Processor."""

import asyncio
import hashlib
import hmac
import time
from base64 import b64encode
from decimal import ROUND_DOWN, Decimal
from urllib.parse import urljoin
from uuid import uuid1

import aiohttp
import orjson
import uvloop
from decouple import config
from loguru import logger
from Processor.nats import get_js_context

from nats.aio.client import Msg

key = config("KEY", cast=str)
secret = config("SECRET", cast=str).encode("utf-8")
passphrase = config("PASSPHRASE", cast=str)
base_keep = Decimal(config("BASE_KEEP", cast=int))


base_uri = "https://api.kucoin.com"


def encrypted_msg(msg: str) -> str:
    """Encrypt msg for excenge."""
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
) -> None:
    """Make limit order by price."""
    method = "POST"
    method_uri = "/api/v1/margin/order"

    now_time = str(int(time.time()) * 1000)

    data_json = orjson.dumps(
        {
            "clientOid": str(uuid1()).replace("-", ""),
            "side": side,
            "symbol": symbol,
            "price": price,
            "size": size,
            "type": "limit",
            "timeInForce": "GTC",
            "autoBorrow": True,
            "autoRepay": True,
        },
    ).decode()

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            urljoin(base_uri, method_uri),
            headers={
                "KC-API-SIGN": encrypted_msg(
                    now_time + method + method_uri + data_json,
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
        match res["code"]:
            case "200000":
                logger.success(f"{res}:{data_json}")
            case _:
                logger.warning(f"{res}:{data_json}")


def get_side_and_size(ledger_data: dict, price: Decimal) -> dict:
    """Get side of trade and size of tokens."""
    new_balance = price * ledger_data["available"]

    tokens_count = Decimal("0")

    if new_balance >= base_keep:
        tokens_count = (new_balance - base_keep) / price
        side = "sell"

    else:
        tokens_count = (base_keep - new_balance) / price
        side = "buy"

    size = tokens_count.quantize(
        ledger_data["baseincrement"],
        ROUND_DOWN,
    )  # around to baseincrement

    return {"side": side, "size": str(size)}


ledger = {}


async def candle(msg: Msg) -> None:
    """Collect data of open price each candle by interval."""
    symbol, price_str = orjson.loads(msg.data).popitem()

    # get side and size
    side_size_data = get_side_and_size(ledger[symbol], Decimal(price_str))

    if float(side_size_data["size"]) != 0.0:
        # make limit order
        await make_margin_limit_order(
            side=side_size_data["side"],
            price=price_str,
            symbol=symbol,
            size=side_size_data["size"],
        )

    # ack msg
    await msg.ack()


async def balance(msg: Msg) -> None:
    """Collect balance of each tokens."""
    data = orjson.loads(msg.data)

    symbol = data["symbol"]
    available = data["available"]
    baseincrement = data["baseincrement"]

    if symbol in ledger:
        available_in_ledger = ledger.get(symbol)["available"]
    else:
        available_in_ledger = ledger.get(symbol, {"available": "0"})["available"]

    logger.info(
        f"Change balance:{symbol}\t{available_in_ledger} \t-> {available}",
    )

    ledger.update(
        {
            symbol: {
                "baseincrement": Decimal(baseincrement),
                "available": Decimal(available),
            },
        },
    )
    await msg.ack()


async def main() -> None:
    """Main func in microservice."""
    js = await get_js_context()

    await js.add_stream(name="kcn", subjects=["candle", "balance"])

    await js.subscribe("candle", "candle", cb=candle)
    await js.subscribe("balance", "balance", cb=balance)

    await asyncio.sleep(60 * 60 * 24 * 365)


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        runner.run(main())
