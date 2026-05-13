"""Application configuration loaded from .env with small, dependency-free parsing."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BROKERS = ["IBKR", "Schwab", "Firstrade", "Manual"]


@dataclass(frozen=True)
class AppConfig:
    brokers: list[str]
    default_broker: str


def load_app_config(env_path: Path | None = None) -> AppConfig:
    env_values = _read_env_file(env_path or ROOT_DIR / ".env")
    brokers = _parse_brokers(env_values.get("PORTFOLIO_BROKERS") or os.getenv("PORTFOLIO_BROKERS", ""))
    if not brokers:
        brokers = DEFAULT_BROKERS.copy()

    default_broker = (env_values.get("DEFAULT_BROKER") or os.getenv("DEFAULT_BROKER", "")).strip()
    if default_broker not in brokers:
        default_broker = brokers[0]
    return AppConfig(brokers=brokers, default_broker=default_broker)


def get_broker_names() -> list[str]:
    return load_app_config().brokers


def get_default_broker() -> str:
    return load_app_config().default_broker


def broker_index(brokers: list[str], *, default_broker: str, last_broker: str | None = None) -> int:
    if last_broker in brokers:
        return brokers.index(last_broker)
    if default_broker in brokers:
        return brokers.index(default_broker)
    return 0


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _parse_brokers(value: str) -> list[str]:
    brokers: list[str] = []
    seen = set()
    for part in value.replace(";", ",").split(","):
        broker = part.strip()
        if broker and broker not in seen:
            brokers.append(broker)
            seen.add(broker)
    return brokers
