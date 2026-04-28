"""
IBKR Flex Web Service client.

Downloads a pre-configured Flex Query report using credentials from .env.
"""
from __future__ import annotations

import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
DEFAULT_VERSION = "3"
DEFAULT_WAIT_SECONDS = 20
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_SECONDS = 10
RETRYABLE_ERROR_CODES = {
    "1001", "1004", "1005", "1006", "1007", "1008", "1009", "1018", "1019", "1021"
}


class IBKRFlexError(Exception):
    """Raised when IBKR Flex Web Service returns an error or invalid response."""


@dataclass(frozen=True)
class IBKRFlexConfig:
    token: str
    query_id: str
    version: str = DEFAULT_VERSION
    base_url: str = DEFAULT_BASE_URL
    wait_seconds: int = DEFAULT_WAIT_SECONDS
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    retry_seconds: int = DEFAULT_RETRY_SECONDS


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE pairs without adding an extra dependency."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_ibkr_flex_config() -> IBKRFlexConfig:
    """Load IBKR Flex settings from environment variables and project .env."""
    _load_dotenv(ROOT_DIR / ".env")

    token = os.getenv("IBKR_FLEX_TOKEN", "").strip()
    query_id = os.getenv("IBKR_FLEX_QUERY_ID", "").strip()

    if not token:
        raise IBKRFlexError("缺少 IBKR_FLEX_TOKEN，请先在 .env 中配置 Flex Web Service token。")
    if not query_id:
        raise IBKRFlexError("缺少 IBKR_FLEX_QUERY_ID，请先在 .env 中配置 Flex Query ID。")

    return IBKRFlexConfig(
        token=token,
        query_id=query_id,
        version=os.getenv("IBKR_FLEX_VERSION", DEFAULT_VERSION).strip() or DEFAULT_VERSION,
        base_url=os.getenv("IBKR_FLEX_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        wait_seconds=_env_int("IBKR_FLEX_WAIT_SECONDS", DEFAULT_WAIT_SECONDS),
        timeout_seconds=_env_int("IBKR_FLEX_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
        max_attempts=max(1, _env_int("IBKR_FLEX_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS)),
        retry_seconds=max(1, _env_int("IBKR_FLEX_RETRY_SECONDS", DEFAULT_RETRY_SECONDS)),
    )


def download_ibkr_flex_report(config: Optional[IBKRFlexConfig] = None) -> bytes:
    """Generate and download the configured IBKR Flex Query report."""
    config = config or load_ibkr_flex_config()

    reference_code = _send_request(config)
    if config.wait_seconds > 0:
        time.sleep(config.wait_seconds)

    for attempt in range(1, config.max_attempts + 1):
        report = _get_statement(config, reference_code)
        if not _looks_like_flex_error(report):
            return report

        error_code, error_message = _read_flex_error(report)
        should_retry = error_code in RETRYABLE_ERROR_CODES and attempt < config.max_attempts
        if not should_retry:
            _raise_flex_error(report)

        time.sleep(config.retry_seconds)

    raise IBKRFlexError("IBKR 报表生成超时，请稍后再试。")


def _send_request(config: IBKRFlexConfig) -> str:
    response = _request(
        config,
        "/SendRequest",
        {"t": config.token, "q": config.query_id, "v": config.version},
    )

    root = _parse_xml(response)
    status = root.findtext("Status", default="")
    if status != "Success":
        _raise_flex_error(response)

    reference_code = root.findtext("ReferenceCode", default="").strip()
    if not reference_code:
        raise IBKRFlexError("IBKR 没有返回 ReferenceCode，无法继续下载报表。")

    return reference_code


def _get_statement(config: IBKRFlexConfig, reference_code: str) -> bytes:
    return _request(
        config,
        "/GetStatement",
        {"t": config.token, "q": reference_code, "v": config.version},
    )


def _request(config: IBKRFlexConfig, path: str, params: dict[str, str]) -> bytes:
    query = urllib.parse.urlencode(params)
    url = f"{config.base_url.rstrip('/')}{path}?{query}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Python/3.11"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            return response.read()
    except Exception as exc:
        raise IBKRFlexError(f"连接 IBKR Flex Web Service 失败: {exc}") from exc


def _parse_xml(content: bytes) -> ET.Element:
    try:
        return ET.fromstring(content)
    except ET.ParseError as exc:
        raise IBKRFlexError("IBKR 返回了无法解析的 XML 响应。") from exc


def _looks_like_flex_error(content: bytes) -> bool:
    stripped = content.lstrip()
    return stripped.startswith(b"<FlexStatementResponse")


def _raise_flex_error(content: bytes) -> None:
    error_code, error_message, status = _read_flex_error(content)

    if error_code:
        raise IBKRFlexError(f"IBKR Flex 请求失败 ({error_code}): {error_message}")
    raise IBKRFlexError(f"IBKR Flex 请求失败 ({status}): {error_message}")


def _read_flex_error(content: bytes) -> tuple[str, str, str]:
    root = _parse_xml(content)
    return (
        root.findtext("ErrorCode", default="").strip(),
        root.findtext("ErrorMessage", default="未知错误").strip(),
        root.findtext("Status", default="Fail").strip(),
    )


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default
