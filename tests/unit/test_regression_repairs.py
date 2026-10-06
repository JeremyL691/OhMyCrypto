"""Unit tests covering the mandatory defect repairs from Section 2.3 and R01/R02."""

from decimal import Decimal
import math
import pytest

from ohmycrypto.domain.models import (
    BookLevel,
    BookState,
    FeeProfile,
    Instrument,
    decimal_validator,
)
from ohmycrypto.domain.kernel import (
    estimate_buy_fill,
    estimate_sell_fill,
    evaluate_cross_venue_opportunity,
)
from ohmycrypto.domain.cooldown import (
    CooldownManager,
    build_route_key,
)
from ohmycrypto.notifications.outbox import (
    NotificationOutbox,
    deliver_macos_notification,
)


def test_nan_and_infinity_rejected():
    """Defect repair: Non-finite values and bool-as-number must be rejected."""
    # float NaN
    with pytest.raises(ValueError, match="cannot be NaN or Infinity"):
        decimal_validator(float("nan"), "test_nan")

    # float inf
    with pytest.raises(ValueError, match="cannot be NaN or Infinity"):
        decimal_validator(float("inf"), "test_inf")

    # boolean passed as number
    with pytest.raises(ValueError, match="must be a number, not boolean"):
        decimal_validator(True, "test_bool")

    # BookLevel reject negative price
    with pytest.raises(ValueError, match="must be positive"):
        BookLevel(price=Decimal("-10.0"), amount=Decimal("1.0"))

    # BookLevel reject zero price
    with pytest.raises(ValueError, match="must be positive"):
        BookLevel(price=Decimal("0.0"), amount=Decimal("1.0"))


def test_all_in_budget_strictly_enforced():
    """Defect repair: All-in budget B must never be exceeded (spend + fee <= B)."""
    budget = Decimal("1000.00")
    inst = Instrument(
        symbol="BTC/USDT",
        base="BTC",
        quote="USDT",
        venue="coinbase",
        native_symbol="BTC-USDT",
        amount_increment=Decimal("0.0001"),
    )
    # Taker fee 0.5% (0.005)
    fee_profile = FeeProfile(venue="coinbase", taker_rate=Decimal("0.005"), fee_currency="QUOTE")

    # Book with ask at 50,000 USDT
    asks = [BookLevel(price=Decimal("50000.00"), amount=Decimal("10.0"))]

    fill = estimate_buy_fill(
        asks=asks,
        all_in_quote_budget=budget,
        fee_profile=fee_profile,
        instrument=inst,
    )

    assert fill.is_complete is True
    total_outlay = fill.quote_spent + fill.fee_quote
    assert total_outlay <= budget, f"Outlay {total_outlay} exceeded budget {budget}!"
    assert fill.residual_quote >= Decimal("0")
    assert fill.acquired_base > Decimal("0")


def test_base_sell_fee_and_conservation():
    """Defect repair: Base-denominated sell fees reduce available base before sale."""
    base_qty = Decimal("2.0000")
    inst = Instrument(
        symbol="ETH/USDT",
        base="ETH",
        quote="USDT",
        venue="binance",
        native_symbol="ETHUSDT",
        amount_increment=Decimal("0.001"),
    )
    # 0.1% fee deducted in BASE currency (ETH)
    fee_profile = FeeProfile(
        venue="binance",
        taker_rate=Decimal("0.001"),
        fee_currency="BASE",
        charged_on="base",
    )

    bids = [BookLevel(price=Decimal("3000.00"), amount=Decimal("10.0"))]

    fill = estimate_sell_fill(
        bids=bids,
        available_base=base_qty,
        fee_profile=fee_profile,
        instrument=inst,
    )

    assert fill.is_complete is True
    assert fill.fee_base > Decimal("0")
    assert fill.fee_quote == Decimal("0")
    # Base asset conservation: sold_base + fee_base + residual_base == requested_amount
    total_accounted = (fill.quote_received / Decimal("3000.00")) + fill.fee_base + fill.residual_base
    assert math.isclose(float(total_accounted), float(base_qty), abs_tol=1e-8)


