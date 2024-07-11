import asyncio
from nats.aio.client import Client
import orjson
import uvloop
from kucoin.ws_client import KucoinWsClient
from loguru import logger
from kucoin.client import WsToken, User, Market
from decouple import config

passphrase = config("PASSPHRASE", cast=str)
key = config("KEY", cast=str)
secret = config("SECRET", cast=str)

user = User(
    key=key,
    secret=secret,
    passphrase=passphrase,
    is_sandbox=False,
)


market = Market(
    key=key,
    secret=secret,
    passphrase=passphrase,
    is_sandbox=False,
)


client = WsToken(
    key=key,
    secret=secret,
    passphrase=passphrase,
    url="https://openapi-v2.kucoin.com",
)

order_book = {
    f"{sh['currency']}": {"available": sh["available"]}
    for sh in user.get_account_list(account_type="margin")
}


for symbol in market.get_symbol_list_v2():
    if symbol in order_book:
        order_book[symbol].update({"baseincrement": symbol["baseIncrement"]})


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

    for symbol in order_book.keys():
        await js.publish(
            "balance",
            orjson.dumps(
                {
                    "symbol": f"{symbol}-USDT",
                    "baseincrement": order_book[symbol]["baseincrement"],
                    "available": order_book[symbol]["available"],
                }
            ),
        )

    async def event(msg: dict) -> None:
        logger.info(msg)
        relationEvent = msg["relationEvent"]
        available = msg["available"]
        currency = msg["currency"]

        if (
            relationEvent
            in [
                "margin.hold",
                "margin.setted",
            ]
            and available != order_book[currency]["available"]
        ):
            order_book[currency]["available"] = available
            await js.publish(
                "balance",
                orjson.dumps(
                    {
                        "symbol": f"{currency}-USDT",
                        "baseincrement": order_book[currency]["baseincrement"],
                        "available": order_book[currency]["available"],
                    }
                ),
            )

    ws_private = await KucoinWsClient.create(None, client, event, private=True)
    await ws_private.subscribe("/account/balance")

    await asyncio.sleep(60 * 60 * 24 * 365)


if __name__ == "__main__":
    uvloop.run(main())
