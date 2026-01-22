"""Strategy definitions for Polymarket arbitrage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .data import OrderBookSnapshot


@dataclass(frozen=True)
class ArbitrageOpportunity:
    up_price: float
    down_price: float
    timestamp: float
    edge: float


class SimpleArbitrageStrategy:
    """Detects basic arbitrage between Up and Down contracts."""

    def __init__(self, profit_threshold: float, fee_rate: float) -> None:
        self.profit_threshold = float(profit_threshold)
        self.fee_rate = float(fee_rate)

    def __call__(self, snapshot: OrderBookSnapshot) -> List[ArbitrageOpportunity]:
        best_ask_up = _best_price(snapshot.up_asks)
        best_ask_down = _best_price(snapshot.down_asks)
        if best_ask_up is None or best_ask_down is None:
            return []
        total_cost = best_ask_up + best_ask_down
        edge = 1.0 - self.fee_rate - total_cost
        if total_cost < 1.0 - self.fee_rate - self.profit_threshold:
            return [
                ArbitrageOpportunity(
                    up_price=best_ask_up,
                    down_price=best_ask_down,
                    timestamp=snapshot.timestamp,
                    edge=edge,
                )
            ]
        return []


def _best_price(levels: List[tuple[float, float]]) -> Optional[float]:
    if not levels:
        return None
    return min(price for price, _ in levels)