def test_tiny_price_move_does_not_reset_cooldown():
    """Defect repair: Price ticks must not create new fingerprints and reset cooldown."""
    mgr = CooldownManager(cooldown_duration_ms=30_000, disappearance_window_ms=60_000)

    inst_buy = Instrument(symbol="BTC/USD", base="BTC", quote="USD", venue="coinbase", native_symbol="BTC-USD")
    inst_sell = Instrument(symbol="BTC/USD", base="BTC", quote="USD", venue="kraken", native_symbol="BTC/USD")
    fee = FeeProfile(venue="generic", taker_rate=Decimal("0.001"))

    # Initial opportunity
    b1_asks = [BookLevel(price=Decimal("100000.00"), amount=Decimal("1.0"))]
    b2_bids = [BookLevel(price=Decimal("100500.00"), amount=Decimal("1.0"))]
    book_buy1 = BookState("coinbase", "BTC/USD", (), tuple(b1_asks), "snap", 1, None, "unknown", 1000, 1000)
    book_sell1 = BookState("kraken", "BTC/USD", tuple(b2_bids), (), "snap", 1, None, "unknown", 1000, 1000)

    opp1 = evaluate_cross_venue_opportunity(
        "BTC/USD", book_buy1, book_sell1, Decimal("1000.00"), fee, fee, inst_buy, inst_sell
    )
    assert opp1.is_eligible is True

    dec1 = mgr.evaluate_opportunity(opp1, now_utc_ms=1000)
    assert dec1.should_notify is True
    assert dec1.severity == "alert"
    initial_episode_id = dec1.episode_id

    # 1 second later: price moves minutely (100000.00 -> 100000.20)
    b1_asks_2 = [BookLevel(price=Decimal("100000.20"), amount=Decimal("1.0"))]
    b2_bids_2 = [BookLevel(price=Decimal("100500.20"), amount=Decimal("1.0"))]
    book_buy2 = BookState("coinbase", "BTC/USD", (), tuple(b1_asks_2), "snap", 2, None, "unknown", 2000, 2000)
    book_sell2 = BookState("kraken", "BTC/USD", tuple(b2_bids_2), (), "snap", 2, None, "unknown", 2000, 2000)

    opp2 = evaluate_cross_venue_opportunity(
        "BTC/USD", book_buy2, book_sell2, Decimal("1000.00"), fee, fee, inst_buy, inst_sell
    )

    dec2 = mgr.evaluate_opportunity(opp2, now_utc_ms=2000)
    assert dec2.should_notify is False
    assert dec2.severity == "suppressed"
    assert dec2.episode_id == initial_episode_id, "Episode ID must be preserved!"

    # 5 seconds later: massive escalation (net profit jumps by >= 15% and >= 2.0 quote units)
    b2_bids_3 = [BookLevel(price=Decimal("102000.00"), amount=Decimal("1.0"))]
    book_sell3 = BookState("kraken", "BTC/USD", tuple(b2_bids_3), (), "snap", 3, None, "unknown", 6000, 6000)

    opp3 = evaluate_cross_venue_opportunity(
        "BTC/USD", book_buy1, book_sell3, Decimal("1000.00"), fee, fee, inst_buy, inst_sell
    )
    dec3 = mgr.evaluate_opportunity(opp3, now_utc_ms=6000)
    assert dec3.should_notify is True
    assert dec3.severity == "escalated"
    assert dec3.episode_id == initial_episode_id


def test_currency_preservation_no_silent_dollar_equivalence():
    """Defect repair: Base/Quote units must be preserved as actual currency labels."""
    inst = Instrument(symbol="ETH/EUR", base="ETH", quote="EUR", venue="kraken", native_symbol="ETH/EUR")
    fee = FeeProfile(venue="kraken", taker_rate=Decimal("0.0025"))
    asks = [BookLevel(price=Decimal("2800.00"), amount=Decimal("2.0"))]
    bids = [BookLevel(price=Decimal("2850.00"), amount=Decimal("2.0"))]

    book_buy = BookState("kraken", "ETH/EUR", (), tuple(asks), "snap", 1, None, "unknown", 1000, 1000)
    book_sell = BookState("coinbase", "ETH/EUR", tuple(bids), (), "snap", 1, None, "unknown", 1000, 1000)

    opp = evaluate_cross_venue_opportunity(
        "ETH/EUR", book_buy, book_sell, Decimal("500.00"), fee, fee, inst, inst
    )
    assert opp.budget_units == "EUR"
    route = build_route_key(opp)
    assert "EUR" in route
    assert "USD" not in route


