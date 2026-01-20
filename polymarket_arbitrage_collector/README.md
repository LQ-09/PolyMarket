# Polymarket Arbitrage Data Collector

This package collects Polymarket CLOB order book data for later backtesting. It supports
REST snapshot polling and WebSocket market data collection, and stores snapshots in a
format compatible with the existing backtester data reader.

## Install

```bash
pip install -r requirements.txt
```

## REST snapshot collection

Collect periodic snapshots for an Up/Down pair and store them in the backtest-compatible
format (`timestamp`, `up`, `down`).

```bash
python -m polymarket_arbitrage_collector.cli.collect \
  --mode rest \
  --up-token-id <UP_TOKEN_ID> \
  --down-token-id <DOWN_TOKEN_ID> \
  --out data/ \
  --snapshot-every 1.0 \
  --seconds 3600
```

Output files:

```
out_dir/
  snapshots/YYYY-MM-DD/snapshots_<UP>_<DOWN>.jsonl
```

## WebSocket collection

Collect raw WebSocket messages and (optionally) periodic combined snapshots.

```bash
python -m polymarket_arbitrage_collector.cli.collect \
  --mode ws \
  --token-ids <UP_TOKEN_ID>,<DOWN_TOKEN_ID> \
  --up-token-id <UP_TOKEN_ID> \
  --down-token-id <DOWN_TOKEN_ID> \
  --out data/ \
  --snapshot-every 1.0
```

Output files:

```
out_dir/
  raw_ws/YYYY-MM-DD/ws_<TOKEN_ID>.jsonl
  snapshots/YYYY-MM-DD/snapshots_<UP>_<DOWN>.jsonl
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
