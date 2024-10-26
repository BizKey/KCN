"""Nats tools for get js context."""

from loguru import logger

from nats.aio.client import Client
from nats.js import JetStreamContext


async def disconnected_cb(*args: list) -> None:
    """CallBack на отключение от nats."""
    logger.error(f"Got disconnected... {args}")


async def reconnected_cb(*args: list) -> None:
    """CallBack на переподключение к nats."""
    logger.error(f"Got reconnected... {args}")


async def error_cb(excep: Exception) -> None:
    """CallBack на ошибку подключения к nats."""
    logger.error(f"Error ... {excep}")


async def closed_cb(*args: list) -> None:
    """CallBack на закрытие подключения к nats."""
    logger.error(f"Closed ... {args}")


async def get_js_context() -> JetStreamContext:
    """Get JetStream Context."""
    nc = Client()

    await nc.connect(
        servers="nats",
        max_reconnect_attempts=-1,
        reconnected_cb=reconnected_cb,
        disconnected_cb=disconnected_cb,
        error_cb=error_cb,
        closed_cb=closed_cb,
    )

    return nc.jetstream()
