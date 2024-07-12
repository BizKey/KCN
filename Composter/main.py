import asyncio
from nats.aio.client import Client
import orjson
import uvloop
from kucoin.client import WsToken
from kucoin.ws_client import KucoinWsClient
from loguru import logger
from decouple import config, Csv


# currency = config("CURRENCY", cast=Csv(str))
time_shift = config("TIME_SHIFT", cast=str, default="1hour")
base_stable = config("BASE_STABLE", cast=str, default="USDT")

start_pos = config("START_POS", cast=int)
count_pos = config("COUNT_POS", cast=int)
currency = config("ALLCURRENCY", cast=Csv(str))[start_pos : count_pos + start_pos]


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
    tokens = ",".join([f"{sym}-{base_stable}_{time_shift}" for sym in currency])
    history = {f"{k}-{base_stable}": "" for k in currency}
    logger.info(f"Tokens:{tokens}")

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

    async def event(msg: dict) -> None:
        symbol = msg["data"]["symbol"]
        price = msg["data"]["candles"][1]
        if history[symbol] != price:
            logger.info(f"Sent -> \t{symbol}:\t{price}")
            await js.publish("candle", orjson.dumps({symbol: price}))
            history[symbol] = price

    ws_public = await KucoinWsClient.create(None, WsToken(), event, private=False)

    await ws_public.subscribe(f"/market/candles:{tokens}")

    await asyncio.sleep(60 * 60 * 24 * 365)


if __name__ == "__main__":
    uvloop.run(main())
