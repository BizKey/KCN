"""Classes for work."""

import hashlib
import hmac
from base64 import b64encode
from decimal import Decimal
from typing import Self


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
            / (self.get_len_trade_currency() * self.base_keep)
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

    def save_accept_tokens(self: Self, all_token_in_excange: dict) -> None:
        """Save all accepted token."""
        self.accept_tokens = [
            Token.remove_postfix(token_in_excange["symbol"])
            for token_in_excange in all_token_in_excange
            if token_in_excange["isMarginEnabled"]
            and token_in_excange["quoteCurrency"] == "USDT"
            and Token.remove_postfix(token_in_excange["symbol"])
            not in self.ignore_currency
        ]

    def save_new_tokens(self: Self, all_token_in_excange: dict) -> None:
        """Get all new token for trade."""
        self.new_tokens = [
            Token.remove_postfix(token_in_excange["symbol"])
            for token_in_excange in all_token_in_excange
            if token_in_excange["quoteCurrency"] == "USDT"
            and token_in_excange["isMarginEnabled"]
            and Token.remove_postfix(token_in_excange["symbol"])
            not in self.trade_currency
            and Token.remove_postfix(token_in_excange["symbol"])
            not in self.ignore_currency
        ]

    def save_del_tokens(self: Self) -> None:
        """."""
        self.del_tokens = [
            used for used in self.trade_currency if used not in self.accept_tokens
        ]


class Telegram:
    """Class for store access to telegram."""

    def __init__(self, telegram_bot_key: str, telegram_bot_chat_id: str) -> None:
        """Init API KEY for telegram."""
        self.telegram_bot_key = telegram_bot_key
        self.telegram_bot_chat_id: list = telegram_bot_chat_id

    def get_telegram_url(self: Self) -> str:
        """Return telegram url."""
        return f"https://api.telegram.org/bot{self.telegram_bot_key}/sendMessage"

    def get_bot_chat_id(self: Self) -> list:
        """Return list chat id users."""
        return self.telegram_bot_chat_id
