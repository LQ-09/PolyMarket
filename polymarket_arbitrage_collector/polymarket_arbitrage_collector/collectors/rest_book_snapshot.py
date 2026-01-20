"""REST snapshot collection for Polymarket CLOB order books."""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

BASE_URL = "https://clob.polymarket.com"
BOOK_ENDPOINT = "/book"


def _parse_levels(levels: Iterable[Any]) -> List[List[float]]:
    normalized: List[List[float]] = []
    for level in levels:
        if isinstance(level, dict):
            price = float(level.get("price", 0.0))
            size = float(level.get("size", 0.0))
        else:
            price = float(level[0])
            size = float(level[1])
        normalized.append([price, size])
    return normalized


def normalize_book_snapshot(raw: Dict[str, Any], token_id: str) -> Dict[str, Any]:
    """Normalize REST response to the snapshot schema."""

    timestamp = float(raw.get("timestamp") or time.time())
    bids = _parse_levels(raw.get("bids", []))
    asks = _parse_levels(raw.get("asks", []))
    return {
        "ts": timestamp,
        "token_id": token_id,
        "bids": bids,
        "asks": asks,
        "tick_size": float(raw.get("tick_size") or 0.0),
        "min_order_size": float(raw.get("min_order_size") or 0.0),
        "raw": raw,
    }


@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5))
def fetch_book_snapshot(token_id: str, timeout: float = 10.0) -> Dict[str, Any]:
    """Fetch a REST snapshot for a token id."""

    url = f"{BASE_URL}{BOOK_ENDPOINT}"
    response = requests.get(url, params={"asset_id": token_id}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return normalize_book_snapshot(payload, token_id)
