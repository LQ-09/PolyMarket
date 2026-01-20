"""Data providers for Polymarket order book snapshots."""

from __future__ import annotations

import abc
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Sequence, Tuple

OrderBookSide = List[Tuple[float, float]]


@dataclass(frozen=True)
class OrderBookSnapshot:
    """Normalized snapshot structure for Up/Down markets."""

    timestamp: float
    up_bids: OrderBookSide
    up_asks: OrderBookSide
    down_bids: OrderBookSide
    down_asks: OrderBookSide


class BaseMarketDataProvider(abc.ABC):
    """Abstract data provider for market snapshots."""

    @abc.abstractmethod
    def __iter__(self) -> Iterator[OrderBookSnapshot]:
        raise NotImplementedError


def _parse_side(entries: Sequence[Sequence[float]]) -> OrderBookSide:
    return [(float(price), float(size)) for price, size in entries]


def _from_raw_snapshot(raw: Dict[str, object]) -> OrderBookSnapshot:
    up = raw["up"]
    down = raw["down"]
    if not isinstance(up, dict) or not isinstance(down, dict):
        raise ValueError("Invalid snapshot structure: missing up/down")
    return OrderBookSnapshot(
        timestamp=float(raw["timestamp"]),
        up_bids=_parse_side(up.get("bids", [])),
        up_asks=_parse_side(up.get("asks", [])),
        down_bids=_parse_side(down.get("bids", [])),
        down_asks=_parse_side(down.get("asks", [])),
    )


class JsonMarketDataProvider(BaseMarketDataProvider):
    """Reads snapshots from a local JSON or CSV file for backtests."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def __iter__(self) -> Iterator[OrderBookSnapshot]:
        if self.path.suffix.lower() == ".json":
            yield from self._iter_json()
        elif self.path.suffix.lower() == ".csv":
            yield from self._iter_csv()
        else:
            raise ValueError(f"Unsupported file type: {self.path.suffix}")

    def _iter_json(self) -> Iterator[OrderBookSnapshot]:
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            payload = payload.get("data", [])
        if not isinstance(payload, Iterable):
            raise ValueError("JSON payload must be a list of snapshots")
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            yield _from_raw_snapshot(raw)

    def _iter_csv(self) -> Iterator[OrderBookSnapshot]:
        with self.path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                yield OrderBookSnapshot(
                    timestamp=float(row["timestamp"]),
                    up_bids=_parse_side(json.loads(row["up_bids"])),
                    up_asks=_parse_side(json.loads(row["up_asks"])),
                    down_bids=_parse_side(json.loads(row["down_bids"])),
                    down_asks=_parse_side(json.loads(row["down_asks"])),
                )


class RealTimeMarketDataProvider(BaseMarketDataProvider):
    """Skeleton for realtime data provider (no actual API calls)."""

    def __iter__(self) -> Iterator[OrderBookSnapshot]:
        raise NotImplementedError("Realtime data provider not implemented.")
