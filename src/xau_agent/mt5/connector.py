"""MT5 terminal init/login/shutdown. Pure connection lifecycle."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

import MetaTrader5 as mt5  # noqa: N813

from xau_agent.config import get_settings

log = logging.getLogger(__name__)


class MT5Error(RuntimeError):
    """Raised when MT5 init/login fails."""


def initialize() -> None:
    """Initialize MT5 terminal + login. Raises MT5Error on failure."""
    s = get_settings()
    kwargs: dict = {}
    if s.mt5_terminal_path:
        kwargs["path"] = s.mt5_terminal_path
    if s.mt5_login:
        kwargs.update(login=s.mt5_login, password=s.mt5_password, server=s.mt5_server)

    if not mt5.initialize(**kwargs):
        err = mt5.last_error()
        raise MT5Error(f"MT5 initialize failed: {err}")

    info = mt5.account_info()
    if info is None:
        mt5.shutdown()
        raise MT5Error(f"MT5 account_info None — login failed: {mt5.last_error()}")
    log.info(
        "MT5 connected: login=%s server=%s balance=%.2f %s",
        info.login, info.server, info.balance, info.currency,
    )


def shutdown() -> None:
    mt5.shutdown()


@contextmanager
def session() -> Iterator[None]:
    """Context manager: init on enter, shutdown on exit."""
    initialize()
    try:
        yield
    finally:
        shutdown()
