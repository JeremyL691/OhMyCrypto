import math
import time

from market import fetch_orderbooks_for_candidate


def filter_fresh_prices(prices, stale_ms, now_ms=None):
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    fresh_prices = {}
    rejected = {}

    for name, price in prices.items():
        reason = _quote_rejection_reason(price, stale_ms, now_ms)
        if reason is None:
            fresh_prices[name] = price
        else:
            rejected[name] = reason

    return fresh_prices, rejected


def scan_spread_candidates(prices, fee_rate):
    candidates = []
    names = list(prices.keys())

    for buy in names:
        for sell in names:
            if buy == sell:
                continue

            buy_price = prices[buy]["ask"]
            sell_price = prices[sell]["bid"]
            spread = (sell_price - buy_price) / buy_price
            net_spread = spread - (2 * fee_rate)

            candidates.append({
                "buy_exchange": buy,
                "sell_exchange": sell,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "spread": spread,
                "net_spread": net_spread,
            })

    candidates.sort(key=lambda item: item["net_spread"], reverse=True)
    return candidates


async def validate_candidate_with_orderbook(
    clients,
    symbol,
    candidate,
    trade_size,
    orderbook_limit,
    fee_rate,
):
    books, errors = await fetch_orderbooks_for_candidate(
        clients,
        symbol,
        candidate,
        orderbook_limit,
    )
    if errors:
        return None

    buy_book = books[candidate["buy_exchange"]]
    sell_book = books[candidate["sell_exchange"]]

    buy_fill = _estimate_buy_fill(buy_book.get("asks", []), trade_size)
    if buy_fill is None:
        return None

    sell_fill = _estimate_sell_fill(sell_book.get("bids", []), buy_fill["base_amount"])
    if sell_fill is None:
        return None

    quote_spent_after_fees = buy_fill["quote_spent"] * (1 + fee_rate)
    quote_received_after_fees = sell_fill["quote_received"] * (1 - fee_rate)
    estimated_profit = quote_received_after_fees - quote_spent_after_fees
    effective_spread = estimated_profit / trade_size

    midpoint = (buy_fill["avg_price"] + sell_fill["avg_price"]) / 2

    return {
        "symbol": symbol,
        "buy_exchange": candidate["buy_exchange"],
        "sell_exchange": candidate["sell_exchange"],
        "candidate_net_spread": candidate["net_spread"],
        "buy_price": candidate["buy_price"],
        "sell_price": candidate["sell_price"],
        "avg_buy_price": buy_fill["avg_price"],
        "avg_sell_price": sell_fill["avg_price"],
        "base_amount": buy_fill["base_amount"],
        "quote_spent": buy_fill["quote_spent"],
        "quote_received": sell_fill["quote_received"],
        "quote_spent_after_fees": quote_spent_after_fees,
        "quote_received_after_fees": quote_received_after_fees,
        "estimated_profit": estimated_profit,
        "effective_spread": effective_spread,
        "midpoint_price": midpoint,
    }


def build_alert_decision(
    opportunity,
    alert_state,
    cooldown_sec,
    min_profit,
    alert_price_change_ratio,
    now=None,
):
    now = now if now is not None else time.time()
    fingerprint = build_opportunity_fingerprint(opportunity)

    if opportunity["estimated_profit"] < min_profit:
        return {
            "should_notify": False,
            "severity": "info",
            "fingerprint": fingerprint,
            "reason": "profit_below_threshold",
        }

    previous = alert_state.get(fingerprint)
    if previous is None:
        return {
            "should_notify": True,
            "severity": "alert",
            "fingerprint": fingerprint,
            "reason": "new_opportunity",
        }

    elapsed = now - previous["last_alert_at"]
    improved = _has_significant_improvement(
        opportunity,
        previous,
        alert_price_change_ratio,
    )

    if elapsed >= cooldown_sec:
        return {
            "should_notify": True,
            "severity": "alert",
            "fingerprint": fingerprint,
            "reason": "cooldown_elapsed",
        }

    if improved:
        return {
            "should_notify": True,
            "severity": "escalated",
            "fingerprint": fingerprint,
            "reason": "opportunity_improved",
        }

    return {
        "should_notify": False,
        "severity": "info",
        "fingerprint": fingerprint,
        "reason": "cooldown_active",
    }


