# Polymarket Order-Book & Execution Research

Maintained by [Ling Qi](https://github.com/LQ-09).

A research project for collecting binary-market order books and testing whether buying complementary Up/Down contracts is attractive after a simplified cost allowance. The focus is data reliability, transparent simulation, and the gap between an apparent price opportunity and an executable trade.

## Research design

- **Data:** REST book snapshots, WebSocket messages, token discovery through Gamma, and separate historical price downloads.
- **Signal:** compare the two best ask prices with a combined payout of 1, less a configured fee allowance and profit threshold.
- **Simulation:** immediately fill one unit of each leg and settle after a configurable holding period.
- **Controls:** cap concurrent open pairs; keep strategy, execution, data loading and position accounting in separate modules.

The collector and backtester are separate packages. Historical token prices do not reconstruct historical order-book depth.

## Run an offline example

Python 3.10+ is recommended for the collector's type syntax. The backtest core and the following synthetic example use only the standard library.

```sh
PYTHONPATH=polymarket_arbitrage python polymarket_arbitrage/scripts/backtest.py \
  --data examples/synthetic_snapshots.json --fee-rate 0.02 \
  --profit-threshold 0.01 --max-positions 1 --expiry-seconds 900
PYTHONPATH=polymarket_arbitrage python -m unittest discover -s tests -v
```

The example is invented, contains no market observations, and demonstrates accounting only. For collection setup, see [collector documentation](polymarket_arbitrage_collector/README.md). For input schema, see [backtester documentation](polymarket_arbitrage/README.md).

## Maintenance record

| Date | Change in the repository | Evidence |
| --- | --- | --- |
| 2026-01-20 | Added the paired-market backtest framework and collector | [backtest](https://github.com/LQ-09/PolyMarket/commit/c3a9bfbe09bf164d735d3d0abd19913fd462d6ff), [collector](https://github.com/LQ-09/PolyMarket/commit/29b0c1e72479ba2be7d2588bd9d90be76d0110c1) |
| 2026-01-20 | Fixed Gamma token-ID payload parsing | [change](https://github.com/LQ-09/PolyMarket/commit/9144423da4f60f91db5cb1b9d36ed238156e1696) |
| 2026-01-22 | Added daily batch history fetching | [change](https://github.com/LQ-09/PolyMarket/commit/e4516082ed05da0a69151785c5e5b0f6fb9fb12c) |
| 2026-01-25 | Documented Gamma response-shape handling | [change](https://github.com/LQ-09/PolyMarket/commit/68b8dd2dd34c61292e3bda73cd71e24156ff1c26) |

Development branches also contain a January 27 discovery change and a February 12 Gemini download script; they are not merged features of this default-branch project. These dated changes demonstrate iterations, not a claim of uninterrupted or scheduled maintenance.

## What has been verified

A local offline smoke checked that one eligible synthetic pair produces the expected modeled settlement and an ineligible pair is skipped. This validates only those small accounting paths. The collector normalization suite still needs its external dependencies in the review environment; no current API-connectivity or live-trading acceptance claim is made.

## Results and limits

No verified market return, Sharpe ratio, capacity or live execution quality is claimed. The live engine prints proposed actions and sends no orders.

The fee is a simplified per-pair input, not a calibrated exchange fee schedule. Immediate two-leg fills omit legging risk, queue priority, depth, partial fills, latency, cancellation and outages. Expiry is simulated as a fixed interval rather than verified market-resolution events. The trade counter counts accepted simulated pairs and excludes capacity rejections; these are modeled fills, not verified market executions.

## Next research steps

Add depth/size-aware fills and one-leg-failure cases; validate market-resolution and fee rules against the selected markets; test collector replay and the duplicated package layouts; compare execution assumptions on dated, permitted data. These are planned checks, not completed improvements.
