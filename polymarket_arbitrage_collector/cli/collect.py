"""CLI for collecting Polymarket market data."""

from __future__ import annotations

import argparse
import signal
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from loguru import logger
import requests

from ..collectors.market_discovery import (
    DEFAULT_MARKET_SLUG,
    DEFAULT_SERIES_SLUG,
    list_series_markets,
    resolve_token_ids,
    resolve_latest_series_market,
    resolve_market_window_seconds,
    slug_from_market_url,
)
from ..collectors.rest_book_snapshot import fetch_book_snapshot
from ..collectors.ws_market_book import MarketWSCollector
from ..storage.writers import (
    JSONLWriter,
    build_history_path,
    build_snapshot_path,
    utc_date_string,
)


def _parse_token_ids(raw: str) -> List[str]:
    return [token.strip() for token in raw.split(",") if token.strip()]


def _trim_levels(
    levels: List[List[float]],
    side: str,
    depth: Optional[int],
) -> List[List[float]]:
    if depth is None:
        return levels
    if side == "bids":
        sorted_levels = sorted(levels, key=lambda x: x[0], reverse=True)
    else:
        sorted_levels = sorted(levels, key=lambda x: x[0])
    return sorted_levels[:depth]


def _combine_snapshots(
    up_snapshot: Dict[str, object],
    down_snapshot: Dict[str, object],
    depth: Optional[int],
) -> Dict[str, object]:
    timestamp = max(float(up_snapshot["ts"]), float(down_snapshot["ts"]))
    return {
        "timestamp": timestamp,
        "up": {
            "bids": _trim_levels(up_snapshot["bids"], "bids", depth),
            "asks": _trim_levels(up_snapshot["asks"], "asks", depth),
        },
        "down": {
            "bids": _trim_levels(down_snapshot["bids"], "bids", depth),
            "asks": _trim_levels(down_snapshot["asks"], "asks", depth),
        },
        "token_id": f"{up_snapshot['token_id']}_{down_snapshot['token_id']}",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Polymarket data collector")
    parser.add_argument("--token-ids", help="Comma-separated token IDs")
    parser.add_argument("--up-token-id", help="Token ID for Up contract")
    parser.add_argument("--down-token-id", help="Token ID for Down contract")
    parser.add_argument(
        "--market-slug",
        default=DEFAULT_MARKET_SLUG,
        help="Gamma market slug for token discovery",
    )
    parser.add_argument("--condition-id", help="Gamma condition ID for token discovery")
    parser.add_argument("--market-url", help="Polymarket event URL for token discovery")
    parser.add_argument(
        "--series-slug",
        default=DEFAULT_SERIES_SLUG,
        help="Gamma series slug for auto-latest market discovery",
    )
    parser.add_argument("--out", default="data", help="Output directory")
    parser.add_argument(
        "--mode",
        choices=["rest", "ws", "history", "history-batch", "discover"],
        required=True,
    )
    parser.add_argument("--seconds", type=float, default=0.0)
    parser.add_argument("--snapshot-every", type=float, default=1.0)
    parser.add_argument("--ping-interval", type=float, default=5.0)
    parser.add_argument("--depth", type=int, default=5, help="Orderbook depth to store")
    parser.add_argument(
        "--auto-window-minutes",
        type=int,
        default=15,
        help="Auto window size for history when not providing start/end",
    )
    parser.add_argument("--start-ts", type=float, help="History start timestamp (epoch)")
    parser.add_argument("--end-ts", type=float, help="History end timestamp (epoch)")
    parser.add_argument(
        "--history-date",
        help="History date (YYYY-MM-DD) for batch series download",
    )
    parser.add_argument(
        "--history-days-ago",
        type=int,
        help="History days ago (UTC) for batch series download",
    )
    parser.add_argument(
        "--fidelity-minutes",
        type=int,
        default=1,
        help="History resolution in minutes",
    )
    return parser.parse_args()


def _resolve_side_map(args: argparse.Namespace) -> Dict[str, str]:
    resolution, _ = _resolve_market_context(args)
    if resolution.up_token_id and resolution.down_token_id:
        return {resolution.up_token_id: "up", resolution.down_token_id: "down"}
    return {}


def _resolve_token_ids(args: argparse.Namespace) -> List[str]:
    if args.token_ids:
        return _parse_token_ids(args.token_ids)
    if args.up_token_id and args.down_token_id:
        return [args.up_token_id, args.down_token_id]
    resolution, _ = _resolve_market_context(args)
    if resolution.all_token_ids:
        return resolution.all_token_ids
    raise ValueError("Must provide --token-ids or --up-token-id/--down-token-id")


def _resolve_market_context(
    args: argparse.Namespace,
) -> Tuple["TokenResolution", str]:
    if args.market_url:
        slug = slug_from_market_url(args.market_url)
        resolution = resolve_token_ids(market_slug=slug)
        return resolution, slug
    if args.market_slug or args.condition_id:
        resolution = resolve_token_ids(
            market_slug=args.market_slug,
            condition_id=args.condition_id,
        )
        slug = args.market_slug or resolution.raw.get("slug", "unknown-market")
        return resolution, slug
    resolution = resolve_latest_series_market(series_slug=args.series_slug)
    slug = resolution.raw.get("slug", "unknown-market")
    return resolution, slug


def _run_rest(args: argparse.Namespace) -> None:
    side_map = _resolve_side_map(args)
    if not side_map:
        raise ValueError("REST mode requires Up/Down token IDs or market discovery info")
    up_token_id = next(token for token, side in side_map.items() if side == "up")
    down_token_id = next(token for token, side in side_map.items() if side == "down")
    resolution, market_slug = _resolve_market_context(args)
    writer = JSONLWriter(
        build_snapshot_path(
            args.out,
            f"{up_token_id}_{down_token_id}",
            utc_date_string(),
            series_slug=args.series_slug,
            market_slug=market_slug,
        )
    )
    stop_at = time.time() + args.seconds if args.seconds else None
    while stop_at is None or time.time() < stop_at:
        up_snapshot = fetch_book_snapshot(up_token_id)
        down_snapshot = fetch_book_snapshot(down_token_id)
        combined = _combine_snapshots(up_snapshot, down_snapshot, args.depth)
        writer.write(combined)
        time.sleep(args.snapshot_every)


def _run_ws(args: argparse.Namespace) -> None:
    token_ids = _resolve_token_ids(args)
    side_map = _resolve_side_map(args)
    resolution, market_slug = _resolve_market_context(args)
    collector = MarketWSCollector(
        token_ids=token_ids,
        out_dir=args.out,
        snapshot_every=args.snapshot_every,
        depth=args.depth,
        ping_interval=args.ping_interval,
        side_map=side_map,
        series_slug=args.series_slug,
        market_slug=market_slug,
    )

    def _handle_sigint(signum: int, frame: Optional[object]) -> None:
        logger.info("Stopping collector")
        collector.stop()

    signal.signal(signal.SIGINT, _handle_sigint)
    if args.seconds:
        signal.signal(signal.SIGALRM, _handle_sigint)
        signal.alarm(int(args.seconds))
    collector.connect()


def _fetch_price_history(
    token_id: str,
    start_ts: float,
    end_ts: float,
    fidelity_minutes: int,
) -> Dict[str, object]:
    url = "https://clob.polymarket.com/prices-history"
    response = requests.get(
        url,
        params={
            "market": token_id,
            "startTs": int(start_ts),
            "endTs": int(end_ts),
            "fidelity": int(fidelity_minutes),
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return {
        "token_id": token_id,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "fidelity_minutes": fidelity_minutes,
        "data": response.json(),
    }


def _run_history(args: argparse.Namespace) -> None:
    resolution, market_slug = _resolve_market_context(args)
    start_ts = args.start_ts
    end_ts = args.end_ts
    if start_ts is None or end_ts is None:
        auto_start, auto_end = resolve_market_window_seconds(
            resolution.raw, fallback_minutes=args.auto_window_minutes
        )
        start_ts = start_ts or auto_start
        end_ts = end_ts or auto_end
    if start_ts is None or end_ts is None:
        raise ValueError("--start-ts/--end-ts required or auto window unavailable")
    token_ids = _resolve_token_ids(args)
    for token_id in token_ids:
        writer = JSONLWriter(
            build_history_path(
                args.out,
                token_id,
                utc_date_string(),
                series_slug=args.series_slug,
                market_slug=market_slug,
            )
        )
        payload = _fetch_price_history(
            token_id=token_id,
            start_ts=start_ts,
            end_ts=end_ts,
            fidelity_minutes=args.fidelity_minutes,
        )
        writer.write(payload)


def _run_discover(args: argparse.Namespace) -> None:
    resolution, market_slug = _resolve_market_context(args)
    print("Resolved token IDs")
    print(f"Up: {resolution.up_token_id}")
    print(f"Down: {resolution.down_token_id}")
    print(f"Market: {market_slug}")


def _run_history_batch(args: argparse.Namespace) -> None:
    history_date = args.history_date
    if not history_date and args.history_days_ago is not None:
        target_date = datetime.now(timezone.utc) - timedelta(days=args.history_days_ago)
        history_date = target_date.strftime("%Y-%m-%d")
    if not history_date:
        raise ValueError(
            "--history-date or --history-days-ago is required for history-batch mode"
        )
    markets = list_series_markets(
        series_slug=args.series_slug, date_iso=history_date
    )
    if not markets:
        raise ValueError("No markets found for the provided history date")
    for market in markets:
        market_slug = market.get("slug", "unknown-market")
        tokens = resolve_token_ids(market_slug=market_slug)
        if not tokens.all_token_ids:
            continue
        start_ts, end_ts = resolve_market_window_seconds(
            market, fallback_minutes=args.auto_window_minutes
        )
        if start_ts is None or end_ts is None:
            continue
        for token_id in tokens.all_token_ids:
            writer = JSONLWriter(
                build_history_path(
                    args.out,
                    token_id,
                    utc_date_string(),
                    series_slug=args.series_slug,
                    market_slug=market_slug,
                )
            )
            payload = _fetch_price_history(
                token_id=token_id,
                start_ts=start_ts,
                end_ts=end_ts,
                fidelity_minutes=args.fidelity_minutes,
            )
            writer.write(payload)


def main() -> None:
    args = parse_args()
    if args.mode != "discover" and not args.out:
        raise ValueError("--out is required for rest/ws/history modes")
    if args.mode == "rest":
        _run_rest(args)
    elif args.mode == "ws":
        _run_ws(args)
    elif args.mode == "discover":
        _run_discover(args)
    elif args.mode == "history-batch":
        _run_history_batch(args)
    else:
        _run_history(args)


if __name__ == "__main__":
    main()
