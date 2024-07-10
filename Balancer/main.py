import asyncio
import nats
import orjson
import uvloop
from kucoin.client import WsToken
from kucoin.ws_client import KucoinWsClient
from loguru import logger
from kucoin.client import Market, Trade, User, WsToken
from decouple import config, Csv


client = WsToken(
    key=key,
    secret=secret,
    passphrase=passphrase,
    url="https://openapi-v2.kucoin.com",
)


async def main():
    nc = await nats.connect("nats")

    js = nc.jetstream()

    async def event(msg: dict) -> None:
        logger.info(msg)

    ws_private = await KucoinWsClient.create(None, client, event, private=True)
    await ws_private.subscribe("/account/balance")

    await asyncio.sleep(60 * 60 * 24 * 365)


if __name__ == "__main__":
    uvloop.run(main())
