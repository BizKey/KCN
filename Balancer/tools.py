"""Tools for Balancer."""

from time import time
from urllib.parse import urljoin

import aiohttp

from models import Access


async def get_account_list(access: Access) -> list:
    """Get margin account list token."""
    uri = "/api/v1/accounts"
    data_json = ""
    params = {"type": "margin"}
    strl = [f"{key}={params[key]}" for key in sorted(params)]
    data_json += "&".join(strl)
    uri += "?" + data_json
    uri_path = uri

    now_time = str(int(time()) * 1000)
    str_to_sign = str(now_time) + "GET" + uri_path

    async with (
        aiohttp.ClientSession() as session,
        session.get(
            urljoin(access.base_uri, uri),
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


async def get_symbol_list(access: Access) -> list:
    """Get all tokens in excange."""
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            urljoin(access.base_uri, "/api/v2/symbols"),
            headers={"User-Agent": "kucoin-python-sdk/2"},
        ) as response,
    ):
        return await response.json()


async def get_private_token(access: Access) -> list:
    """Get margin account list token."""
    uri = "/api/v1/bullet-private"
    data_json = ""
    uri_path = uri

    now_time = str(int(time()) * 1000)
    str_to_sign = str(now_time) + "POST" + uri_path

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            urljoin(access.base_uri, uri),
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
