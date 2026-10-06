"""Deterministic calculation kernel for OhMyCrypto.

Follows Section 6.1 and 6.2 of PROJECT_EXECUTION_GUIDE.md:
- Strictly Decimal-based math (no binary float drift)
- All-in quote budget enforcement (book spend + taker fee <= budget)
- Base vs quote fee debit/credit handling
- Incremental lot-size and precision truncation (no over-selling)
- Residual tracking for unspent quote and unsold base dust
- Invariant assertions on budget and asset conservation
"""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import List, Optional, Tuple, Sequence

from ohmycrypto.domain.models import (
    BookLevel,
    BookState,
    FeeProfile,
    FillResult,
    Instrument,
    OpportunityResult,
    compute_sha256,
    decimal_validator,
)

KERNEL_VERSION = "1.0.0"


def quantize_down(val: Decimal, increment: Decimal) -> Decimal:
    """Quantize a decimal down to multiples of increment."""
    if increment <= Decimal("0"):
        raise ValueError(f"Increment must be positive, got {increment}")
    steps = (val / increment).to_integral_value(rounding=ROUND_DOWN)
    return steps * increment


def estimate_buy_fill(
    asks: Sequence[BookLevel],
    all_in_quote_budget: Decimal,
    fee_profile: FeeProfile,
    instrument: Instrument,
) -> FillResult:
    """Estimate buy execution against asks under an all-in quote budget.
    
    Invariant: quote_spent + fee_quote <= all_in_quote_budget
    """
    budget = decimal_validator(all_in_quote_budget, "all_in_quote_budget", allow_zero=False)
    taker_rate = fee_profile.taker_rate
    fixed_fee = fee_profile.fixed_fee

    if fee_profile.fee_currency == "QUOTE" or fee_profile.charged_on == "quote":
        # Effective max book spend S such that S * (1 + taker_rate) + fixed_fee <= budget
        if budget <= fixed_fee:
            return FillResult(
                side="buy",
                requested_amount=budget,
                acquired_base=Decimal("0"),
                quote_spent=Decimal("0"),
                quote_received=Decimal("0"),
                avg_price=Decimal("0"),
                fee_quote=Decimal("0"),
                fee_base=Decimal("0"),
                residual_quote=budget,
                residual_base=Decimal("0"),
                levels_consumed=0,
                is_complete=False,
                rejection_reason="budget_less_than_fixed_fee",
            )
        max_spend_allowed = (budget - fixed_fee) / (Decimal("1") + taker_rate)
    else:
        # Fee charged in base currency; whole budget can be spent on book
        max_spend_allowed = budget

    remaining_spend = max_spend_allowed
    acquired_base = Decimal("0")
    actual_quote_spent = Decimal("0")
    levels_consumed = 0

    for level in asks:
        if remaining_spend <= Decimal("0"):
            break
        price = level.price
        available_base = level.amount
        level_quote = price * available_base

        if level_quote <= remaining_spend:
            # Consume whole level
            base_to_buy = quantize_down(available_base, instrument.amount_increment)
            spend_here = base_to_buy * price
            remaining_spend -= spend_here
            actual_quote_spent += spend_here
            acquired_base += base_to_buy
            levels_consumed += 1
        else:
            # Partial consumption
            base_raw = remaining_spend / price
            base_to_buy = quantize_down(base_raw, instrument.amount_increment)
            if base_to_buy > Decimal("0"):
                spend_here = base_to_buy * price
                actual_quote_spent += spend_here
                acquired_base += base_to_buy
                remaining_spend -= spend_here
                levels_consumed += 1
            break

    if acquired_base < instrument.min_amount:
        return FillResult(
            side="buy",
            requested_amount=budget,
            acquired_base=Decimal("0"),
            quote_spent=Decimal("0"),
            quote_received=Decimal("0"),
            avg_price=Decimal("0"),
            fee_quote=Decimal("0"),
            fee_base=Decimal("0"),
            residual_quote=budget,
            residual_base=Decimal("0"),
            levels_consumed=levels_consumed,
            is_complete=False,
            rejection_reason=f"acquired_base_{acquired_base}_below_min_{instrument.min_amount}",
        )

    # Compute fees
    if fee_profile.fee_currency == "QUOTE" or fee_profile.charged_on == "quote":
        fee_quote = (actual_quote_spent * taker_rate) + fixed_fee
        fee_base = Decimal("0")
        residual_quote = budget - (actual_quote_spent + fee_quote)
        residual_base = Decimal("0")
    else:
        # Base fee
        fee_quote = Decimal("0")
        fee_base = (acquired_base * taker_rate) + fixed_fee
        acquired_base -= fee_base
        residual_quote = budget - actual_quote_spent
        residual_base = Decimal("0")

    # Invariant assertion
    if fee_profile.fee_currency == "QUOTE" or fee_profile.charged_on == "quote":
        assert (actual_quote_spent + fee_quote) <= budget + Decimal("1e-12"), (
            f"Budget exceeded! spend={actual_quote_spent}, fee={fee_quote}, budget={budget}"
        )

    avg_price = actual_quote_spent / (acquired_base + fee_base) if (acquired_base + fee_base) > Decimal("0") else Decimal("0")
    min_lot_spend = instrument.amount_increment * (asks[-1].price if asks else Decimal("1"))
    is_complete = remaining_spend <= min_lot_spend
    rejection_reason = None if is_complete else "insufficient_asks_depth"

    return FillResult(
        side="buy",
        requested_amount=budget,
        acquired_base=acquired_base,
        quote_spent=actual_quote_spent,
        quote_received=Decimal("0"),
        avg_price=avg_price,
        fee_quote=fee_quote,
        fee_base=fee_base,
        residual_quote=residual_quote,
        residual_base=residual_base,
        levels_consumed=levels_consumed,
        is_complete=is_complete,
        rejection_reason=rejection_reason,
    )


