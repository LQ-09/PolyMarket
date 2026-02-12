#!/usr/bin/env python3
"""Download historical candles and recent trades from Gemini REST API.

Usage examples:
  python download_gemini_data.py \
      --symbol btcusd \
      --timeframe 1m \
      --start-time 2024-01-01T00:00:00Z \
      --end-time 2024-01-31T23:59:59Z \
      --max-records 2000

Notes:
- Candles are downloaded from: /v2/candles/{symbol}/{timeframe}
- Trades are downloaded from: /v1/trades/{symbol}
- Timestamps are saved in UTC.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import requests


BASE_URL = "https://api.gemini.com"
RAW_DIR = Path("data/raw")
MAX_RETRIES = 6
BACKOFF_BASE_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 30


class GeminiAPIError(RuntimeError):
    """Raised when Gemini API returns an unrecoverable error."""


def parse_datetime_to_ms(value: str) -> int:
    """Parse an ISO-8601 datetime string (or YYYY-MM-DD) into epoch milliseconds."""
    parsed = value.strip()

    # Accept trailing Z and date-only formats.
    if parsed.endswith("Z"):
        parsed = parsed[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(parsed)
    except ValueError:
        # Fallback for date-only input like 2024-01-01.
        try:
            dt = datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"Invalid datetime '{value}'. Use ISO-8601 or YYYY-MM-DD."
            ) from exc

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return int(dt.timestamp() * 1000)


def format_yyyymmdd(epoch_ms: int) -> str:
    """Format epoch milliseconds as UTC YYYYMMDD."""
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y%m%d")


def get_timeframe_ms(timeframe: str) -> int:
    """Convert Gemini timeframe label to milliseconds."""
    mapping = {
        "1m": 60_000,
        "5m": 5 * 60_000,
        "15m": 15 * 60_000,
        "30m": 30 * 60_000,
        "1hr": 60 * 60_000,
        "6hr": 6 * 60 * 60_000,
        "1day": 24 * 60 * 60_000,
    }
    if timeframe not in mapping:
        valid = ", ".join(mapping.keys())
        raise argparse.ArgumentTypeError(
            f"Unsupported timeframe '{timeframe}'. Supported values: {valid}"
        )
    return mapping[timeframe]


def request_with_retry(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """GET helper with exponential backoff for network/rate-limit/server issues."""
    last_error: Optional[Exception] = None

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)

            # Retry on rate-limit and transient server errors.
            if response.status_code in {429, 500, 502, 503, 504}:
                raise GeminiAPIError(
                    f"Transient API error {response.status_code}: {response.text[:200]}"
                )

            response.raise_for_status()
            return response.json()
        except (requests.RequestException, GeminiAPIError) as exc:
            last_error = exc
            if attempt == MAX_RETRIES - 1:
                break
            sleep_seconds = BACKOFF_BASE_SECONDS * (2 ** attempt)
            print(
                f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}). "
                f"Retrying in {sleep_seconds:.1f}s... Error: {exc}"
            )
            time.sleep(sleep_seconds)

    raise GeminiAPIError(f"Request failed after {MAX_RETRIES} attempts: {last_error}")


def normalize_candles(candles: Iterable[List[Any]]) -> pd.DataFrame:
    """Normalize raw Gemini candle payload into required column format."""
    rows = list(candles)
    if not rows:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    # Gemini candle row format: [timestamp_ms, open, high, low, close, volume]
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Ensure chronological order and unique timestamps.
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    return df.reset_index(drop=True)


def download_candles(symbol: str, timeframe: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    """Download all candles between start_ms and end_ms using Gemini v2 endpoint."""
    url = f"{BASE_URL}/v2/candles/{symbol}/{timeframe}"
    timeframe_ms = get_timeframe_ms(timeframe)

    all_rows: List[List[Any]] = []
    cursor = start_ms

    while cursor <= end_ms:
        params = {"start": cursor, "end": end_ms}
        payload = request_with_retry(url, params=params)

        if not isinstance(payload, list):
            raise GeminiAPIError(f"Unexpected candles response: {payload}")

        if not payload:
            break

        all_rows.extend(payload)

        # Move cursor to the next candle after the newest timestamp from this page.
        newest_ts = max(int(row[0]) for row in payload)
        next_cursor = newest_ts + timeframe_ms

        # Safety break to avoid infinite loop if API returns unexpected data.
        if next_cursor <= cursor:
            break

        cursor = next_cursor

        # If the endpoint returned a very small page near the end, we may already be done.
        if newest_ts >= end_ms:
            break

    df = normalize_candles(all_rows)

    # Keep only requested range.
    mask = (df["timestamp"] >= pd.to_datetime(start_ms, unit="ms", utc=True)) & (
        df["timestamp"] <= pd.to_datetime(end_ms, unit="ms", utc=True)
    )
    return df.loc[mask].reset_index(drop=True)


def normalize_trades(trades: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    """Normalize raw Gemini trades payload into required column format."""
    rows = list(trades)
    if not rows:
        return pd.DataFrame(columns=["timestamp", "price", "quantity", "side"])

    normalized = []
    for trade in rows:
        normalized.append(
            {
                "timestamp": trade.get("timestampms") or trade.get("timestamp"),
                "price": trade.get("price"),
                "quantity": trade.get("amount"),
                "side": trade.get("type") or trade.get("side"),
            }
        )

    df = pd.DataFrame(normalized)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True, errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["side"] = df["side"].astype("string")

    df = df.dropna(subset=["timestamp", "price", "quantity"]).sort_values("timestamp")
    df = df.drop_duplicates(subset=["timestamp", "price", "quantity", "side"], keep="last")
    return df.reset_index(drop=True)


def download_recent_trades(symbol: str, max_records: int) -> pd.DataFrame:
    """Download recent trades up to max_records (subject to Gemini API limits)."""
    url = f"{BASE_URL}/v1/trades/{symbol}"
    page_size = min(500, max_records) if max_records > 0 else 500

    all_trades: List[Dict[str, Any]] = []
    cursor_timestamp: Optional[int] = None

    while len(all_trades) < max_records:
        params: Dict[str, Any] = {"limit_trades": page_size}
        if cursor_timestamp is not None:
            # Request older trades by using a timestamp cursor.
            params["timestamp"] = cursor_timestamp

        payload = request_with_retry(url, params=params)

        if not isinstance(payload, list):
            raise GeminiAPIError(f"Unexpected trades response: {payload}")

        if not payload:
            break

        all_trades.extend(payload)

        # Gemini returns most recent trades first; step back using oldest trade timestamp.
        oldest_ts = min(int(t.get("timestampms", 0)) for t in payload if t.get("timestampms") is not None)
        next_cursor = oldest_ts - 1

        # Stop if cursor no longer progresses.
        if cursor_timestamp is not None and next_cursor >= cursor_timestamp:
            break
        cursor_timestamp = next_cursor

        # Break early if less than full page returned (likely no more history exposed by endpoint).
        if len(payload) < page_size:
            break

    # Respect max_records strictly after deduplication.
    df = normalize_trades(all_trades)
    if len(df) > max_records:
        df = df.iloc[-max_records:].reset_index(drop=True)
    return df


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""
    parser = argparse.ArgumentParser(description="Download Gemini candle and trade data to parquet.")
    parser.add_argument("--symbol", required=True, help="Trading symbol, e.g. btcusd")
    parser.add_argument("--timeframe", required=True, help="Candle timeframe, e.g. 1m")
    parser.add_argument(
        "--start-time",
        required=True,
        type=parse_datetime_to_ms,
        help="Start time (ISO-8601 or YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-time",
        required=True,
        type=parse_datetime_to_ms,
        help="End time (ISO-8601 or YYYY-MM-DD).",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=1000,
        help="Maximum number of recent trades to fetch (default: 1000).",
    )
    return parser


def main() -> None:
    """Program entrypoint."""
    parser = build_arg_parser()
    args = parser.parse_args()

    symbol = args.symbol.lower()
    timeframe = args.timeframe
    start_ms = args.start_time
    end_ms = args.end_time
    max_records = args.max_records

    if start_ms >= end_ms:
        parser.error("--start-time must be earlier than --end-time")
    if max_records <= 0:
        parser.error("--max-records must be a positive integer")

    # Ensure output directory exists.
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("Downloading candles...")
    candles_df = download_candles(symbol=symbol, timeframe=timeframe, start_ms=start_ms, end_ms=end_ms)

    start_str = format_yyyymmdd(start_ms)
    end_str = format_yyyymmdd(end_ms)
    candles_path = RAW_DIR / f"{symbol}_{timeframe}_{start_str}_{end_str}.parquet"
    candles_df.to_parquet(candles_path, engine="pyarrow", index=False)

    print("Downloading recent trades...")
    trades_df = download_recent_trades(symbol=symbol, max_records=max_records)
    trades_path = RAW_DIR / f"{symbol}_trades_recent.parquet"
    trades_df.to_parquet(trades_path, engine="pyarrow", index=False)

    # Final summary statistics.
    print("\nDownload complete:")
    print(f"- Candle rows: {len(candles_df)}")
    print(f"- Trade rows: {len(trades_df)}")
    print(f"- Candles saved to: {candles_path}")
    print(f"- Trades saved to: {trades_path}")


if __name__ == "__main__":
    main()
