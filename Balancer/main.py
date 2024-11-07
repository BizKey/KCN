"""Balancer."""

import asyncio
from decimal import Decimal
from time import time
from uuid import uuid4

import orjson
import uvloop
from decouple import Csv, config
from nats.js import JetStreamContext
from websockets.asyncio.client import ClientConnection, connect

from models import Access, OrderBook, Token
from natslocal import get_js_context
from tools import get_account_list, get_private_token, get_symbol_list


async def init_order_book(
    access: Access,
    orderbook: OrderBook,
) -> None:
    """First init order_book."""
    account_list = await get_account_list(access, {"type": "margin"})
    symbol_list = await get_symbol_list()

    orderbook.fill_order_book(account_list)
    orderbook.fill_base_increment(symbol_list)


async def event(msg: dict, orderbook: OrderBook, js: JetStreamContext) -> None:
    """Work with change amount of balance on exchange."""
    data = msg["data"]
    relationevent = data["relationEvent"]
    available = data["available"]
    currency = data["currency"]

    if (
        currency != "USDT"  # ignore income USDT in balance
        and relationevent
        in [
            "margin.hold",
            "margin.setted",
        ]
        and available
        != orderbook.order_book[currency][
            "available"
        ]  # ignore income qeuals available tokens
    ):
        orderbook.order_book[currency]["available"] = available
        await js.publish(
            "balance",
            orjson.dumps(
                {
                    "symbol": f"{currency}-USDT",
                    "baseincrement": orderbook.order_book[currency]["baseincrement"],
                    "available": orderbook.order_book[currency]["available"],
                },
            ),
        )


async def set_up_subscribe(websocket: ClientConnection) -> None:
    """SetUp all subscribe to change balance."""
    await websocket.recv()  # {  "id": "hQvf8jkno",  "type": "welcome"}

    await websocket.send(
        orjson.dumps(
            {
                "id": str(int(time() * 1000)),
                "type": "subscribe",
                "topic": "/account/balance",
                "privateChannel": True,
            },
        ).decode(),
    )


async def get_url_websocket(access: Access) -> str:
    """SetUp and get url for websocket."""
    private_token = await get_private_token(access)

    endpoint = private_token["instanceServers"][0]["endpoint"]
    token = private_token["token"]

    return f"{endpoint}?token={token}&connectId={str(uuid4()).replace('-', '')}"


async def main() -> None:
    """Main func in microservice."""
    access = Access(
        key=config("KEY", cast=str),
        secret=config("SECRET", cast=str),
        passphrase=config("PASSPHRASE", cast=str),
        base_uri="https://api.kucoin.com",
    )

    token = Token(
        currency=config("ALLCURRENCY", cast=Csv(str)),
        ignore_currency=config("IGNORECURRENCY", cast=Csv(str)),
        base_keep=Decimal(config("BASE_KEEP", cast=int)),
    )

    orderbook = OrderBook(token=token)

    await init_order_book(access, orderbook)

    js = await get_js_context()

    # Send first initial balance from excange
    await orderbook.send_balance(js)

    url = await get_url_websocket(access)

    async with connect(url, max_queue=1024) as websocket:
        await set_up_subscribe(websocket, token)

        while True:
            recv = await websocket.recv()
            await event(orjson.loads(recv)["data"], js, token)


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        runner.run(main())
