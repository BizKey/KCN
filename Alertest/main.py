"""KCN Alertest."""

import asyncio
from decimal import Decimal

from decouple import Csv, config
from loguru import logger

from models import Access, Telegram, Token
from tools import (
    get_margin_account,
    get_seconds_to_next_minutes,
    get_symbol_list,
    send_telegram_msg,
)

DAY_IN_MILLISECONDS = 86400000
WEEK_IN_MILLISECONDS = DAY_IN_MILLISECONDS * 7


def get_start_at_for_day(now_mill: int) -> int:
    """Return milliseconds for shift a day."""
    return now_mill - DAY_IN_MILLISECONDS


def get_start_at_for_week(now_mill: int) -> int:
    """Return milliseconds for shift a week."""
    return now_mill - WEEK_IN_MILLISECONDS


async def get_available_funds(
    access: Access,
    token: Token,
) -> None:
    """Get available funds in excechge."""
    logger.info("Run get_available_funds")

    margin_account = await get_margin_account(access, {"quoteCurrency": "USDT"})

    for i in [i for i in margin_account["accounts"] if i["currency"] == "USDT"]:
        token.borrow_size = Decimal(i["liability"])
        token.avail_size = Decimal(i["available"])


async def get_tokens(access: Access, token: Token) -> None:
    """Get available tokens."""
    logger.info("Run get_tokens")
    all_token_in_excange = await get_symbol_list(access)

    token.save_accept_tokens(all_token_in_excange)
    token.save_new_tokens(all_token_in_excange)
    token.save_del_tokens()


async def get_actual_token_stats(
    access: Access,
    token: Token,
    telegram: Telegram,
) -> None:
    """Get actual all tokens stats."""
    logger.info("Run get_actual_token_stats")
    await get_available_funds(access, token)
    await get_tokens(access, token)

    msg = telegram.get_telegram_msg(token)
    logger.warning(msg)
    await send_telegram_msg(telegram, msg)


async def main() -> None:
    """Main func in microservice.

    wait second to next time with 10:00 minutes equals
    in infinity loop to run get_actual_token_stats
    """
    logger.info("Run Alertest microservice")

    # Access object
    access = Access(
        key=config("KEY", cast=str),
        secret=config("SECRET", cast=str),
        passphrase=config("PASSPHRASE", cast=str),
        base_uri="https://api.kucoin.com",
    )

    # Token's object
    token = Token(
        time_shift=config("TIME_SHIFT", cast=str, default="1hour"),
        base_stable=config("BASE_STABLE", cast=str, default="USDT"),
        currency=config("ALLCURRENCY", cast=Csv(str)),
        ignore_currency=config("IGNORECURRENCY", cast=Csv(str)),
        base_keep=Decimal(config("BASE_KEEP", cast=int)),
    )

    # Telegram object
    telegram = Telegram(
        telegram_bot_key=config("TELEGRAM_BOT_API_KEY", cast=str),
        telegram_bot_chat_id=config("TELEGRAM_BOT_CHAT_ID", cast=Csv(str)),
    )

    await get_actual_token_stats(
        access,
        token,
        telegram,
    )

    while True:
        wait_seconds = get_seconds_to_next_minutes(10)

        logger.info(f"Wait {wait_seconds} to run get_actual_token_stats")
        await asyncio.sleep(wait_seconds)

        await get_actual_token_stats(
            access,
            token,
            telegram,
        )


if __name__ == "__main__":
    asyncio.run(main())
