"""Storage helpers for collected market data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


def _date_folder(date_str: str) -> str:
    return date_str


def build_raw_ws_path(out_dir: str, token_id: str, date_str: str) -> Path:
    base = Path(out_dir) / "raw_ws" / _date_folder(date_str)
    base.mkdir(parents=True, exist_ok=True)
    return base / f"ws_{token_id}.jsonl"


def build_snapshot_path(out_dir: str, token_id: str, date_str: str) -> Path:
    base = Path(out_dir) / "snapshots" / _date_folder(date_str)
    base.mkdir(parents=True, exist_ok=True)
    return base / f"snapshots_{token_id}.jsonl"


@dataclass
class JSONLWriter:
    path: Path

    def write(self, record: Dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


@dataclass
class ParquetWriter:
    path: Path
    batch_size: int = 500
    _buffer: List[Dict[str, Any]] = field(default_factory=list)

    def add(self, record: Dict[str, Any]) -> None:
        self._buffer.append(record)
        if len(self._buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        df = pd.DataFrame(self._buffer)
        self._buffer.clear()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            existing = pd.read_parquet(self.path)
            df = pd.concat([existing, df], ignore_index=True)
        df.to_parquet(self.path, index=False)


def utc_date_string(timestamp: float | None = None) -> str:
    if timestamp is None:
        timestamp = datetime.now(tz=timezone.utc).timestamp()
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")
