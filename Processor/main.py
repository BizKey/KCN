"""KCN Processor."""

import asyncio
from decimal import ROUND_DOWN, Decimal

import orjson
from decouple import Csv, config
from loguru import logger
from nats.aio.client import Msg

from models import Access, Token
from natslocal import get_js_context
from tools import make_margin_limit_order


def get_side_and_size(ledger_data: dict, price: Decimal, token: Token) -> dict:
    """Get side of trade and size of tokens."""
    new_balance = price * ledger_data["available"]

    tokens_count = Decimal("0")

    if new_balance >= token.base_keep:
        tokens_count = (new_balance - token.base_keep) / price
        side = "sell"

    else:
        tokens_count = (token.base_keep - new_balance) / price
        side = "buy"

    size = tokens_count.quantize(
        ledger_data["baseincrement"],
        ROUND_DOWN,
    )  # around to baseincrement

    return {"side": side, "size": str(size)}


async def candle(msg: Msg) -> None:
    """Collect data of open price each candle by interval."""
    try:
        logger.debug(msg.data.decode())
        symbol, price_str = orjson.loads(msg.data).popitem()

        if symbol in ledger:
            # get side and size
            side_size_data = get_side_and_size(
                ledger[symbol],
                Decimal(price_str),
                token,
            )

            if float(side_size_data["size"]) != 0.0:  # check on buy '0' count of tokens
                # make limit order
                await make_margin_limit_order(
                    access=access,
                    side=side_size_data["side"],
                    price=price_str,
                    symbol=symbol,
                    size=side_size_data["size"],
                )

        await msg.ack()
    except Exception as e:
        logger.exception(e)


async def balance(msg: Msg) -> None:
    """Collect balance of each tokens."""
    try:
        data = orjson.loads(msg.data)

        symbol = data["symbol"]  # "...-USDT"
        available = data["available"]
        baseincrement = data["baseincrement"]

        available_in_ledger = ledger.get(symbol, {"available": "0"})["available"]

        ledger.update(
            {
                symbol: {
                    "baseincrement": Decimal(baseincrement),
                    "available": Decimal(available),
                },
            },
        )

        logger.success(
            f"Change balance:{symbol}\t{available_in_ledger} \t-> {available}",
        )
    except Exception as e:
        logger.exception(e)
    finally:
        await msg.ack()


async def main() -> None:
    """Main func in microservice."""
    logger.info("START PROCESSOR")
    global ledger, access, token
    ledger = {}

    js = await get_js_context()

    # Access object
    access = Access(
        key=config("KEY", cast=str),
        secret=config("SECRET", cast=str),
        passphrase=config("PASSPHRASE", cast=str),
        base_uri="https://api.kucoin.com",
    )
    # Token's object
    token = Token(
        time_shift=config("TIME_SHIFT", cast=str, default="1hour"),
        base_stable=config("BASE_STABLE", cast=str, default="USDT"),
        currency=config("ALLCURRENCY", cast=Csv(str)),
        ignore_currency=config("IGNORECURRENCY", cast=Csv(str)),
        base_keep=Decimal(config("BASE_KEEP", cast=int)),
    )

    await js.add_stream(name="kcn", subjects=["candle", "balance"])

    await js.subscribe("candle", "candle", cb=candle)
    await js.subscribe("balance", "balance", cb=balance)

    await asyncio.sleep(60 * 60 * 24 * 365)


if __name__ == "__main__":
    asyncio.run(main())
