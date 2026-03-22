"""
quantify.config
~~~~~~~~~~~~~~~
Loads and validates system configuration from:

  1. config/settings.yaml   — base values
  2. .env                   — secrets (never committed)
  3. Environment variables  — runtime overrides (highest priority)

Usage
-----
    from quantify.config import settings

    # Typed access
    print(settings.alpaca.paper)           # True
    print(settings.risk.max_single_position)  # 0.10
    print(settings.strategies["pairs_mean_reversion"].allocation)  # 0.20

    # Raw dict (for libraries that need plain dicts)
    raw = settings.to_dict()
"""

from __future__ import annotations

import logging
import logging.config
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _find_repo_root() -> Path:
    """
    Locate the repository root that contains ``config/settings.yaml``.

    Resolution order (first match wins):
    1. ``QUANTIFY_HOME`` environment variable — explicit override.
    2. ``parents[2]`` of this file — works in the ``src/`` dev layout
       (src/quantify/config.py → src → repo root).
    3. ``Path.cwd()`` — works when installed as a wheel and the process
       working directory is set to the repo root (e.g. via systemd
       ``WorkingDirectory``).
    """
    # 1. Explicit env override
    env_home = os.environ.get("QUANTIFY_HOME")
    if env_home:
        return Path(env_home).resolve()

    # 2. Dev / editable-install layout: src/quantify/config.py
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "config" / "settings.yaml").exists():
        return candidate

    # 3. Installed wheel: use CWD (systemd WorkingDirectory)
    return Path.cwd()


_REPO_ROOT = _find_repo_root()
_CONFIG_DIR = _REPO_ROOT / "config"
_SETTINGS_PATH = _CONFIG_DIR / "settings.yaml"
_LOGGING_PATH = _CONFIG_DIR / "logging.yaml"
_ENV_PATH = _REPO_ROOT / ".env"


# ---------------------------------------------------------------------------
# Typed settings dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DataSettings:
    cache_dir: Path
    default_provider: str
    universe: list[str]
    bar_timeframe: str
    history_years: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DataSettings":
        return cls(
            cache_dir=Path(d["cache_dir"]),
            default_provider=str(d.get("default_provider", "yfinance")),
            universe=list(d.get("universe", [])),
            bar_timeframe=str(d.get("bar_timeframe", "1Day")),
            history_years=int(d.get("history_years", 5)),
        )


@dataclass
class AlpacaSettings:
    paper: bool
    base_url_paper: str
    base_url_live: str
    data_url: str
    api_key: str
    secret_key: str

    @property
    def base_url(self) -> str:
        """Return the appropriate REST base URL based on paper flag."""
        return self.base_url_paper if self.paper else self.base_url_live

    @classmethod
    def from_dict(cls, d: dict[str, Any], env: dict[str, str]) -> "AlpacaSettings":
        # Env vars take precedence over YAML for paper flag
        paper_env = env.get("ALPACA_PAPER", "").lower()
        if paper_env in ("false", "0", "no"):
            paper = False
        elif paper_env in ("true", "1", "yes"):
            paper = True
        else:
            paper = bool(d.get("paper", True))

        api_key = env.get("ALPACA_API_KEY", "")
        secret_key = env.get("ALPACA_SECRET_KEY", "")
        if not api_key or not secret_key:
            log.warning(
                "ALPACA_API_KEY / ALPACA_SECRET_KEY not set — "
                "live/paper trading will be unavailable."
            )
        return cls(
            paper=paper,
            base_url_paper=str(d.get("base_url_paper", "https://paper-api.alpaca.markets")),
            base_url_live=str(d.get("base_url_live", "https://api.alpaca.markets")),
            data_url=str(d.get("data_url", "https://data.alpaca.markets")),
            api_key=api_key,
            secret_key=secret_key,
        )


@dataclass
class RiskSettings:
    max_portfolio_drawdown: float
    max_gross_leverage: float
    max_single_position: float
    max_sector_exposure: float
    daily_loss_limit: float
    default_stop_loss: float
    default_take_profit: float
    default_position_sizer: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RiskSettings":
        return cls(
            max_portfolio_drawdown=float(d.get("max_portfolio_drawdown", 0.15)),
            max_gross_leverage=float(d.get("max_gross_leverage", 1.5)),
            max_single_position=float(d.get("max_single_position", 0.10)),
            max_sector_exposure=float(d.get("max_sector_exposure", 0.30)),
            daily_loss_limit=float(d.get("daily_loss_limit", 0.03)),
            default_stop_loss=float(d.get("default_stop_loss", 0.02)),
            default_take_profit=float(d.get("default_take_profit", 0.04)),
            default_position_sizer=str(d.get("default_position_sizer", "equal_weight")),
        )


@dataclass
class BacktestSettings:
    initial_capital: float
    commission_per_share: float
    spread_bps: float
    slippage_pct: float
    benchmark: str
    rebalance_frequency: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BacktestSettings":
        return cls(
            initial_capital=float(d.get("initial_capital", 100_000)),
            commission_per_share=float(d.get("commission_per_share", 0.005)),
            spread_bps=float(d.get("spread_bps", 5)),
            slippage_pct=float(d.get("slippage_pct", 0.05)),
            benchmark=str(d.get("benchmark", "SPY")),
            rebalance_frequency=str(d.get("rebalance_frequency", "weekly")),
        )


