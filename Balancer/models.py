"""Classes for work."""

import hashlib
import hmac
from base64 import b64encode
from decimal import Decimal
from typing import Self

import orjson
from loguru import logger
from nats.js import JetStreamContext


class Access:
    """Class for store access condention to exchange."""

    def __init__(self, key: str, secret: str, passphrase: str, base_uri: str) -> None:
        """Init access condention keys."""
        self.key: str = key
        self.secret: str = secret
        self.passphrase: str = passphrase
        self.base_uri: str = base_uri

    def encrypted(self: Self, msg: str) -> str:
        """Encrypted msg for exchange."""
        return b64encode(
            hmac.new(
                self.secret.encode("utf-8"),
                msg.encode("utf-8"),
                hashlib.sha256,
            ).digest(),
        ).decode()


class Token:
    """Class for store token data for trade."""

    def __init__(
        self: Self,
        currency: list,
        ignore_currency: list,
        base_keep: Decimal,
        time_shift: str = "1hour",
        base_stable: str = "USDT",
    ) -> None:
        """Init class for store trade tokens."""
        self.trade_currency: list[str] = currency  # Tokens for trade in bot
        self.ignore_currency: list[str] = ignore_currency
        self.base_keep: Decimal = base_keep
        self.base_stable: str = base_stable
        self.time_shift: str = time_shift
        self.borrow_size: Decimal = Decimal("0")
        self.avail_size: Decimal = Decimal("0")

        self.accept_tokens: list[str] = []  # tradable tokens
        self.new_tokens: list[str] = (
            []
        )  # tokens that can be traded but are not in the bot
        self.del_tokens: list[str] = (
            []
        )  # tokens that have been removed from the exchange
        self.history: dict = {}

    def init_history(self: Self) -> None:
        """Init history."""
        self.history = {f"{key}-{self.base_stable}": "" for key in self.trade_currency}

    def get_candles_for_kline(self: Self, tokens: list) -> str:
        """Get str candles for kline websocket."""
        return ",".join(
            [f"{sym}-{self.base_stable}_{self.time_shift}" for sym in tokens],
        )

    def get_clear_borrow(self: Self) -> Decimal:
        """Get clear borrow size."""
        return self.borrow_size - self.avail_size

    def get_percent_borrow(self: Self) -> int:
        """Get percent of borrowing."""
        return (
            self.get_clear_borrow()
            * 100
            / (self.trade_currency * float(self.base_keep))
        )

    def get_len_trade_currency(self: Self) -> int:
        """Get len of trade_currency."""
        return len(self.trade_currency)

    def get_len_accept_tokens(self: Self) -> int:
        """Get len of accept_tokens."""
        return len(self.accept_tokens)

    def get_len_del_tokens(self: Self) -> int:
        """Get len del_tokens."""
        return len(self.del_tokens)

    def get_len_ignore_currency(self: Self) -> int:
        """Get len of ignore_currency."""
        return len(self.ignore_currency)

    def get_len_new_tokens(self: Self) -> int:
        """Get len of new_tokens."""
        return len(self.new_tokens)

    @staticmethod
    def remove_postfix(symbol: str, postfix: str = "-USDT") -> str:
        """Remove postfix."""
        return symbol.replace(postfix, "")

    def save_accept_tokens(self: Self, all_token_in_excange: list) -> None:
        """Save all accepted token."""
        self.accept_tokens = [
            Token.remove_postfix(token_in_excange["symbol"])
            for token_in_excange in all_token_in_excange
            if token_in_excange["isMarginEnabled"]
            and token_in_excange["quoteCurrency"] == "USDT"
            and Token.remove_postfix(token_in_excange["symbol"])
            not in self.ignore_currency
        ]

    def save_new_tokens(self: Self, all_token_in_excange: list) -> None:
        """."""
        self.new_tokens = [
            Token.remove_postfix(token_in_excange["symbol"])
            for token_in_excange in all_token_in_excange
            if Token.remove_postfix(token_in_excange["symbol"])
            not in self.accept_tokens
        ]

    def save_del_tokens(self: Self) -> None:
        """."""
        self.del_tokens = [
            used for used in self.trade_currency if used not in self.accept_tokens
        ]


class OrderBook:
    """Class for store orders data from excange."""

    def __init__(self: Self, token: Token) -> None:
        """Init order book by symbol from config by available 0."""
        self.order_book: dict = {s: {"available": 0} for s in token.trade_currency}

    def fill_order_book(self: Self, account_list: dict) -> None:
        """Fill real available from exchange."""
        self.order_book: dict = {
            account["currency"]: {"available": account["available"]}
            for account in account_list
            if account["currency"] in self.order_book
        }

    def fill_base_increment(self: Self, symbol_increments: dict) -> None:
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
