"""Composter."""

import asyncio
import signal
from decimal import Decimal
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


async def tunnel(
    ws: ClientConnection,
    tunnelid: str,
    type_: str,
) -> None:
    """Working with tunnel."""
    logger.info(f"Tunnel {type_}")
    await ws.send(
        orjson.dumps(
            {
                "id": str(int(time() * 1000)),
                "type": type_,
                "newTunnelId": tunnelid,
            },
        ).decode(),
    )


async def klines(
    ws: ClientConnection,
    tunnelid: str,
    token: Token,
    tokens: list,
    type_: str,
) -> None:
    """Init/final klines subscribe/unsubscribe."""
    logger.info(f"KLines {type_}")
    await ws.send(
        orjson.dumps(
            {
                "id": str(int(time() * 1000)),
                "type": type_,
                "topic": f"/market/candles:{token.get_candles_for_kline(tokens)}",
                "privateChannel": False,
                "tunnelId": tunnelid,
            },
        ).decode(),
    )


async def set_up_subscribe(
    ws: ClientConnection,
    token: Token,
) -> None:
    """SetUp all subscribe."""
    logger.info("Set up subscribe")
    tunnelid = "all_klines"

    await tunnel(ws, tunnelid, "openTunnel")

    await asyncio.gather(
        *[
            klines(ws, tunnelid, token, tokens, "subscribe")
            for tokens in divide_chunks(token.trade_currency, 20)
        ],
    )


async def set_down_subscribe(
    ws: ClientConnection,
    token: Token,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """SetUp all subscribe."""
    logger.info("Set down subscribe")
    tunnelid = "all_klines"

    await asyncio.gather(
        *[
            klines(ws, tunnelid, token, tokens, "unsubscribe")
            for tokens in divide_chunks(token.trade_currency, 20)
        ],
    )

    await tunnel(ws, tunnelid, "closeTunnel")

    await ws.close()
    loop.stop()


async def main() -> None:
    """Main func in microservice."""
    loop = asyncio.get_event_loop()

    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

    js = await get_js_context()
    url = await get_url_websocket()
    token = Token(
        time_shift=config("TIME_SHIFT", cast=str, default="1hour"),
        base_stable=config("BASE_STABLE", cast=str, default="USDT"),
        currency=config("ALLCURRENCY", cast=Csv(str)),
        ignore_currency=config("IGNORECURRENCY", cast=Csv(str)),
        base_keep=Decimal(config("BASE_KEEP", cast=int)),
    )

    token.init_history()

    async with connect(
        url,
        max_queue=1024,
    ) as ws:
        await ws.recv()
        await set_up_subscribe(ws, token)

        for s in signals:
            loop.add_signal_handler(
                s,
                lambda s=s: asyncio.create_task(
                    set_down_subscribe(
                        ws,
                        token,
                        loop,
                    ),
                ),
            )

        background_tasks = set()

        while True:
            recv = await ws.recv()

            task = asyncio.create_task(
                event(
                    orjson.loads(recv)["data"],
                    js,
                    token,
                ),
            )
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        runner.run(main())
