# Polymarket Arbitrage Data Collector

This package collects Polymarket CLOB order book data for later backtesting. It supports
REST snapshot polling and WebSocket market data collection, and stores snapshots in a
format compatible with the existing backtester data reader.

## Install

```bash
pip install -r requirements.txt
```

> ⚠️ 运行前请确保安装依赖（`tenacity`, `requests`, `websocket-client` 等），否则会报
> `ModuleNotFoundError: No module named 'tenacity'` 之类错误。

## REST snapshot collection

Collect periodic snapshots for an Up/Down pair and store them in the backtest-compatible
format (`timestamp`, `up`, `down`).

```powershell
python -m polymarket_arbitrage_collector.cli.collect `
  --mode rest `
  --series-slug btc-up-or-down-15m `
  --out data/ `
  --snapshot-every 1.0 `
  --depth 5 `
  --seconds 3600
```

> 说明：请在仓库根目录（包含 `polymarket_arbitrage_collector/` 的那一层）执行上述命令。
> 如果你已经 `cd polymarket_arbitrage_collector/`，请先设置：
> `PYTHONPATH=..` 再运行。

## Discover token IDs (no URL needed)

Use the default series slug (`btc-up-or-down-15m`) or pass `--market-slug` /
`--condition-id` to resolve token IDs without copying the event URL.

```powershell
python -m polymarket_arbitrage_collector.cli.collect `
  --mode discover
```

```powershell
python -m polymarket_arbitrage_collector.cli.collect `
  --mode discover `
  --series-slug btc-up-or-down-15m
```

> 输出目录默认是 `data/`，并自动按类型区分为：
> `data/snapshots/<series>/<market>/`（REST/WS 快照）、`data/raw_ws/<series>/<market>/`（WS 原始消息）、`data/history/<series>/<market>/`（历史价格）。

Output files:

```
out_dir/
  snapshots/<series>/<market>/YYYY-MM-DD/snapshots_<UP>_<DOWN>.jsonl
```

## WebSocket collection

Collect raw WebSocket messages and (optionally) periodic combined snapshots.

```powershell
python -m polymarket_arbitrage_collector.cli.collect `
  --mode ws `
  --series-slug btc-up-or-down-15m `
  --out data/ `
  --snapshot-every 1.0 `
  --depth 5
```

> 同上：建议在仓库根目录执行，或设置 `PYTHONPATH=..`。

Output files:

```
out_dir/
  raw_ws/<series>/<market>/YYYY-MM-DD/ws_<TOKEN_ID>.jsonl
  snapshots/<series>/<market>/YYYY-MM-DD/snapshots_<UP>_<DOWN>.jsonl
```

## Historical price collection (Gamma token discovery + price history)

If you only know a market slug or condition ID, you can resolve token IDs via Gamma and
download price history by time range. Note: this endpoint returns historical prices, not
full order book snapshots, so it is stored under `history/`.

```powershell
python -m polymarket_arbitrage_collector.cli.collect `
  --mode history `
  --series-slug btc-up-or-down-15m `
  --auto-window-minutes 15 `
  --fidelity-minutes 1 `
  --out data/
```

> 说明：`--series-slug` 默认使用 `btc-up-or-down-15m`，也可以传入 `--market-url`
> 或 `--condition-id` 覆盖。

## History batch (daily 15m markets)

Download all 15-minute markets for a given date (e.g. 96 markets for a full day).

```powershell
python -m polymarket_arbitrage_collector.cli.collect `
  --mode history-batch `
  --series-slug btc-up-or-down-15m `
  --history-date 2026-01-21 `
  --auto-window-minutes 15 `
  --fidelity-minutes 1 `
  --out data/
```

Output files:

```
out_dir/
  history/<series>/<market>/YYYY-MM-DD/history_<TOKEN_ID>.jsonl
```

## Stored snapshot schema (backtest-compatible)

Each snapshot line contains:

```json
{
  "timestamp": 1690000000.0,
  "up": {
    "bids": [[0.45, 100], [0.44, 200]],
    "asks": [[0.46, 100], [0.47, 200]]
  },
  "down": {
    "bids": [[0.53, 100], [0.52, 200]],
    "asks": [[0.54, 100], [0.55, 200]]
  },
  "token_id": "<UP>_<DOWN>"
}
```

The `token_id` field is appended to help with provenance but is ignored by the existing
backtest reader.
