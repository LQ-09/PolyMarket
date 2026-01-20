"""Risk management module for tracking open positions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Position:
    open_timestamp: float
    cost: float
    expiry_timestamp: float


@dataclass
class BasicRiskManager:
    max_open_positions: int
    expiry_seconds: float
    positions: List[Position] = field(default_factory=list)
    realized_pnl: float = 0.0

    def can_open_position(self) -> bool:
        return len(self.positions) < self.max_open_positions

    def open_position(self, cost: float, timestamp: float) -> None:
        expiry_timestamp = timestamp + self.expiry_seconds
        self.positions.append(
            Position(
                open_timestamp=timestamp,
                cost=cost,
                expiry_timestamp=expiry_timestamp,
            )
        )

    def settle_positions(self, current_timestamp: float) -> int:
        remaining: List[Position] = []
        settled_count = 0
        for position in self.positions:
            if current_timestamp >= position.expiry_timestamp:
                pnl = 1.0 - position.cost
                self.realized_pnl += pnl
                settled_count += 1
            else:
                remaining.append(position)
        self.positions = remaining
        return settled_count