@dataclass
class StrategyConfig:
    """Generic container for a single strategy's configuration block."""

    name: str
    enabled: bool
    allocation: float
    params: dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a parameter by name, falling back to *default*."""
        return self.params.get(key, default)

    def __getattr__(self, item: str) -> Any:
        # Allow attribute-style access to params (e.g. config.entry_zscore)
        try:
            return self.params[item]
        except KeyError:
            raise AttributeError(
                f"StrategyConfig '{self.name}' has no parameter '{item}'"
            ) from None

    @classmethod
    def from_dict(cls, name: str, d: dict[str, Any]) -> "StrategyConfig":
        return cls(
            name=name,
            enabled=bool(d.get("enabled", True)),
            allocation=float(d.get("allocation", 0.0)),
            params={k: v for k, v in d.items() if k not in ("enabled", "allocation")},
        )


# ---------------------------------------------------------------------------
# Top-level Settings
# ---------------------------------------------------------------------------


@dataclass
class Settings:
    data: DataSettings
    alpaca: AlpacaSettings
    risk: RiskSettings
    backtest: BacktestSettings
    strategies: dict[str, StrategyConfig]
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Return the raw merged configuration dictionary."""
        return dict(self._raw)

    def strategy(self, name: str) -> StrategyConfig:
        """Look up a strategy config by name, raising KeyError if missing."""
        try:
            return self.strategies[name]
        except KeyError:
            available = ", ".join(self.strategies)
            raise KeyError(
                f"Unknown strategy '{name}'. Available: {available}"
            ) from None

    @classmethod
    def from_dict(cls, raw: dict[str, Any], env: dict[str, str]) -> "Settings":
        strategies = {
            name: StrategyConfig.from_dict(name, cfg)
            for name, cfg in raw.get("strategies", {}).items()
        }
        return cls(
            data=DataSettings.from_dict(raw.get("data", {})),
            alpaca=AlpacaSettings.from_dict(raw.get("alpaca", {}), env),
            risk=RiskSettings.from_dict(raw.get("risk", {})),
            backtest=BacktestSettings.from_dict(raw.get("backtest", {})),
            strategies=strategies,
            _raw=raw,
        )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file and return its contents as a dict."""
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*. Returns a new dict."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(raw: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    """
    Apply a small set of well-known environment variable overrides to *raw*.
    Supports:
      DATA_CACHE_DIR → data.cache_dir
      LOG_LEVEL      → (handled in logging setup, not in raw config)
    """
    overrides: dict[str, Any] = {}

    if "DATA_CACHE_DIR" in env:
        overrides.setdefault("data", {})["cache_dir"] = env["DATA_CACHE_DIR"]

    return _deep_merge(raw, overrides) if overrides else raw


def configure_logging(log_cfg_path: Path | None = None) -> None:
    """
    Configure Python's logging subsystem from *logging.yaml*.

    Creates the ``logs/`` directory if it does not exist so that file
    handlers don't error on startup.
    """
    cfg_path = log_cfg_path or _LOGGING_PATH
    logs_dir = _REPO_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)

    if cfg_path.exists():
        cfg = _load_yaml(cfg_path)
        logging.config.dictConfig(cfg)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        )
        log.warning("logging.yaml not found at %s — using basicConfig fallback.", cfg_path)


def load_settings(
    settings_path: Path | None = None,
    env_path: Path | None = None,
    *,
    configure_log: bool = True,
) -> Settings:
    """
    Load, merge, and validate configuration.

    Parameters
    ----------
    settings_path:
        Path to ``settings.yaml``. Defaults to ``config/settings.yaml``
        relative to the repository root.
    env_path:
        Path to ``.env`` file. Defaults to ``.env`` in the repository root.
    configure_log:
        If ``True`` (default), also configure Python's logging subsystem
        from ``config/logging.yaml``.

    Returns
    -------
    Settings
        Fully populated, typed settings object.
    """
    # 1. Load .env (silently ignored if absent)
    _env_file = env_path or _ENV_PATH
    load_dotenv(_env_file, override=False)  # don't clobber already-set env vars
    env: dict[str, str] = {k: v for k, v in os.environ.items() if v}

    # 2. Load YAML
    yaml_path = settings_path or _SETTINGS_PATH
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"settings.yaml not found at {yaml_path}. "
            "Ensure the repository was set up correctly."
        )
    raw = _load_yaml(yaml_path)

    # 3. Apply env-variable overrides
    raw = _apply_env_overrides(raw, env)

    # 4. Build typed Settings
    result = Settings.from_dict(raw, env)

    # 5. Ensure cache directory exists
    result.data.cache_dir.mkdir(parents=True, exist_ok=True)

    # 6. Optionally configure logging
    if configure_log:
        configure_logging()

    log.debug("Configuration loaded from %s", yaml_path)
    return result


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

def _build_singleton() -> Settings:
    """Build the module-level singleton, deferring errors to first attribute access."""
    try:
        return load_settings()
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load settings at import time: %s", exc)
        # Return a minimal stub so that ``from quantify.config import settings``
        # succeeds even in environments without a settings.yaml (e.g. CI).
        raise


try:
    settings: Settings = _build_singleton()
except Exception:
    # Re-expose as a callable so callers can load lazily:
    #   from quantify.config import load_settings
    #   settings = load_settings()
    settings = None  # type: ignore[assignment]


__all__ = [
    "Settings",
    "DataSettings",
    "AlpacaSettings",
    "RiskSettings",
    "BacktestSettings",
    "StrategyConfig",
    "load_settings",
    "configure_logging",
    "settings",
]