def estimate_sell_fill(
    bids: Sequence[BookLevel],
    available_base: Decimal,
    fee_profile: FeeProfile,
    instrument: Instrument,
) -> FillResult:
    """Estimate sell execution against bids using available base quantity.
    
    Handles base vs quote fees and lot size quantization.
    """
    total_base = decimal_validator(available_base, "available_base", allow_zero=False)
    taker_rate = fee_profile.taker_rate
    fixed_fee = fee_profile.fixed_fee

    if fee_profile.fee_currency == "BASE" or fee_profile.charged_on == "base":
        # Fee deducted in base asset: sellable + base_fee <= total_base
        if total_base <= fixed_fee:
            return FillResult(
                side="sell",
                requested_amount=total_base,
                acquired_base=Decimal("0"),
                quote_spent=Decimal("0"),
                quote_received=Decimal("0"),
                avg_price=Decimal("0"),
                fee_quote=Decimal("0"),
                fee_base=Decimal("0"),
                residual_quote=Decimal("0"),
                residual_base=total_base,
                levels_consumed=0,
                is_complete=False,
                rejection_reason="base_amount_less_than_fixed_fee",
            )
        max_base_to_sell = (total_base - fixed_fee) / (Decimal("1") + taker_rate)
        sellable_base = quantize_down(max_base_to_sell, instrument.amount_increment)
        fee_base = (sellable_base * taker_rate) + fixed_fee
        fee_quote = Decimal("0")
        residual_base = total_base - (sellable_base + fee_base)
    else:
        # Fee deducted from quote proceeds
        sellable_base = quantize_down(total_base, instrument.amount_increment)
        fee_base = Decimal("0")
        residual_base = total_base - sellable_base
        fee_quote = Decimal("0")  # will calculate after quote proceeds known

    if sellable_base < instrument.min_amount:
        return FillResult(
            side="sell",
            requested_amount=total_base,
            acquired_base=Decimal("0"),
            quote_spent=Decimal("0"),
            quote_received=Decimal("0"),
            avg_price=Decimal("0"),
            fee_quote=Decimal("0"),
            fee_base=fee_base if (fee_profile.fee_currency == "BASE" or fee_profile.charged_on == "base") else Decimal("0"),
            residual_quote=Decimal("0"),
            residual_base=total_base,
            levels_consumed=0,
            is_complete=False,
            rejection_reason=f"sellable_base_{sellable_base}_below_min_{instrument.min_amount}",
        )

    remaining_base_to_fill = sellable_base
    gross_quote_received = Decimal("0")
    sold_base = Decimal("0")
    levels_consumed = 0

    for level in bids:
        if remaining_base_to_fill <= Decimal("0"):
            break
        price = level.price
        bid_amount = level.amount

        if bid_amount <= remaining_base_to_fill:
            lot = quantize_down(bid_amount, instrument.amount_increment)
            gross_quote_received += lot * price
            sold_base += lot
            remaining_base_to_fill -= lot
            levels_consumed += 1
        else:
            lot = quantize_down(remaining_base_to_fill, instrument.amount_increment)
            if lot > Decimal("0"):
                gross_quote_received += lot * price
                sold_base += lot
                remaining_base_to_fill -= lot
                levels_consumed += 1
            break

    if sold_base < sellable_base:
        return FillResult(
            side="sell",
            requested_amount=total_base,
            acquired_base=Decimal("0"),
            quote_spent=Decimal("0"),
            quote_received=Decimal("0"),
            avg_price=Decimal("0"),
            fee_quote=Decimal("0"),
            fee_base=Decimal("0"),
            residual_quote=Decimal("0"),
            residual_base=total_base,
            levels_consumed=levels_consumed,
            is_complete=False,
            rejection_reason="insufficient_bids_depth",
        )

    if fee_profile.fee_currency != "BASE" and fee_profile.charged_on != "base":
        fee_quote = (gross_quote_received * taker_rate) + fixed_fee

    net_quote_received = gross_quote_received - fee_quote
    avg_price = gross_quote_received / sold_base if sold_base > Decimal("0") else Decimal("0")

    # Conservation assertion
    assert (sold_base + fee_base + residual_base) <= total_base + Decimal("1e-12")

    return FillResult(
        side="sell",
        requested_amount=total_base,
        acquired_base=Decimal("0"),
        quote_spent=Decimal("0"),
        quote_received=net_quote_received,
        avg_price=avg_price,
        fee_quote=fee_quote,
        fee_base=fee_base,
        residual_quote=Decimal("0"),
        residual_base=residual_base,
        levels_consumed=levels_consumed,
        is_complete=True,
    )


