"""Alertest."""

import asyncio
from decimal import Decimal

import uvloop
from decouple import Csv, config
from loguru import logger

from models import Access, Telegram, Token
from tools import (
    get_margin_account,
    get_seconds_to_next_minutes,
    get_symbol_list,
    send_telegram_msg,
)


def get_telegram_msg(token: Token) -> str:
    """Prepare telegram msg."""
    return f"""<b>KuCoin</b>

<i>KEEP</i>:{token.base_keep}
<i>USDT</i>:{token.avail_size:.2f}
<i>BORROWING USDT</i>:{token.get_clear_borrow():.2f} ({token.get_percent_borrow():.2f}%)
<i>ALL TOKENS</i>:{token.get_len_accept_tokens()}
<i>USED TOKENS</i>({token.get_trade_currency()})
<i>DELETED</i>({token.get_len_del_tokens()}):{",".join(token.del_tokens)}
<i>NEW</i>({token.get_len_new_tokens()}):{",".join(token.new_tokens)}
<i>IGNORE</i>({token.get_len_ignore_currency}):{",".join(token.ignore_currency)}"""


async def get_available_funds(
    access: Access,
    token: Token,
) -> None:
    """Get available funds in excechge."""
    logger.info("Run get_available_funds")

    margin_account = await get_margin_account(access)["accounts"]

    for i in [i for i in margin_account if i["currency"] == "USDT"]:
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

    msg = get_telegram_msg(token)
    logger.warning(msg)
    await send_telegram_msg(telegram, msg)


async def main() -> None:
    """Main func in microservice.

    wait second to next time with 10:00 minutes equals
    in infinity loop to run get_actual_token_stats
    """
    logger.info("Run Alertest microservice")
    access = Access(
        key=config("KEY", cast=str),
        secret=config("SECRET", cast=str),
        passphrase=config("PASSPHRASE", cast=str),
        base_uri="https://api.kucoin.com",
    )
    token = Token(
        currency=config("ALLCURRENCY", cast=Csv(str)),
        ignore_currency=config("IGNORECURRENCY", cast=Csv(str)),
        base_keep=Decimal(config("BASE_KEEP", cast=int)),
    )

    telegram = Telegram(
        telegram_bot_key=config("TELEGRAM_BOT_API_KEY", cast=str),
        telegram_bot_chat_id=config("TELEGRAM_BOT_CHAT_ID", cast=Csv(str)),
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
    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        runner.run(main())
