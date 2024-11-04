"""Composter."""

import asyncio
from time import time
from uuid import uuid4

import orjson
import uvloop
from decouple import Csv, config
from loguru import logger
from nats.js import JetStreamContext
from websockets.asyncio.client import ClientConnection, connect

from models import Token
from natslocal import get_js_context
from tools import divide_chunks, get_public_token


async def event(data: dict, js: JetStreamContext, token: Token) -> None:
    """Processing event klines."""
    symbol = data["symbol"]
    open_price = data["candles"][1]

    if token.history[symbol] != open_price:
        logger.info(f"Sent -> \t{symbol}:\t{open_price}")
        await js.publish("candle", orjson.dumps({symbol: open_price}))
        token.history[symbol] = open_price


async def get_url_websocket() -> str:
    """SetUp and get url for websocket."""
    public_token = await get_public_token()

    endpoint = public_token["instanceServers"][0]["endpoint"]
    token = public_token["token"]

    return f"{endpoint}?token={token}&connectId={str(uuid4()).replace('-', '')}"


async def set_up_subscribe(websocket: ClientConnection, token: Token) -> None:
    """SetUp all subscribe."""
    await websocket.recv()

    tunnelid = "all_klines"

    await websocket.send(
        orjson.dumps(
            {
                "id": str(int(time() * 1000)),
                "type": "openTunnel",
                "newTunnelId": tunnelid,
            },
        ).decode(),
    )

    for tokens in divide_chunks(token.trade_currency, 20):
        await websocket.send(
            orjson.dumps(
                {
                    "id": str(int(time() * 1000)),
                    "type": "subscribe",
                    "topic": f"/market/candles:{token.get_candles_for_kline(tokens)}",
                    "privateChannel": False,
                    "tunnelId": tunnelid,
                },
            ).decode(),
        )


async def main() -> None:
    """Main func in microservice."""
    js = await get_js_context()
    url = await get_url_websocket()
    token = Token(
        time_shift=config("TIME_SHIFT", cast=str, default="1hour"),
        base_stable=config("BASE_STABLE", cast=str, default="USDT"),
        currency=config("ALLCURRENCY", cast=Csv(str)),
    )

    token.init_history()

    async with connect(
        url,
        max_queue=1024,
    ) as websocket:
        await set_up_subscribe(websocket, token)

        while True:
            recv = await websocket.recv()
            await event(orjson.loads(recv)["data"], js, token)


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        runner.run(main())
