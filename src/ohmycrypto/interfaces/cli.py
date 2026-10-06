"""Command line interface for OhMyCrypto.

Follows Section 4 and Section 12 of PROJECT_EXECUTION_GUIDE.md:
- Installed `ohmycrypto` entry point
- Subcommands for monitoring, verification, diagnostics, execution cost comparison, and replay
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
import os
import sys
import tempfile
from typing import Optional, Sequence

from ohmycrypto.domain.models import DecimalJSONEncoder, Instrument, FeeProfile, BookState, BookLevel
from ohmycrypto.domain.kernel import evaluate_cross_venue_opportunity


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ohmycrypto",
        description="OhMyCrypto: deterministic arbitrage verification, data quality diagnostics, and execution cost comparison.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # status subcommand
    subparsers.add_parser("status", help="Display system and database status")

    # verify subcommand
    verify_p = subparsers.add_parser("verify", help="Verify arbitrage opportunity deterministically")
    verify_p.add_argument("--symbol", default="BTC/USDT", help="Spot symbol (e.g. BTC/USDT)")
    verify_p.add_argument("--budget", required=True, type=str, help="All-in quote budget (e.g. 1000)")
    verify_p.add_argument("--buy-venue", default="coinbase", help="Buy venue")
    verify_p.add_argument("--sell-venue", default="kraken", help="Sell venue")
    verify_p.add_argument("--buy-price", required=True, type=str, help="Simulated buy ask price")
    verify_p.add_argument("--sell-price", required=True, type=str, help="Simulated sell bid price")
    verify_p.add_argument("--depth", default="1.0", type=str, help="Simulated available depth at top price")

    # compare subcommand
    compare_p = subparsers.add_parser("compare", help="Compare execution costs across venues")
    compare_p.add_argument("--symbol", default="BTC/USDT", help="Spot symbol")
    compare_p.add_argument("--amount", required=True, type=str, help="Quote budget or base amount")
    compare_p.add_argument("--side", choices=["buy", "sell"], default="buy", help="Side: buy or sell")

    # replay subcommand
    replay_p = subparsers.add_parser("replay", help="Replay stored or exported event bundle")
    replay_p.add_argument("--bundle", required=True, help="Path to replay bundle JSON file")

    # diagnostics subcommand
    diag_p = subparsers.add_parser("diagnostics", help="Diagnostic utilities and reproduction")
    diag_sub = diag_p.add_subparsers(dest="diag_action", required=True)
    reproduce_p = diag_sub.add_parser("reproduce", help="Reproduce incident bundle offline")
    reproduce_p.add_argument("--bundle", required=True, help="Path to incident bundle JSON file")

    return parser


def run_verify(args: argparse.Namespace) -> int:
    """Run deterministic opportunity verification."""
    budget = Decimal(args.budget)
    buy_price = Decimal(args.buy_price)
    sell_price = Decimal(args.sell_price)
    depth = Decimal(args.depth)

    inst = Instrument(
        symbol=args.symbol,
        base=args.symbol.split("/")[0],
        quote=args.symbol.split("/")[1],
        venue="generic",
        native_symbol=args.symbol,
    )
    buy_fee = FeeProfile(venue=args.buy_venue, taker_rate=Decimal("0.0025"))
    sell_fee = FeeProfile(venue=args.sell_venue, taker_rate=Decimal("0.0025"))

    buy_book = BookState(
        venue=args.buy_venue,
        symbol=args.symbol,
        bids=(),
        asks=(BookLevel(price=buy_price, amount=depth),),
        snapshot_origin="cli_synthetic",
        applied_sequence=1,
        source_time_ms=None,
        source_time_meaning="unknown",
        local_receipt_utc_ms=0,
        local_receipt_mono_ns=0,
    )
    sell_book = BookState(
        venue=args.sell_venue,
        symbol=args.symbol,
        bids=(BookLevel(price=sell_price, amount=depth),),
        asks=(),
        snapshot_origin="cli_synthetic",
        applied_sequence=1,
        source_time_ms=None,
        source_time_meaning="unknown",
        local_receipt_utc_ms=0,
        local_receipt_mono_ns=0,
    )

    res = evaluate_cross_venue_opportunity(
        symbol=args.symbol,
        buy_book=buy_book,
        sell_book=sell_book,
        all_in_quote_budget=budget,
        buy_fee_profile=buy_fee,
        sell_fee_profile=sell_fee,
        buy_instrument=inst,
        sell_instrument=inst,
    )

    output = {
        "symbol": res.symbol,
        "buy_venue": res.buy_venue,
        "sell_venue": res.sell_venue,
        "all_in_budget": str(res.budget_amount),
        "quote_spent": str(res.buy_fill.quote_spent),
        "buy_fee": str(res.buy_fill.fee_quote),
        "acquired_base": str(res.buy_fill.acquired_base),
        "net_quote_received": str(res.sell_fill.quote_received),
        "sell_fee": str(res.sell_fill.fee_quote),
        "net_profit_quote": str(res.net_profit_quote),
        "effective_spread": str(res.effective_spread),
        "is_positive": res.is_positive,
        "is_eligible": res.is_eligible,
        "eligibility_reasons": list(res.eligibility_reasons),
        "input_hash": res.input_hash,
    }
    sys.stdout.write(json.dumps(output, indent=2, cls=DecimalJSONEncoder) + "\n")
    return 0


def run_compare(args: argparse.Namespace) -> int:
    """Compare execution costs across venues."""
    amount = Decimal(args.amount)
    symbol = args.symbol
    side = args.side

    from ohmycrypto.services.cost import CostAdvisorService
    from ohmycrypto.storage.repository import StorageRepository
    from ohmycrypto.storage.db import create_connection
    from ohmycrypto.storage.migrations import run_migrations

    with tempfile.TemporaryDirectory() as tmpdir:
        conn = create_connection(os.path.join(tmpdir, "cli_cost.db"))
        run_migrations(conn)
        repo = StorageRepository(conn)
        advisor = CostAdvisorService(repo)

        # Synthesize baseline book depths if live feeds are not connected
        default_price = Decimal("85000")
        sample_bids = (BookLevel(price=default_price - Decimal("10"), amount=Decimal("5.0")),)
        sample_asks = (BookLevel(price=default_price + Decimal("10"), amount=Decimal("5.0")),)

        books = {
            "coinbase": BookState(
                venue="coinbase",
                symbol=symbol,
                bids=sample_bids,
                asks=sample_asks,
                snapshot_origin="cli_sample",
                applied_sequence=1,
                source_time_ms=None,
                source_time_meaning="unknown",
                local_receipt_utc_ms=0,
                local_receipt_mono_ns=0,
            ),
            "kraken": BookState(
                venue="kraken",
                symbol=symbol,
                bids=sample_bids,
                asks=sample_asks,
                snapshot_origin="cli_sample",
                applied_sequence=1,
                source_time_ms=None,
                source_time_meaning="unknown",
                local_receipt_utc_ms=0,
                local_receipt_mono_ns=0,
            ),
        }
        res = advisor.compare_single_venue(
            symbol=symbol,
            side=side,
            amount=amount,
            books=books,
        )
        sys.stdout.write(json.dumps(res, indent=2, cls=DecimalJSONEncoder) + "\n")
    return 0


def run_replay(args: argparse.Namespace) -> int:
    """Replay exported opportunity bundle deterministically."""
    if not os.path.exists(args.bundle):
        sys.stderr.write(f"Error: Replay bundle file not found: {args.bundle}\n")
        sys.exit(1)

    try:
        with open(args.bundle, "r", encoding="utf-8") as f:
            bundle = json.load(f)
    except Exception as err:
        sys.stderr.write(f"Error parsing replay bundle: {err}\n")
        sys.exit(1)

    from ohmycrypto.storage.repository import StorageRepository
    from ohmycrypto.storage.archives import ArchiveManager
    from ohmycrypto.storage.db import create_connection
    from ohmycrypto.storage.migrations import run_migrations
    from ohmycrypto.services.opportunity import OpportunityService

    with tempfile.TemporaryDirectory() as tmpdir:
        conn = create_connection(os.path.join(tmpdir, "cli_replay.db"))
        run_migrations(conn)
        repo = StorageRepository(conn)
        archives = ArchiveManager(tmpdir)
        opp_svc = OpportunityService(repo, archives)
        res = opp_svc.replay_bundle(bundle)
        sys.stdout.write(json.dumps(res, indent=2, cls=DecimalJSONEncoder) + "\n")
        return 0 if res.get("status") == "REPLAYED" else 1


def run_diagnostics(args: argparse.Namespace) -> int:
    """Run diagnostics offline reproduction."""
    if args.diag_action == "reproduce":
        if not os.path.exists(args.bundle):
            sys.stderr.write(f"Error: Incident bundle file not found: {args.bundle}\n")
            sys.exit(1)

        try:
            with open(args.bundle, "r", encoding="utf-8") as f:
                bundle = json.load(f)
        except Exception as err:
            sys.stderr.write(f"Error parsing incident bundle: {err}\n")
            sys.exit(1)

        from ohmycrypto.services.diagnostics import DiagnosticService
        res = DiagnosticService.reproduce_incident(bundle)
        sys.stdout.write(json.dumps(res, indent=2) + "\n")
        return 0 if res.get("status") == "REPRODUCED" else 1
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "status":
        sys.stdout.write(json.dumps({"status": "ready", "version": "1.0.0"}) + "\n")
        return 0
    elif args.subcommand == "verify":
        return run_verify(args)
    elif args.subcommand == "compare":
        return run_compare(args)
    elif args.subcommand == "replay":
        return run_replay(args)
    elif args.subcommand == "diagnostics":
        return run_diagnostics(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
