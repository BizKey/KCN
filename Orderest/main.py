"""Orderest."""

import asyncio

import uvloop
from decouple import config
from loguru import logger

from models import Access
from tools import cancel_order, get_order_list, get_seconds_to_next_minutes


async def find_order_for_cancel(access: Access) -> None:
    """Find order created more then 1 hour ago."""
    orders = await get_order_list(
        access,
        params={
            "type": "limit",
            "tradeType": "MARGIN_TRADE",
            "status": "active",
        },
    )
    for item in orders["items"]:
        logger.warning(f"Need cancel:{item}")
        await cancel_order(access, f"/api/v1/orders/{item['id']}")


async def main() -> None:
    """Main func in microservice."""
    access = Access(
        key=config("KEY", cast=str),
        secret=config("SECRET", cast=str),
        passphrase=config("PASSPHRASE", cast=str),
        base_uri="https://api.kucoin.com",
    )

    while True:
        wait_seconds = get_seconds_to_next_minutes(59)

        logger.info(f"Wait {wait_seconds} to run find_order_for_cancel")
        await asyncio.sleep(wait_seconds)

        await find_order_for_cancel(access)


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        runner.run(main())