def compute_canonical_input_payload(
    symbol: str,
    buy_book: BookState,
    sell_book: BookState,
    all_in_quote_budget: Decimal,
    buy_instrument: Instrument,
    sell_instrument: Instrument,
) -> dict:
    return {
        "symbol": symbol,
        "buy_venue": buy_book.venue,
        "sell_venue": sell_book.venue,
        "budget": str(all_in_quote_budget),
        "budget_units": buy_instrument.quote,
        "buy_asks": [[str(lvl.price), str(lvl.amount)] for lvl in buy_book.asks],
        "sell_bids": [[str(lvl.price), str(lvl.amount)] for lvl in sell_book.bids],
        "buy_book_seq": buy_book.applied_sequence,
        "sell_book_seq": sell_book.applied_sequence,
        "buy_instrument": {
            "price_increment": str(buy_instrument.price_increment),
            "amount_increment": str(buy_instrument.amount_increment),
            "min_amount": str(buy_instrument.min_amount),
            "min_cost": str(buy_instrument.min_cost),
        },
        "sell_instrument": {
            "price_increment": str(sell_instrument.price_increment),
            "amount_increment": str(sell_instrument.amount_increment),
            "min_amount": str(sell_instrument.min_amount),
            "min_cost": str(sell_instrument.min_cost),
        },
        "kernel_version": KERNEL_VERSION,
    }


def compute_canonical_config_payload(
    buy_fee_profile: FeeProfile,
    sell_fee_profile: FeeProfile,
    min_profit_threshold: Decimal,
    min_spread_threshold: Decimal,
) -> dict:
    return {
        "buy_fee": {
            "maker_rate": str(buy_fee_profile.maker_rate),
            "taker_rate": str(buy_fee_profile.taker_rate),
            "fixed_fee": str(buy_fee_profile.fixed_fee),
            "fee_currency": buy_fee_profile.fee_currency,
            "charged_on": buy_fee_profile.charged_on,
        },
        "sell_fee": {
            "maker_rate": str(sell_fee_profile.maker_rate),
            "taker_rate": str(sell_fee_profile.taker_rate),
            "fixed_fee": str(sell_fee_profile.fixed_fee),
            "fee_currency": sell_fee_profile.fee_currency,
            "charged_on": sell_fee_profile.charged_on,
        },
        "min_profit": str(min_profit_threshold),
        "min_spread": str(min_spread_threshold),
        "kernel_version": KERNEL_VERSION,
    }


