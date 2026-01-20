"""CLI for collecting Polymarket market data."""

from __future__ import annotations

import argparse
import signal
import time
from typing import Dict, List, Optional

from loguru import logger

from ..collectors.rest_book_snapshot import fetch_book_snapshot
from ..collectors.ws_market_book import MarketWSCollector
from ..storage.writers import JSONLWriter, build_snapshot_path, utc_date_string


def _parse_token_ids(raw: str) -> List[str]:
    return [token.strip() for token in raw.split(",") if token.strip()]


def _combine_snapshots(
    up_snapshot: Dict[str, object],
    down_snapshot: Dict[str, object],
) -> Dict[str, object]:
    timestamp = max(float(up_snapshot["ts"]), float(down_snapshot["ts"]))
    return {
        "timestamp": timestamp,
        "up": {"bids": up_snapshot["bids"], "asks": up_snapshot["asks"]},
        "down": {"bids": down_snapshot["bids"], "asks": down_snapshot["asks"]},
        "token_id": f"{up_snapshot['token_id']}_{down_snapshot['token_id']}",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Polymarket data collector")
    parser.add_argument("--token-ids", help="Comma-separated token IDs")
    parser.add_argument("--up-token-id", help="Token ID for Up contract")
    parser.add_argument("--down-token-id", help="Token ID for Down contract")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--mode", choices=["rest", "ws"], required=True)
    parser.add_argument("--seconds", type=float, default=0.0)
    parser.add_argument("--snapshot-every", type=float, default=1.0)
    parser.add_argument("--ping-interval", type=float, default=5.0)
    return parser.parse_args()


def _resolve_side_map(args: argparse.Namespace) -> Dict[str, str]:
    if args.up_token_id and args.down_token_id:
        return {args.up_token_id: "up", args.down_token_id: "down"}
    return {}


def _resolve_token_ids(args: argparse.Namespace) -> List[str]:
    if args.token_ids:
        return _parse_token_ids(args.token_ids)
    if args.up_token_id and args.down_token_id:
        return [args.up_token_id, args.down_token_id]
    raise ValueError("Must provide --token-ids or --up-token-id/--down-token-id")


def _run_rest(args: argparse.Namespace) -> None:
    if not args.up_token_id or not args.down_token_id:
        raise ValueError("REST mode requires --up-token-id and --down-token-id")
    writer = JSONLWriter(
        build_snapshot_path(
            args.out, f"{args.up_token_id}_{args.down_token_id}", utc_date_string()
        )
    )
    stop_at = time.time() + args.seconds if args.seconds else None
    while stop_at is None or time.time() < stop_at:
        up_snapshot = fetch_book_snapshot(args.up_token_id)
        down_snapshot = fetch_book_snapshot(args.down_token_id)
        combined = _combine_snapshots(up_snapshot, down_snapshot)
        writer.write(combined)
        time.sleep(args.snapshot_every)


def _run_ws(args: argparse.Namespace) -> None:
    token_ids = _resolve_token_ids(args)
    side_map = _resolve_side_map(args)
    collector = MarketWSCollector(
        token_ids=token_ids,
        out_dir=args.out,
        snapshot_every=args.snapshot_every,
        ping_interval=args.ping_interval,
        side_map=side_map,
    )

    def _handle_sigint(signum: int, frame: Optional[object]) -> None:
        logger.info("Stopping collector")
        collector.stop()

    signal.signal(signal.SIGINT, _handle_sigint)
    if args.seconds:
        signal.signal(signal.SIGALRM, _handle_sigint)
        signal.alarm(int(args.seconds))
    collector.connect()


def main() -> None:
    args = parse_args()
    if args.mode == "rest":
        _run_rest(args)
    else:
        _run_ws(args)


if __name__ == "__main__":
    main()
