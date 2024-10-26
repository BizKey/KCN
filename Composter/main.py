"""Composter."""

import asyncio
import time
from collections.abc import Generator
from uuid import uuid4

import aiohttp
import orjson
import uvloop
from Composter.nats import get_js_context
from decouple import Csv, config
from loguru import logger
from websockets.asyncio.client import ClientConnection, connect

from nats.js import JetStreamContext

time_shift = config("TIME_SHIFT", cast=str, default="1hour")
base_stable = config("BASE_STABLE", cast=str, default="USDT")

currency = config("ALLCURRENCY", cast=Csv(str))
history = {f"{key}-{base_stable}": "" for key in currency}


def divide_chunks(length: list, number: int) -> Generator:
    """Функция разбиения словаря на подсловари по number значений."""
    for itr in range(0, len(length), number):
        yield length[itr : itr + number]


async def get_public_token() -> dict:
    """Get auth data for create websocket connection."""
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            "https://api.kucoin.com/api/v1/bullet-public",
        ) as response,
    ):
        res = await response.read()
        return orjson.loads(res)["data"]


async def event(data: dict, js: JetStreamContext) -> None:
    """Processing event klines."""
    symbol = data["symbol"]
    open_price = data["candles"][1]

    if history[symbol] != open_price:
        logger.info(f"Sent -> \t{symbol}:\t{open_price}")
        await js.publish("candle", orjson.dumps({symbol: open_price}))
        history[symbol] = open_price


async def get_url_websocket() -> str:
    """SetUp and get url for websocket."""
    public_token = await get_public_token()

    uri = public_token["instanceServers"][0]["endpoint"]
    token = public_token["token"]

    return f"{uri}?token={token}&connectId={str(uuid4()).replace('-', '')}"


async def set_up_subscribe(websocket: ClientConnection) -> None:
    """SetUp all subscribe."""
    await websocket.recv()

    tunnelid = "all_klines"

    await websocket.send(
        orjson.dumps(
            {
                "id": str(int(time.time() * 1000)),
                "type": "openTunnel",
                "newTunnelId": tunnelid,
            },
        ).decode(),
    )

    for tokens in divide_chunks(currency, 20):
        candles = ",".join([f"{sym}-{base_stable}_{time_shift}" for sym in tokens])

        await websocket.send(
            orjson.dumps(
                {
                    "id": str(int(time.time() * 1000)),
                    "type": "subscribe",
                    "topic": f"/market/candles:{candles}",
                    "privateChannel": False,
                    "tunnelId": tunnelid,
                },
            ).decode(),
        )


async def main() -> None:
    """Main func in microservice."""
    js = await get_js_context()
    await js.add_stream(name="kcn", subjects=["candle", "balance"])
    url = await get_url_websocket()

    async with connect(
        url,
        max_queue=1024,
    ) as websocket:
        await set_up_subscribe(websocket)

        while True:
            recv = await websocket.recv()
            data = orjson.loads(recv)["data"]
            await event(data, js)


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        runner.run(main())
