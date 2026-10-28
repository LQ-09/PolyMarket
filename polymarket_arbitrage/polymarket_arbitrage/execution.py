"""Execution engines for simulated or live trading."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import List

from .risk import BasicRiskManager
from .strategy import ArbitrageOpportunity


class ExecutionEngine(abc.ABC):
    """Abstract execution engine."""

    @abc.abstractmethod
    def execute(self, opportunity: ArbitrageOpportunity) -> bool:
        """Return whether the opportunity was executed."""
        raise NotImplementedError


@dataclass
class ExecutionRecord:
    timestamp: float
    cost: float
    edge: float


class SimulationExecutionEngine(ExecutionEngine):
    """Simulates execution by immediately filling both legs."""

    def __init__(self, risk_manager: BasicRiskManager, fee_rate: float) -> None:
        self.risk_manager = risk_manager
        self.fee_rate = float(fee_rate)
        self.records: List[ExecutionRecord] = []

    def execute(self, opportunity: ArbitrageOpportunity) -> bool:
        cost = opportunity.up_price + opportunity.down_price + self.fee_rate
        if not self.risk_manager.can_open_position():
            return False
        self.risk_manager.open_position(cost, opportunity.timestamp)
        self.records.append(
            ExecutionRecord(
                timestamp=opportunity.timestamp,
                cost=cost,
                edge=opportunity.edge,
            )
        )

        return True


class LiveExecutionEngine(ExecutionEngine):
    """Skeleton for live execution (no real orders)."""

    def execute(self, opportunity: ArbitrageOpportunity) -> bool:
        print(
            "[LIVE] Would execute arbitrage: "
            f"up={opportunity.up_price:.4f}, "
            f"down={opportunity.down_price:.4f}, "
            f"edge={opportunity.edge:.4f}"
        )
        return False
