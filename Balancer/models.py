"""Classes for work."""

import hashlib
import hmac
from base64 import b64encode
from typing import Self

import orjson
from loguru import logger

from nats.js import JetStreamContext


class Access:
    """Class for store access condention to exchange."""

    def __init__(self, key: str, secret: str, passphrase: str) -> None:
        """Init access condention keys."""
        self.key: str = key
        self.secret: str = secret
        self.passphrase: str = passphrase

    def encrypted(self: Self, msg: str) -> str:
        """Encrypted msg for exchange."""
        return b64encode(
            hmac.new(
                self.secret,
                msg.encode("utf-8"),
                hashlib.sha256,
            ).digest(),
        ).decode()


class Token:
    """Class for store token data for trade."""

    def __init__(self: Self, currency: list) -> None:
        """Init class for store trade tokens."""
        self.trade_currency: list[str] = currency  # Tokens for trade in bot


class OrderBook:
    """Class for store orders data from excange."""

    def __init__(self: Self, token: Token) -> None:
        """Init order book by symbol from config by available 0."""
        self.order_book: dict = {s: {"available": 0} for s in token.trade_currency}

    def fill_order_book(self: Self, account_list: list) -> None:
        """Fill real available from exchange."""
        self.order_book: dict = {
            account["currency"]: {"available": account["available"]}
            for account in account_list
            if account["currency"] in self.order_book
        }

    def fill_base_increment(self: Self, symbol_increments: list) -> None:
        """Fill real baseincrement from exchange.

        after:
        {"ICP":{"available":"123"}}

        before:
        {"ICP":{"available":"123","baseincrement":"0.0001"}}
        """
        self.order_book.update(
            {
                symbol_increment["baseCurrency"]: {
                    "baseincrement": symbol_increment["baseIncrement"],
                    "available": self.order_book[symbol_increment["baseCurrency"]],
                }
                for symbol_increment in symbol_increments
                if symbol_increment["baseCurrency"] in self.order_book
                and symbol_increment["quoteCurrency"] == "USDT"
            },
        )

    async def send_balance(self: Self, js: JetStreamContext) -> None:
        """Send first run balance state."""
        for symbol, value in self.order_book.items():
            data = {
                "symbol": f"{symbol}-USDT",
                "baseincrement": value["baseincrement"],
                "available": value["available"],
            }
            logger.info(
                f"{data['symbol']}\t{data['baseincrement']}\t{data['available']}",
            )
            await js.publish(
                "balance",
                orjson.dumps(data),
            )
