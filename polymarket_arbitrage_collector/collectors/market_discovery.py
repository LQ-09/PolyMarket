"""Helpers for resolving Polymarket token IDs via Gamma API."""

from __future__ import annotations

from dataclasses import dataclass
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
DEFAULT_MARKET_SLUG = "btc-updown-15m-1768907700"
DEFAULT_SERIES_SLUG = "btc-up-or-down-15m"


@dataclass(frozen=True)
class TokenResolution:
    up_token_id: Optional[str]
    down_token_id: Optional[str]
    all_token_ids: List[str]
    raw: Dict[str, Any]


def _parse_json_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return []
    return []


def _extract_token_ids(market: Dict[str, Any]) -> Dict[str, Optional[str]]:
    up_token = None
    down_token = None
    tokens = market.get("tokens") or []
    for token in tokens:
        if not isinstance(token, dict):
            continue
        token_id = token.get("token_id") or token.get("id")
        outcome = str(token.get("outcome") or "").lower()
        if not token_id:
            continue
        if outcome in ("yes", "up", "true"):
            up_token = str(token_id)
        elif outcome in ("no", "down", "false"):
            down_token = str(token_id)
    if up_token or down_token:
        return {"up": up_token, "down": down_token}
    clob_token_ids = _parse_json_list(market.get("clobTokenIds"))
    outcomes = _parse_json_list(market.get("outcomes"))
    if clob_token_ids and outcomes and len(clob_token_ids) == len(outcomes):
        for token_id, outcome in zip(clob_token_ids, outcomes):
            outcome_name = str(outcome).lower()
            if outcome_name in ("up", "yes", "true"):
                up_token = str(token_id)
            elif outcome_name in ("down", "no", "false"):
                down_token = str(token_id)
    return {"up": up_token, "down": down_token}


def _extract_market_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        value = payload.get("value")
        if isinstance(value, list) and value:
            return value[0]
        data = payload.get("data")
        if isinstance(data, list) and data:
            return data[0]
        if "market" in payload and isinstance(payload["market"], dict):
            return payload["market"]
    if isinstance(payload, list) and payload:
        return payload[0]
    return {}


def _extract_markets_list(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        value = payload.get("value")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _parse_iso_to_epoch(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def slug_from_market_url(url: str) -> str:
    """Extract a market slug from a Polymarket event URL."""

    parsed = urlparse(url)
    if not parsed.path:
        raise ValueError("Invalid market URL")
    parts = [segment for segment in parsed.path.split("/") if segment]
    if not parts:
        raise ValueError("Invalid market URL path")
    return parts[-1]


def _fetch_market_by_slug(slug: str, timeout: float) -> Dict[str, Any]:
    response = requests.get(
        f"{GAMMA_BASE_URL}/markets",
        params={"slug": slug},
        timeout=timeout,
    )
    response.raise_for_status()
    market = _extract_market_payload(response.json())
    if market:
        return market
    response = requests.get(f"{GAMMA_BASE_URL}/markets/{slug}", timeout=timeout)
    response.raise_for_status()
    return _extract_market_payload(response.json())


def _fetch_market_by_condition(condition_id: str, timeout: float) -> Dict[str, Any]:
    response = requests.get(
        f"{GAMMA_BASE_URL}/markets",
        params={"conditionId": condition_id},
        timeout=timeout,
    )
    response.raise_for_status()
    return _extract_market_payload(response.json())


def _fetch_markets_by_series(series_slug: str, timeout: float) -> List[Dict[str, Any]]:
    response = requests.get(
        f"{GAMMA_BASE_URL}/markets",
        params={"seriesSlug": series_slug},
        timeout=timeout,
    )
    response.raise_for_status()
    return _extract_markets_list(response.json())


@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5))
def resolve_token_ids(
    *,
    market_slug: Optional[str] = None,
    condition_id: Optional[str] = None,
    timeout: float = 10.0,
) -> TokenResolution:
    """Resolve Up/Down token IDs from Gamma API using slug or condition id."""

    if not market_slug and not condition_id:
        raise ValueError("market_slug or condition_id is required")
    market: Dict[str, Any] = {}
    if market_slug:
        market = _fetch_market_by_slug(market_slug, timeout)
    elif condition_id:
        market = _fetch_market_by_condition(condition_id, timeout)
    tokens = _extract_token_ids(market)
    all_tokens = [
        token_id
        for token_id in (tokens["up"], tokens["down"])
        if token_id is not None
    ]
    return TokenResolution(
        up_token_id=tokens["up"],
        down_token_id=tokens["down"],
        all_token_ids=all_tokens,
        raw=market,
    )


@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5))
def resolve_latest_series_market(
    *,
    series_slug: str,
    timeout: float = 10.0,
) -> TokenResolution:
    markets = _fetch_markets_by_series(series_slug, timeout)
    if not markets:
        return TokenResolution(None, None, [], {})
    def _score(market: Dict[str, Any]) -> Tuple[int, float]:
        active = int(bool(market.get("active") or market.get("acceptingOrders")))
        start_ts = _parse_iso_to_epoch(market.get("startDate")) or 0.0
        return (active, start_ts)

    selected = sorted(markets, key=_score, reverse=True)[0]
    tokens = _extract_token_ids(selected)
    all_tokens = [
        token_id for token_id in (tokens["up"], tokens["down"]) if token_id is not None
    ]
    return TokenResolution(
        up_token_id=tokens["up"],
        down_token_id=tokens["down"],
        all_token_ids=all_tokens,
        raw=selected,
    )


def resolve_market_window_seconds(
    market: Dict[str, Any],
    fallback_minutes: int = 15,
) -> Tuple[Optional[float], Optional[float]]:
    start_ts = _parse_iso_to_epoch(market.get("startDate"))
    end_ts = _parse_iso_to_epoch(market.get("endDate"))
    if start_ts and end_ts:
        return start_ts, end_ts
    event_start = _parse_iso_to_epoch(market.get("eventStartTime"))
    if event_start:
        return event_start, event_start + fallback_minutes * 60
    return None, None


def list_series_markets(
    *,
    series_slug: str,
    date_iso: Optional[str] = None,
    timeout: float = 10.0,
) -> List[Dict[str, Any]]:
    markets = _fetch_markets_by_series(series_slug, timeout)
    if not date_iso:
        return markets
    return [
        market
        for market in markets
        if market.get("startDateIso") == date_iso or market.get("endDateIso") == date_iso
    ]