def test_notification_outbox_quiet_mode_and_visibility():
    """Defect repair: Notification delivery must decouple timestamps and support quiet suppression."""
    outbox = NotificationOutbox(quiet_mode=True)
    rec = outbox.enqueue(
        event_id="evt_1",
        episode_id="ep_1",
        route_key="cb->kr:BTC/USDT:1000USDT",
        mode="speech",
        decision_utc_ms=1728148800000,
    )
    assert rec.state == "suppressed"
    assert rec.suppression_reason == "quiet_mode_enabled"
    assert rec.delivery_utc_ms is None

    # Normal outbox
    active_outbox = NotificationOutbox(quiet_mode=False)
    rec2 = active_outbox.enqueue(
        event_id="evt_2",
        episode_id="ep_2",
        route_key="cb->kr:BTC/USDT:1000USDT",
        mode="audio",
        decision_utc_ms=1728148800000,
    )
    assert rec2.state == "pending"
    assert rec2.enqueue_utc_ms >= rec2.decision_utc_ms


def test_unsorted_books_rejected():
    """N01: Unsorted bids or asks must be rejected by BookState."""
    # Unsorted asks (ascending required)
    asks = (
        BookLevel(price=Decimal("102.0"), amount=Decimal("1.0")),
        BookLevel(price=Decimal("101.0"), amount=Decimal("1.0")),
    )
    with pytest.raises(ValueError, match="Unsorted asks"):
        BookState("cb", "BTC/USDT", (), asks, "test", 1, None, "unknown", 1000, 1000)

    # Unsorted bids (descending required)
    bids = (
        BookLevel(price=Decimal("99.0"), amount=Decimal("1.0")),
        BookLevel(price=Decimal("100.0"), amount=Decimal("1.0")),
    )
    with pytest.raises(ValueError, match="Unsorted bids"):
        BookState("cb", "BTC/USDT", bids, (), "test", 1, None, "unknown", 1000, 1000)


def test_incompatible_instruments_rejected():
    """N01: Incompatible base or cross-quote assets must not produce eligible opportunity."""
    inst_btc = Instrument("BTC/USDT", "BTC", "USDT", "cb", "BTC-USDT")
    inst_eth = Instrument("ETH/USDT", "ETH", "USDT", "kr", "ETH/USDT")
    fee = FeeProfile("generic", taker_rate=Decimal("0.001"))

    asks = (BookLevel(price=Decimal("50000.0"), amount=Decimal("1.0")),)
    bids = (BookLevel(price=Decimal("55000.0"), amount=Decimal("1.0")),)
    b_buy = BookState("cb", "BTC/USDT", (), asks, "test", 1, None, "unknown", 1000, 1000)
    b_sell = BookState("kr", "ETH/USDT", bids, (), "test", 1, None, "unknown", 1000, 1000)

    opp = evaluate_cross_venue_opportunity(
        "BTC/USDT", b_buy, b_sell, Decimal("1000.0"), fee, fee, inst_btc, inst_eth
    )
    assert opp.is_eligible is False
    assert "incompatible_base_assets" in opp.eligibility_reasons


def test_zero_fee_and_zero_threshold_valid():
    """N01: Zero fees and zero thresholds are valid and supported."""
    inst = Instrument("BTC/USDT", "BTC", "USDT", "cb", "BTC-USDT")
    zero_fee = FeeProfile("cb", taker_rate=Decimal("0.0"), maker_rate=Decimal("0.0"), fixed_fee=Decimal("0.0"))
    asks = (BookLevel(price=Decimal("100.0"), amount=Decimal("10.0")),)
    bids = (BookLevel(price=Decimal("110.0"), amount=Decimal("10.0")),)
    b_buy = BookState("cb", "BTC/USDT", (), asks, "test", 1, None, "unknown", 1000, 1000)
    b_sell = BookState("kr", "BTC/USDT", bids, (), "test", 1, None, "unknown", 1000, 1000)

    opp = evaluate_cross_venue_opportunity(
        "BTC/USDT", b_buy, b_sell, Decimal("1000.0"), zero_fee, zero_fee, inst, inst,
        min_profit_threshold=Decimal("0.0"), min_spread_threshold=Decimal("0.0")
    )
    assert opp.is_positive is True
    assert opp.is_eligible is True
    assert opp.buy_fill.fee_quote == Decimal("0.0")
    assert opp.sell_fill.fee_quote == Decimal("0.0")
    assert opp.net_profit_quote == Decimal("100.0")  # (1000 / 100) * 110 - 1000 = 1100 - 1000 = 100

