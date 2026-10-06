import argparse
import asyncio
import json
import logging
import re
import time

from config import (
    DEFAULT_ALERT_COOLDOWN_SEC,
    DEFAULT_ALERT_PRICE_CHANGE_RATIO,
    DEFAULT_EXCHANGES,
    DEFAULT_FEE_RATE,
    DEFAULT_MAX_CONSECUTIVE_ERRORS,
    DEFAULT_MIN_PROFIT_USD,
    DEFAULT_MIN_SPREAD,
    DEFAULT_ORDERBOOK_DEPTH_LIMIT,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_STALE_PRICE_MS,
    DEFAULT_SYMBOL,
    DEFAULT_TIMEOUT,
    DEFAULT_TRADE_SIZE,
    PROJECT_NAME,
)
from market import (
    build_exchanges,
    close_exchanges,
    fetch_prices,
    initialize_exchange_health,
    update_exchange_health,
    validate_exchange_names,
)
from strategy import (
    build_alert_decision,
    build_notification_payload,
    filter_fresh_prices,
    record_alert,
    scan_spread_candidates,
    validate_candidate_with_orderbook,
)

import notifier


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def parse_args():
    parser = argparse.ArgumentParser(prog=PROJECT_NAME)
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--exchanges", default=",".join(DEFAULT_EXCHANGES))
    parser.add_argument("--interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--min-spread", type=float, default=DEFAULT_MIN_SPREAD)
    parser.add_argument("--trade-size", type=float, default=DEFAULT_TRADE_SIZE)
    parser.add_argument("--min-profit", type=float, default=DEFAULT_MIN_PROFIT_USD)
    parser.add_argument("--fee-rate", type=float, default=DEFAULT_FEE_RATE)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument(
        "--alert-cooldown",
        type=float,
        default=DEFAULT_ALERT_COOLDOWN_SEC,
    )
    parser.add_argument("--stale-ms", type=int, default=DEFAULT_STALE_PRICE_MS)
    parser.add_argument(
        "--orderbook-limit",
        type=int,
        default=DEFAULT_ORDERBOOK_DEPTH_LIMIT,
    )
    parser.add_argument(
        "--max-errors",
        type=int,
        default=DEFAULT_MAX_CONSECUTIVE_ERRORS,
    )
    parser.add_argument(
        "--alert-price-change-ratio",
        type=float,
        default=DEFAULT_ALERT_PRICE_CHANGE_RATIO,
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def validate_runtime_args(args):
    exchanges = [item.strip() for item in args.exchanges.split(",") if item.strip()]
    if not exchanges:
        raise ValueError("At least one exchange must be provided")

    invalid = validate_exchange_names(exchanges)
    if invalid:
        raise ValueError(f"Unsupported exchanges: {', '.join(sorted(invalid))}")

    if not re.fullmatch(r"[^/\s]+/[^/\s]+", args.symbol):
        raise ValueError(
            "Symbol must look like BASE/QUOTE, for example BTC/USDT"
        )

    numeric_checks = {
        "interval": args.interval,
        "min_spread": args.min_spread,
        "trade_size": args.trade_size,
        "min_profit": args.min_profit,
        "fee_rate": args.fee_rate,
        "timeout": args.timeout,
        "top": args.top,
        "alert_cooldown": args.alert_cooldown,
        "stale_ms": args.stale_ms,
        "orderbook_limit": args.orderbook_limit,
        "max_errors": args.max_errors,
    }
    for name, value in numeric_checks.items():
        if value <= 0:
            raise ValueError(f"{name} must be greater than zero")

    if args.alert_price_change_ratio < 0:
        raise ValueError("alert_price_change_ratio must be non-negative")

    return exchanges


def log_event(event, **fields):
    payload = {"event": event, **fields}
    logging.info(json.dumps(payload, sort_keys=True, default=str))


async def schedule_notification(notification_tasks, payload):
    task = asyncio.create_task(asyncio.to_thread(notifier.notify_opportunity, payload))
    notification_tasks.add(task)
    task.add_done_callback(notification_tasks.discard)


async def main_loop():
    configure_logging()
    args = parse_args()
    exchanges_list = validate_runtime_args(args)

    log_event(
        "startup",
        project=PROJECT_NAME,
        symbol=args.symbol,
        exchanges=exchanges_list,
        interval=args.interval,
        min_spread=args.min_spread,
        min_profit=args.min_profit,
        quiet=args.quiet,
    )

    clients = build_exchanges(exchanges_list, args.timeout)
    exchange_health = initialize_exchange_health(exchanges_list)
    alert_state = {}
    notification_tasks = set()
    cycle = 0
    last_alert = None

    try:
        while True:
            cycle += 1
            cycle_started = time.monotonic()

            prices, fetch_results = await fetch_prices(clients, args.symbol)
            update_exchange_health(
                exchange_health,
                fetch_results,
                args.max_errors,
            )

            fresh_prices, rejected_quotes = filter_fresh_prices(
                prices,
                args.stale_ms,
            )
            degraded_exchanges = sorted(
                name
                for name, state in exchange_health.items()
                if state["degraded"]
            )

            candidates = []
            validated_opportunities = []
            best_opportunity = None

            if len(fresh_prices) >= 2:
                candidates = scan_spread_candidates(fresh_prices, args.fee_rate)
                top_candidates = [
                    item for item in candidates if item["net_spread"] >= args.min_spread
                ][: args.top]

                for candidate in top_candidates:
                    opportunity = await validate_candidate_with_orderbook(
                        clients,
                        args.symbol,
                        candidate,
                        args.trade_size,
                        args.orderbook_limit,
                        args.fee_rate,
                    )
                    if opportunity is None:
                        continue
                    if opportunity["effective_spread"] < args.min_spread:
                        continue
                    validated_opportunities.append(opportunity)

                if validated_opportunities:
                    best_opportunity = max(
                        validated_opportunities,
                        key=lambda item: item["estimated_profit"],
                    )

            if best_opportunity is not None:
                decision = build_alert_decision(
                    best_opportunity,
                    alert_state,
                    args.alert_cooldown,
                    args.min_profit,
                    args.alert_price_change_ratio,
                )

                log_event(
                    "opportunity",
                    cycle=cycle,
                    symbol=best_opportunity["symbol"],
                    buy_exchange=best_opportunity["buy_exchange"],
                    sell_exchange=best_opportunity["sell_exchange"],
                    estimated_profit=round(best_opportunity["estimated_profit"], 4),
                    effective_spread=round(best_opportunity["effective_spread"], 6),
                    severity=decision["severity"],
                    should_notify=decision["should_notify"],
                    reason=decision["reason"],
                )

                if decision["should_notify"]:
                    record_alert(
                        alert_state,
                        best_opportunity,
                        decision["fingerprint"],
                        decision["severity"],
                    )
                    payload = build_notification_payload(
                        best_opportunity,
                        decision["severity"],
                    )
                    last_alert = {
                        "buy_exchange": payload["buy_exchange"],
                        "sell_exchange": payload["sell_exchange"],
                        "estimated_profit": round(payload["estimated_profit"], 4),
                        "severity": payload["severity"],
                    }
                    if not args.quiet:
                        await schedule_notification(notification_tasks, payload)

            cycle_ms = round((time.monotonic() - cycle_started) * 1000, 2)
            failed_exchanges = sorted(
                result["name"] for result in fetch_results if result["error"] is not None
            )
            error_details = {
                result["name"]: result["error"]
                for result in fetch_results
                if result["error"] is not None
            }

            log_event(
                "cycle_summary",
                cycle=cycle,
                successful_exchanges=len(prices),
                fresh_exchanges=len(fresh_prices),
                rejected_quotes=rejected_quotes,
                failed_exchanges=failed_exchanges,
                error_details=error_details,
                degraded_exchanges=degraded_exchanges,
                candidate_count=len(candidates),
                validated_count=len(validated_opportunities),
                cycle_ms=cycle_ms,
                last_alert=last_alert,
            )

            await asyncio.sleep(args.interval)

    except KeyboardInterrupt:
        log_event("shutdown_requested", reason="keyboard_interrupt")
    finally:
        if notification_tasks:
            await asyncio.gather(*notification_tasks, return_exceptions=True)
        await close_exchanges(clients)
        log_event("shutdown_complete")


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        log_event("fatal_error", error=f"{type(exc).__name__}: {exc}")
        raise
