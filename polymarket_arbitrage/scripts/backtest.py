"""CLI entrypoint for backtesting."""

from __future__ import annotations

import argparse

from polymarket_arbitrage.backtest import build_default_backtester
from polymarket_arbitrage.data import JsonMarketDataProvider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Polymarket arbitrage backtest")
    parser.add_argument("--data", required=True, help="Path to JSON/CSV data file")
    parser.add_argument("--fee-rate", type=float, default=0.02)
    parser.add_argument("--profit-threshold", type=float, default=0.01)
    parser.add_argument("--max-positions", type=int, default=5)
    parser.add_argument("--expiry-seconds", type=float, default=900)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_provider = JsonMarketDataProvider(args.data)
    backtester = build_default_backtester(
        data_provider=data_provider,
        profit_threshold=args.profit_threshold,
        fee_rate=args.fee_rate,
        max_positions=args.max_positions,
        expiry_seconds=args.expiry_seconds,
    )
    result = backtester.run()
    print("Backtest Summary")
    print(f"Total PnL: {result.total_pnl:.6f}")
    print(f"Trades: {result.trades}")
    print(f"Avg PnL/Trade: {result.avg_pnl_per_trade:.6f}")
    print(f"Max Open Positions: {result.max_open_positions}")


if __name__ == "__main__":
    main()
