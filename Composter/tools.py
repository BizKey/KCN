"""Tools for Composter."""

from collections.abc import Generator

import aiohttp
import orjson


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
