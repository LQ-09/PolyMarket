from polymarket_arbitrage_collector.collectors.rest_book_snapshot import normalize_book_snapshot
from polymarket_arbitrage_collector.cli.collect import _combine_snapshots


def test_normalize_book_snapshot_basic() -> None:
    raw = {
        "timestamp": 123.0,
        "bids": [[0.4, 10], [0.39, 5]],
        "asks": [[0.6, 8]],
        "tick_size": 0.01,
        "min_order_size": 1,
    }
    result = normalize_book_snapshot(raw, "token123")
    assert result["ts"] == 123.0
    assert result["token_id"] == "token123"
    assert result["bids"][0] == [0.4, 10.0]
    assert result["asks"][0] == [0.6, 8.0]


def test_combine_snapshots_shape() -> None:
    up = {
        "ts": 10.0,
        "token_id": "up",
        "bids": [[0.4, 1.0]],
        "asks": [[0.6, 1.0]],
    }
    down = {
        "ts": 12.0,
        "token_id": "down",
        "bids": [[0.3, 1.0]],
        "asks": [[0.7, 1.0]],
    }
    combined = _combine_snapshots(up, down)
    assert combined["timestamp"] == 12.0
    assert combined["up"]["bids"][0] == [0.4, 1.0]
    assert combined["down"]["asks"][0] == [0.7, 1.0]
