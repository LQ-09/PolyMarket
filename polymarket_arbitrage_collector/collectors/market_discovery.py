"""Helpers for resolving Polymarket token IDs via Gamma API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
DEFAULT_MARKET_SLUG = "btc-updown-15m-1768907700"


@dataclass(frozen=True)
class TokenResolution:
    up_token_id: Optional[str]
    down_token_id: Optional[str]
    all_token_ids: List[str]
    raw: Dict[str, Any]


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
    return {"up": up_token, "down": down_token}


def _extract_market_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list) and data:
            return data[0]
        if "market" in payload and isinstance(payload["market"], dict):
            return payload["market"]
    if isinstance(payload, list) and payload:
        return payload[0]
    return {}


def slug_from_market_url(url: str) -> str:
    """Extract a market slug from a Polymarket event URL."""

    parsed = urlparse(url)
    if not parsed.path:
        raise ValueError("Invalid market URL")
    parts = [segment for segment in parsed.path.split("/") if segment]
    if not parts:
        raise ValueError("Invalid market URL path")
    return parts[-1]


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
    params: Dict[str, str] = {}
    if market_slug:
        params["slug"] = market_slug
    if condition_id:
        params["conditionId"] = condition_id
    response = requests.get(f"{GAMMA_BASE_URL}/markets", params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    market = _extract_market_payload(payload)
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
