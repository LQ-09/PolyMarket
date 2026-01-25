"""Skeleton live trading runner (no real orders)."""

from __future__ import annotations

import time

from polymarket_arbitrage.data import RealTimeMarketDataProvider
from polymarket_arbitrage.execution import LiveExecutionEngine
from polymarket_arbitrage.strategy import SimpleArbitrageStrategy


def main() -> None:
    data_provider = RealTimeMarketDataProvider()
    strategy = SimpleArbitrageStrategy(profit_threshold=0.01, fee_rate=0.02)
    execution_engine = LiveExecutionEngine()

    print("Starting live trading skeleton. Press Ctrl+C to stop.")
    while True:
        try:
            for snapshot in data_provider:
                for opportunity in strategy(snapshot):
                    execution_engine.execute(opportunity)
        except NotImplementedError as exc:
            print(f"Data provider not implemented: {exc}")
        time.sleep(5)


if __name__ == "__main__":
    main()
