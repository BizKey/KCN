import asyncio
import nats
import orjson
import uvloop
from kucoin.client import WsToken
from kucoin.ws_client import KucoinWsClient
from loguru import logger
from decouple import config, Csv

currency = config("CURRENCY", cast=Csv(str))
time_shift = config("TIME_SHIFT", cast=str, default="1hour")
base_stable = config("BASE_STABLE", cast=str, default="USDT")


history = {f"{k}-{base_stable}": "" for k in currency}


async def main():
    tokens = ",".join([f"{sym}-{base_stable}_{time_shift}" for sym in currency])
    logger.info(f"Tokens:{tokens}")
    nc = await nats.connect("nats")

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