def compute_canonical_result_payload(
    symbol: str,
    buy_venue: str,
    sell_venue: str,
    budget_amount: Decimal,
    budget_units: str,
    buy_fill: FillResult,
    sell_fill: FillResult,
    net_profit_quote: Decimal,
    effective_spread: Decimal,
    midpoint_price: Decimal,
    is_positive: bool,
    is_eligible: bool,
    eligibility_reasons: Sequence[str],
) -> dict:
    return {
        "symbol": symbol,
        "buy_venue": buy_venue,
        "sell_venue": sell_venue,
        "budget_amount": str(budget_amount),
        "budget_units": budget_units,
        "net_profit_quote": str(net_profit_quote),
        "effective_spread": str(effective_spread),
        "midpoint_price": str(midpoint_price),
        "is_positive": is_positive,
        "is_eligible": is_eligible,
        "eligibility_reasons": list(eligibility_reasons),
        "buy_fill": {
            "side": buy_fill.side,
            "is_complete": buy_fill.is_complete,
            "rejection_reason": buy_fill.rejection_reason,
            "acquired_base": str(buy_fill.acquired_base),
            "quote_spent": str(buy_fill.quote_spent),
            "fee_quote": str(buy_fill.fee_quote),
            "fee_base": str(buy_fill.fee_base),
            "residual_quote": str(buy_fill.residual_quote),
            "residual_base": str(buy_fill.residual_base),
            "avg_price": str(buy_fill.avg_price),
            "levels_consumed": buy_fill.levels_consumed,
        },
        "sell_fill": {
            "side": sell_fill.side,
            "is_complete": sell_fill.is_complete,
            "rejection_reason": sell_fill.rejection_reason,
            "acquired_base": str(sell_fill.acquired_base),
            "quote_received": str(sell_fill.quote_received),
            "fee_quote": str(sell_fill.fee_quote),
            "fee_base": str(sell_fill.fee_base),
            "residual_quote": str(sell_fill.residual_quote),
            "residual_base": str(sell_fill.residual_base),
            "avg_price": str(sell_fill.avg_price),
            "levels_consumed": sell_fill.levels_consumed,
        },
        "kernel_version": KERNEL_VERSION,
    }


