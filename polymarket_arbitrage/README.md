# Polymarket Arbitrage Backtest Framework

This project provides a simple, modular backtesting framework for Polymarket 15-minute
Up/Down binary option arbitrage. The focus is on microstructure and execution, not
predictive modeling.

## Project Structure

```
polymarket_arbitrage/
├── polymarket_arbitrage/
│   ├── __init__.py
│   ├── data.py
│   ├── strategy.py
│   ├── execution.py
│   ├── risk.py
│   └── backtest.py
├── scripts/
│   ├── backtest.py
│   └── live_trade.py
├── requirements.txt
└── README.md
```

## Data Format

Each snapshot must be a JSON object with the following format:

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
  }
}
```

A JSON file can either be a list of snapshots or a dictionary with a `data` key that
contains the list.

## Backtest CLI

```bash
python scripts/backtest.py \
  --data data/sample.json \
  --fee-rate 0.02 \
  --profit-threshold 0.01 \
  --max-positions 5 \
  --expiry-seconds 900
```

## Live Trading Skeleton

```bash
python scripts/live_trade.py
```

This runner only prints what would be executed. It does **not** connect to any live APIs.
