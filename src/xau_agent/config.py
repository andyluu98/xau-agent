"""Runtime config loaded from .env. Single source of truth for all params."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # MT5
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = "Exness-MT5Trial"
    mt5_terminal_path: str = ""  # empty = auto-detect

    # LLM
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # News
    tavily_api_key: str = ""

    # TradingView (free, no auth) — for 26-indicator consensus vote
    tv_symbol: str = "XAUUSD"        # ký hiệu trên TradingView (khác MT5)
    tv_exchange: str = "OANDA"       # sàn TV: OANDA / FX_IDC / FOREXCOM
    tv_screener: str = "cfd"         # screener: cfd / forex / crypto

    # Trading
    symbol: str = "XAUUSD"
    entry_tf: Literal["M1", "M5", "M15", "M30", "H1"] = "M15"
    trend_tfs: str = "H1,H4"  # comma-separated; parsed to list below
    default_lot: float = 0.01
    max_open_trades: int = 1
    max_trades_per_day: int = 4
    atr_sl_mult: float = 1.5
    atr_tp_mult: float = 2.5
    atr_period: int = 14
    bars_lookback: int = 200  # how many bars to fetch per TF

    # Risk management (G2 + G3)
    risk_pct_per_trade: float = 0.0   # 0 = dùng default_lot. >0 = tính lot từ % balance
    kill_dd_pct: float = 3.0          # daily DD ≥ x% → tự tắt bot đến hôm sau

    # Runtime
    dry_run: bool = True
    log_level: str = "INFO"

    @field_validator("trend_tfs")
    @classmethod
    def _normalize_tfs(cls, v: str) -> str:
        return ",".join(tf.strip().upper() for tf in v.split(",") if tf.strip())

    @property
    def trend_tf_list(self) -> list[str]:
        return self.trend_tfs.split(",")

    @property
    def rr_ratio(self) -> float:
        return self.atr_tp_mult / self.atr_sl_mult if self.atr_sl_mult else 0.0


_settings: Settings | None = None


def get_settings() -> Settings:
    """Singleton accessor — first call loads .env, subsequent calls reuse."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
