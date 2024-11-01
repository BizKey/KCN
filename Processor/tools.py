"""Tools for Processor."""

from time import time
from urllib.parse import urljoin
from uuid import uuid1

import aiohttp
import orjson
from loguru import logger

from models import Access


async def make_margin_limit_order(
    access: Access,
    side: str,
    price: str,
    symbol: str,
    size: str,
) -> None:
    """Make limit order by price."""
    method = "POST"
    method_uri = "/api/v1/margin/order"

    now_time = str(int(time()) * 1000)

    data_json = orjson.dumps(
        {
            "clientOid": str(uuid1()).replace("-", ""),
            "side": side,
            "symbol": symbol,
            "price": price,
            "size": size,
            "type": "limit",
            "timeInForce": "GTC",
            "autoBorrow": True,
            "autoRepay": True,
        },
    ).decode()

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            urljoin(access.base_uri, method_uri),
            headers={
                "KC-API-SIGN": access.encrypted(
                    now_time + method + method_uri + data_json,
                ),
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
        res = await response.json()
        match res["code"]:
            case "200000":
                logger.success(f"{res}:{data_json}")
            case _:
                logger.warning(f"{res}:{data_json}")
