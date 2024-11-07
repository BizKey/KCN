"""Orderest."""

import asyncio

import uvloop
from decouple import config
from loguru import logger

from models import Access
from tools import cancel_order, get_order_list, get_server_timestamp


async def check_need_cancel(
    access: Access,
    servertimestamp: int,
    item: dict,
) -> None:
    """Check if datetime of create order more when 1 hour."""
    if servertimestamp > item["createdAt"] + 3500000:
        # order was claim more 1 hour ago
        logger.warning(f"Need cancel:{item}")
        await cancel_order(access, f"/api/v1/orders/{item['id']}")


async def brute_orders(
    servertimestamp: int,
    orders: dict,
    access: Access,
) -> None:
    """Brute order by create time more when 1 hour."""
    for item in orders["items"]:
        await check_need_cancel(access, servertimestamp, item)


async def main() -> None:
    """Main func in microservice."""
    access = Access(
        key=config("KEY", cast=str),
        secret=config("SECRET", cast=str),
        passphrase=config("PASSPHRASE", cast=str),
        base_uri="https://api.kucoin.com",
    )

    while True:
        servertimestamp = await get_server_timestamp()
        orders = await get_order_list(
            access,
            params={"type": "limit", "tradeType": "MARGIN_TRADE", "status": "active"},
        )
        await brute_orders(servertimestamp, orders, access)
        await asyncio.sleep(60)


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        runner.run(main())
