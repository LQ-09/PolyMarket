"""WebSocket market data collector for Polymarket."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from websocket import WebSocketApp

from ..storage.writers import JSONLWriter, build_raw_ws_path, build_snapshot_path

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def _parse_levels(levels: List[Any]) -> List[List[float]]:
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


def _trim_levels(
    levels: List[List[float]],
    side: str,
    depth: Optional[int],
) -> List[List[float]]:
    if depth is None:
        return levels
    if side == "bids":
        sorted_levels = sorted(levels, key=lambda x: x[0], reverse=True)
    else:
        sorted_levels = sorted(levels, key=lambda x: x[0])
    return sorted_levels[:depth]


def _utc_date_string(timestamp: Optional[float] = None) -> str:
    if timestamp is None:
        timestamp = time.time()
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")


@dataclass
class BookState:
    bids: List[List[float]]
    asks: List[List[float]]
    tick_size: float = 0.0
    min_order_size: float = 0.0


class MarketWSCollector:
    """Collects market data via WebSocket and persists raw + snapshots."""

    def __init__(
        self,
        token_ids: List[str],
        out_dir: str,
        snapshot_every: Optional[float],
        depth: Optional[int] = None,
        ping_interval: float = 5.0,
        side_map: Optional[Dict[str, str]] = None,
    ) -> None:
        self.token_ids = token_ids
        self.out_dir = out_dir
        self.snapshot_every = snapshot_every
        self.depth = depth
        self.ping_interval = ping_interval
        self.side_map = side_map or {}
        self._ws: Optional[WebSocketApp] = None
        self._stop_event = threading.Event()
        self._book_state: Dict[str, BookState] = {}
        self._snapshot_lock = threading.Lock()
        self._last_snapshot_ts = 0.0
        self._raw_writers: Dict[str, JSONLWriter] = {}
        self._snapshot_writers: Dict[str, JSONLWriter] = {}

    def connect(self) -> None:
        backoff = 1.0
        while not self._stop_event.is_set():
            logger.info("Connecting to websocket")
            self._ws = WebSocketApp(
                WS_URL,
                on_open=self._on_open,
                on_message=self._on_message,
                on_close=self._on_close,
                on_error=self._on_error,
            )
            self._start_ping_loop()
            self._ws.run_forever()
            if self._stop_event.is_set():
                break
            logger.warning("Websocket disconnected, retrying in {:.1f}s", backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    def stop(self) -> None:
        self._stop_event.set()
        if self._ws:
            self._ws.close()

    def _start_ping_loop(self) -> None:
        def _ping() -> None:
            while not self._stop_event.is_set():
                if self._ws:
                    try:
                        self._ws.send("PING")
                    except Exception as exc:
                        logger.debug("Ping failed: {}", exc)
                time.sleep(self.ping_interval)

        threading.Thread(target=_ping, daemon=True).start()

    def _on_open(self, ws: WebSocketApp) -> None:
        subscribe = {"type": "market", "assets_ids": self.token_ids}
        ws.send(json.dumps(subscribe))
        logger.info("Subscribed to {} tokens", len(self.token_ids))

    def _on_message(self, ws: WebSocketApp, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            logger.debug("Failed to decode message")
            return
        token_id = self._extract_token_id(payload)
        if token_id:
            self._write_raw_message(token_id, payload)
        book = self._extract_book(payload)
        if token_id and book:
            self._book_state[token_id] = book
            self._maybe_write_snapshot(payload)

    def _on_close(self, ws: WebSocketApp, code: Any, reason: Any) -> None:
        logger.warning("Websocket closed: {} {}", code, reason)

    def _on_error(self, ws: WebSocketApp, error: Any) -> None:
        logger.error("Websocket error: {}", error)

    def _extract_token_id(self, payload: Dict[str, Any]) -> Optional[str]:
        for key in ("asset_id", "token_id", "market", "assetId"):
            value = payload.get(key)
            if value:
                return str(value)
        return None

    def _extract_book(self, payload: Dict[str, Any]) -> Optional[BookState]:
        if "book" in payload and isinstance(payload["book"], dict):
            book = payload["book"]
        else:
            book = payload
        if not isinstance(book, dict):
            return None
        bids = book.get("bids")
        asks = book.get("asks")
        if bids is None or asks is None:
            return None
        return BookState(
            bids=_parse_levels(bids),
            asks=_parse_levels(asks),
            tick_size=float(book.get("tick_size") or 0.0),
            min_order_size=float(book.get("min_order_size") or 0.0),
        )

    def _write_raw_message(self, token_id: str, payload: Dict[str, Any]) -> None:
        writer = self._raw_writers.get(token_id)
        if writer is None:
            path = build_raw_ws_path(self.out_dir, token_id, _utc_date_string())
            writer = JSONLWriter(path)
            self._raw_writers[token_id] = writer
        writer.write(payload)

    def _maybe_write_snapshot(self, payload: Dict[str, Any]) -> None:
        if self.snapshot_every is None:
            return
        now = time.time()
        with self._snapshot_lock:
            if now - self._last_snapshot_ts < self.snapshot_every:
                return
            self._last_snapshot_ts = now
        snapshot = self._build_combined_snapshot(now)
        if snapshot is None:
            return
        token_key = snapshot["token_id"]
        writer = self._snapshot_writers.get(token_key)
        if writer is None:
            path = build_snapshot_path(self.out_dir, token_key, _utc_date_string(now))
            writer = JSONLWriter(path)
            self._snapshot_writers[token_key] = writer
        writer.write(snapshot)

    def _build_combined_snapshot(self, timestamp: float) -> Optional[Dict[str, Any]]:
        if not self.side_map:
            return None
        up_token = self._token_for_side("up")
        down_token = self._token_for_side("down")
        if not up_token or not down_token:
            return None
        up_state = self._book_state.get(up_token)
        down_state = self._book_state.get(down_token)
        if not up_state or not down_state:
            return None
        return {
            "timestamp": timestamp,
            "up": {
                "bids": _trim_levels(up_state.bids, "bids", self.depth),
                "asks": _trim_levels(up_state.asks, "asks", self.depth),
            },
            "down": {
                "bids": _trim_levels(down_state.bids, "bids", self.depth),
                "asks": _trim_levels(down_state.asks, "asks", self.depth),
            },
            "token_id": f"{up_token}_{down_token}",
        }

    def _token_for_side(self, side: str) -> Optional[str]:
        for token, mapped_side in self.side_map.items():
            if mapped_side == side:
                return token
        return None
