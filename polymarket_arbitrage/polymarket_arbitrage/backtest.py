"""Backtesting engine for Polymarket arbitrage strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .data import BaseMarketDataProvider, OrderBookSnapshot
from .execution import ExecutionEngine, SimulationExecutionEngine
from .risk import BasicRiskManager
from .strategy import ArbitrageOpportunity, SimpleArbitrageStrategy


@dataclass
class BacktestResult:
    total_pnl: float
    trades: int
    avg_pnl_per_trade: float
    max_open_positions: int


class Backtester:
    """Runs a strategy against historical data and collects metrics."""

    def __init__(
        self,
        data_provider: BaseMarketDataProvider,
        strategy: SimpleArbitrageStrategy,
        execution_engine: ExecutionEngine,
        risk_manager: BasicRiskManager,
    ) -> None:
        self.data_provider = data_provider
        self.strategy = strategy
        self.execution_engine = execution_engine
        self.risk_manager = risk_manager
        self.max_open_positions = 0

    def run(self) -> BacktestResult:
        trades = 0
        for snapshot in self._iter_snapshots(self.data_provider):
            opportunities = self.strategy(snapshot)
            for opportunity in opportunities:
                self.execution_engine.execute(opportunity)
                trades += 1
            self.risk_manager.settle_positions(snapshot.timestamp)
            self.max_open_positions = max(
                self.max_open_positions, len(self.risk_manager.positions)
            )
        self.risk_manager.settle_positions(float("inf"))
        avg_pnl = self.risk_manager.realized_pnl / trades if trades else 0.0
        return BacktestResult(
            total_pnl=self.risk_manager.realized_pnl,
            trades=trades,
            avg_pnl_per_trade=avg_pnl,
            max_open_positions=self.max_open_positions,
        )

    @staticmethod
    def _iter_snapshots(
        data_provider: Iterable[OrderBookSnapshot],
    ) -> Iterable[OrderBookSnapshot]:
        for snapshot in data_provider:
            yield snapshot


def build_default_backtester(
    data_provider: BaseMarketDataProvider,
    profit_threshold: float,
    fee_rate: float,
    max_positions: int,
    expiry_seconds: float,
) -> Backtester:
    risk_manager = BasicRiskManager(
        max_open_positions=max_positions,
        expiry_seconds=expiry_seconds,
    )
    strategy = SimpleArbitrageStrategy(
        profit_threshold=profit_threshold,
        fee_rate=fee_rate,
    )
    execution_engine = SimulationExecutionEngine(
        risk_manager=risk_manager,
        fee_rate=fee_rate,
    )
    return Backtester(
        data_provider=data_provider,
        strategy=strategy,
        execution_engine=execution_engine,
        risk_manager=risk_manager,
    )
