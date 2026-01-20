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
  --market-url https://polymarket.com/event/btc-updown-15m-1768907700 `
  --out data/ `
  --snapshot-every 1.0 `
  --depth 5 `
  --seconds 3600
```

> 说明：请在仓库根目录（包含 `polymarket_arbitrage_collector/` 的那一层）执行上述命令。
> 如果你已经 `cd polymarket_arbitrage_collector/`，请先设置：
> `PYTHONPATH=..` 再运行。

Output files:

```
out_dir/
  snapshots/YYYY-MM-DD/snapshots_<UP>_<DOWN>.jsonl
```

## WebSocket collection

Collect raw WebSocket messages and (optionally) periodic combined snapshots.

```powershell
python -m polymarket_arbitrage_collector.cli.collect `
  --mode ws `
  --market-url https://polymarket.com/event/btc-updown-15m-1768907700 `
  --out data/ `
  --snapshot-every 1.0 `
  --depth 5
```

> 同上：建议在仓库根目录执行，或设置 `PYTHONPATH=..`。

Output files:

```
out_dir/
  raw_ws/YYYY-MM-DD/ws_<TOKEN_ID>.jsonl
  snapshots/YYYY-MM-DD/snapshots_<UP>_<DOWN>.jsonl
```

## Historical price collection (Gamma token discovery + price history)

If you only know a market slug or condition ID, you can resolve token IDs via Gamma and
download price history by time range. Note: this endpoint returns historical prices, not
full order book snapshots, so it is stored under `history/`.

```powershell
python -m polymarket_arbitrage_collector.cli.collect `
  --mode history `
  --market-url https://polymarket.com/event/btc-updown-15m-1768907700 `
  --start-ts 1710000000 `
  --end-ts 1710086400 `
  --fidelity-minutes 1 `
  --out data/
```

> 说明：`--market-slug` 默认使用 `btc-updown-15m-1768907700`，也可以传入 `--market-url`
> 或 `--condition-id` 覆盖。

Output files:

```
out_dir/
  history/YYYY-MM-DD/history_<TOKEN_ID>.jsonl
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
