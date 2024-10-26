"""Classes for work."""

import hashlib
import hmac
from base64 import b64encode
from decimal import Decimal
from typing import Self


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

    def __init__(
        self: Self,
        currency: list,
        ignore_currency: list,
        base_keep: Decimal,
    ) -> None:
        """Init class for store trade tokens."""
        self.trade_currency: list[str] = currency  # Tokens for trade in bot
        self.ignore_currency: list[str] = ignore_currency
        self.base_keep: Decimal = base_keep