def should_alert(
    opportunity,
    alert_state,
    cooldown_sec,
    min_profit,
    alert_price_change_ratio=0.15,
    now=None,
):
    decision = build_alert_decision(
        opportunity,
        alert_state,
        cooldown_sec,
        min_profit,
        alert_price_change_ratio,
        now=now,
    )
    return decision["should_notify"]


def record_alert(alert_state, opportunity, fingerprint, severity, now=None):
    now = now if now is not None else time.time()
    alert_state[fingerprint] = {
        "last_alert_at": now,
        "last_profit": opportunity["estimated_profit"],
        "last_spread": opportunity["effective_spread"],
        "last_midpoint_price": opportunity["midpoint_price"],
        "last_severity": severity,
    }


def build_notification_payload(opportunity, severity):
    payload = dict(opportunity)
    payload["severity"] = severity
    return payload


def _quote_rejection_reason(price, stale_ms, now_ms):
    bid = price.get("bid")
    ask = price.get("ask")
    last = price.get("last")
    timestamp = price.get("timestamp")
    fetched_at_ms = price.get("fetched_at_ms")

    if bid is None or ask is None or last is None:
        return "missing_quote_fields"
    if bid <= 0 or ask <= 0 or last <= 0:
        return "non_positive_price"
    if ask < bid:
        return "crossed_quote"
    reference_timestamp = fetched_at_ms if fetched_at_ms is not None else timestamp
    if reference_timestamp is None:
        return "missing_timestamp"
    if (now_ms - reference_timestamp) > stale_ms:
        return "stale_quote"
    return None


def _estimate_buy_fill(asks, quote_budget):
    remaining_quote = quote_budget
    acquired_base = 0.0
    quote_spent = 0.0

    for level in asks:
        if len(level) < 2:
            continue
        price, amount = level[0], level[1]
        if price is None or amount is None or price <= 0 or amount <= 0:
            continue

        level_quote = price * amount
        spend_here = min(level_quote, remaining_quote)
        base_here = spend_here / price
        acquired_base += base_here
        quote_spent += spend_here
        remaining_quote -= spend_here

        if math.isclose(remaining_quote, 0.0, abs_tol=1e-9):
            remaining_quote = 0.0
            break

    if remaining_quote > 1e-9 or acquired_base <= 0:
        return None

    return {
        "base_amount": acquired_base,
        "quote_spent": quote_spent,
        "avg_price": quote_spent / acquired_base,
    }


def _estimate_sell_fill(bids, base_amount):
    remaining_base = base_amount
    quote_received = 0.0
    sold_base = 0.0

    for level in bids:
        if len(level) < 2:
            continue
        price, amount = level[0], level[1]
        if price is None or amount is None or price <= 0 or amount <= 0:
            continue

        base_here = min(amount, remaining_base)
        sold_base += base_here
        quote_received += base_here * price
        remaining_base -= base_here

        if math.isclose(remaining_base, 0.0, abs_tol=1e-9):
            remaining_base = 0.0
            break

    if remaining_base > 1e-9 or sold_base <= 0:
        return None

    return {
        "base_amount": sold_base,
        "quote_received": quote_received,
        "avg_price": quote_received / sold_base,
    }


def _has_significant_improvement(opportunity, previous, threshold_ratio):
    profit_baseline = max(abs(previous["last_profit"]), 1e-9)
    spread_baseline = max(abs(previous["last_spread"]), 1e-9)
    price_baseline = max(abs(previous["last_midpoint_price"]), 1e-9)

    profit_ratio = (
        opportunity["estimated_profit"] - previous["last_profit"]
    ) / profit_baseline
    spread_ratio = (
        opportunity["effective_spread"] - previous["last_spread"]
    ) / spread_baseline
    price_ratio = abs(
        opportunity["midpoint_price"] - previous["last_midpoint_price"]
    ) / price_baseline

    return (
        profit_ratio >= threshold_ratio
        or spread_ratio >= threshold_ratio
        or price_ratio >= threshold_ratio
    )


def build_opportunity_fingerprint(opportunity):
    bucket = _price_bucket(opportunity["midpoint_price"])
    return (
        f"{opportunity['buy_exchange']}|"
        f"{opportunity['sell_exchange']}|"
        f"{opportunity['symbol']}|"
        f"{bucket}"
    )


def _price_bucket(price):
    if price >= 1000:
        return round(price, 1)
    if price >= 100:
        return round(price, 2)
    if price >= 1:
        return round(price, 4)
    return round(price, 6)