def evaluate_cross_venue_opportunity(
    symbol: str,
    buy_book: BookState,
    sell_book: BookState,
    all_in_quote_budget: Decimal,
    buy_fee_profile: FeeProfile,
    sell_fee_profile: FeeProfile,
    buy_instrument: Instrument,
    sell_instrument: Instrument,
    min_profit_threshold: Decimal = Decimal("0.0"),
    min_spread_threshold: Decimal = Decimal("0.0"),
) -> OpportunityResult:
    """Evaluate cross-venue arbitrage opportunity deterministically."""
    reasons: List[str] = []

    if buy_instrument.base != sell_instrument.base:
        reasons.append("incompatible_base_assets")
    if buy_instrument.quote != sell_instrument.quote:
        reasons.append("unsupported_cross_quote_conversion")

    input_payload = compute_canonical_input_payload(
        symbol=symbol,
        buy_book=buy_book,
        sell_book=sell_book,
        all_in_quote_budget=all_in_quote_budget,
        buy_instrument=buy_instrument,
        sell_instrument=sell_instrument,
    )
    config_payload = compute_canonical_config_payload(
        buy_fee_profile=buy_fee_profile,
        sell_fee_profile=sell_fee_profile,
        min_profit_threshold=min_profit_threshold,
        min_spread_threshold=min_spread_threshold,
    )
    input_hash = compute_sha256(input_payload)
    config_hash = compute_sha256(config_payload)

    # Estimate buy leg
    buy_fill = estimate_buy_fill(
        asks=buy_book.asks,
        all_in_quote_budget=all_in_quote_budget,
        fee_profile=buy_fee_profile,
        instrument=buy_instrument,
    )

    if not buy_fill.is_complete:
        reasons.append(f"buy_fill_failed: {buy_fill.rejection_reason}")
        midpoint = Decimal("0")
        if len(buy_book.asks) > 0 and len(sell_book.bids) > 0:
            midpoint = (buy_book.asks[0].price + sell_book.bids[0].price) / Decimal("2")

        sell_stub = FillResult(
            side="sell",
            requested_amount=Decimal("0"),
            acquired_base=Decimal("0"),
            quote_spent=Decimal("0"),
            quote_received=Decimal("0"),
            avg_price=Decimal("0"),
            fee_quote=Decimal("0"),
            fee_base=Decimal("0"),
            residual_quote=Decimal("0"),
            residual_base=Decimal("0"),
            levels_consumed=0,
            is_complete=False,
            rejection_reason="no_base_acquired",
        )

        res_payload = compute_canonical_result_payload(
            symbol=symbol,
            buy_venue=buy_book.venue,
            sell_venue=sell_book.venue,
            budget_amount=all_in_quote_budget,
            budget_units=buy_instrument.quote,
            buy_fill=buy_fill,
            sell_fill=sell_stub,
            net_profit_quote=Decimal("0"),
            effective_spread=Decimal("0"),
            midpoint_price=midpoint,
            is_positive=False,
            is_eligible=False,
            eligibility_reasons=reasons,
        )

        return OpportunityResult(
            symbol=symbol,
            buy_venue=buy_book.venue,
            sell_venue=sell_book.venue,
            budget_amount=all_in_quote_budget,
            budget_units=buy_instrument.quote,
            buy_fill=buy_fill,
            sell_fill=sell_stub,
            net_profit_quote=Decimal("0"),
            effective_spread=Decimal("0"),
            midpoint_price=midpoint,
            is_positive=False,
            is_eligible=False,
            eligibility_reasons=tuple(reasons),
            input_hash=input_hash,
            config_hash=config_hash,
            kernel_version=KERNEL_VERSION,
            result_hash=compute_sha256(res_payload),
        )

    # Sell leg: sell exactly the net acquired base
    sell_fill = estimate_sell_fill(
        bids=sell_book.bids,
        available_base=buy_fill.acquired_base,
        fee_profile=sell_fee_profile,
        instrument=sell_instrument,
    )

    if not sell_fill.is_complete:
        reasons.append(f"sell_fill_failed: {sell_fill.rejection_reason}")

    # Total all-in cash spend on buy venue
    total_quote_spend = buy_fill.quote_spent + buy_fill.fee_quote
    # Total net cash received on sell venue
    net_quote_received = sell_fill.quote_received

    net_profit = net_quote_received - total_quote_spend
    effective_spread = net_profit / total_quote_spend if total_quote_spend > Decimal("0") else Decimal("0")
    midpoint = (buy_fill.avg_price + sell_fill.avg_price) / Decimal("2") if (buy_fill.avg_price > Decimal("0") and sell_fill.avg_price > Decimal("0")) else Decimal("0")

    is_positive = net_profit > Decimal("0")

    if not is_positive:
        reasons.append("non_positive_profit")
    if net_profit < min_profit_threshold:
        reasons.append(f"profit_{net_profit}_below_threshold_{min_profit_threshold}")
    if effective_spread < min_spread_threshold:
        reasons.append(f"spread_{effective_spread}_below_threshold_{min_spread_threshold}")

    is_eligible = (
        buy_fill.is_complete
        and sell_fill.is_complete
        and is_positive
        and (net_profit >= min_profit_threshold)
        and (effective_spread >= min_spread_threshold)
        and ("incompatible_base_assets" not in reasons)
        and ("unsupported_cross_quote_conversion" not in reasons)
    )

    res_payload = compute_canonical_result_payload(
        symbol=symbol,
        buy_venue=buy_book.venue,
        sell_venue=sell_book.venue,
        budget_amount=all_in_quote_budget,
        budget_units=buy_instrument.quote,
        buy_fill=buy_fill,
        sell_fill=sell_fill,
        net_profit_quote=net_profit,
        effective_spread=effective_spread,
        midpoint_price=midpoint,
        is_positive=is_positive,
        is_eligible=is_eligible,
        eligibility_reasons=reasons,
    )

    return OpportunityResult(
        symbol=symbol,
        buy_venue=buy_book.venue,
        sell_venue=sell_book.venue,
        budget_amount=all_in_quote_budget,
        budget_units=buy_instrument.quote,
        buy_fill=buy_fill,
        sell_fill=sell_fill,
        net_profit_quote=net_profit,
        effective_spread=effective_spread,
        midpoint_price=midpoint,
        is_positive=is_positive,
        is_eligible=is_eligible,
        eligibility_reasons=tuple(reasons),
        input_hash=input_hash,
        config_hash=config_hash,
        kernel_version=KERNEL_VERSION,
        result_hash=compute_sha256(res_payload),
    )
