"""Balancer."""

import asyncio
import time
from urllib.parse import urljoin

import aiohttp
import orjson
import uvloop
from Balancer.nats import get_js_context
from decouple import Csv, config
from websockets.asyncio.client import ClientConnection, connect

from models import Access, OrderBook, Token
from nats.js import JetStreamContext

base_uri = "https://api.kucoin.com"


async def get_symbol_list() -> list:
    """Get all tokens in excange."""
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            urljoin(base_uri, "/api/v2/symbols"),
            headers={"User-Agent": "kucoin-python-sdk/2"},
        ) as response,
    ):
        return await response.json()


async def get_account_list(access: Access) -> list:
    """Get margin account list token."""
    uri = "/api/v1/accounts"
    data_json = ""
    params = {"type": "margin"}
    strl = [f"{key}={params[key]}" for key in sorted(params)]
    data_json += "&".join(strl)
    uri += "?" + data_json
    uri_path = uri

    now_time = str(int(time.time()) * 1000)
    str_to_sign = str(now_time) + "GET" + uri_path

    async with (
        aiohttp.ClientSession() as session,
        session.get(
            urljoin(base_uri, uri),
            headers={
                "KC-API-SIGN": access.encrypted(str_to_sign),
                "KC-API-TIMESTAMP": now_time,
                "KC-API-PASSPHRASE": access.encrypted(access.passphrase),
                "KC-API-KEY": access.key,
                "Content-Type": "application/json",
                "KC-API-KEY-VERSION": "2",
                "User-Agent": "kucoin-python-sdk/2",
            },
            data=data_json,
        ) as response,
    ):
        return await response.json()


async def init_order_book(
    access: Access,
    token: Token,
    orderbook: OrderBook,
) -> OrderBook:
    """First init order_book."""
    account_list = await get_account_list(access)

    orderbook.fill_order_book(account_list, token)
    orderbook.fill_base_increment(get_symbol_list())


async def event(msg: dict, orderbook: OrderBook, js: JetStreamContext) -> None:
    """Work with change amount of balance on exchange."""
    relationevent = msg["data"]["relationEvent"]
    available = msg["data"]["available"]
    currency = msg["data"]["currency"]

    if (
        currency != "USDT"
        and relationevent
        in [
            "margin.hold",
            "margin.setted",
        ]
        and available != orderbook.order_book[currency]["available"]
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


async def main() -> None:
    """Main func in microservice."""
    access = Access(
        key=config("KEY", cast=str),
        secret=config("SECRET", cast=str),
        passphrase=config("PASSPHRASE", cast=str),
    )
    token = Token(currency=config("ALLCURRENCY", cast=Csv(str)))
    orderbook = OrderBook(token=token)

    await init_order_book(access, token, orderbook)

    js = await get_js_context()

    # Send first initial balance from excange
    await orderbook.send_balance(orderbook, js)


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        runner.run(main())
