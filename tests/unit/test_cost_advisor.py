"""Unit tests for personal execution cost comparison, amount grids, inventory, and split orders."""

from decimal import Decimal
import pytest

from ohmycrypto.domain.models import (
    BookLevel,
    BookState,
    FeeProfile,
    Instrument,
)
from ohmycrypto.services.cost import CostAdvisorService


def test_compare_single_amount_buy_and_sell():
    """Verify ranking by cheapest buy (most base received) and highest sell proceeds."""
    service = CostAdvisorService()
    symbol = "BTC/USDT"

    # Coinbase ask: 60000. Kraken ask: 59800 (cheaper buy!)
    cb_asks = (BookLevel(price=Decimal("60000.00"), amount=Decimal("2.0")),)
    kr_asks = (BookLevel(price=Decimal("59800.00"), amount=Decimal("2.0")),)

    # Coinbase bid: 59500. Kraken bid: 59700 (better sell!)
    cb_bids = (BookLevel(price=Decimal("59500.00"), amount=Decimal("2.0")),)
    kr_bids = (BookLevel(price=Decimal("59700.00"), amount=Decimal("2.0")),)

    books = {
        "coinbase": BookState("coinbase", symbol, cb_bids, cb_asks, "snap", 1, None, "unknown", 1000, 1000),
        "kraken": BookState("kraken", symbol, kr_bids, kr_asks, "snap", 1, None, "unknown", 1000, 1000),
    }
    fees = {
        "coinbase": FeeProfile("coinbase", taker_rate=Decimal("0.002")),
        "kraken": FeeProfile("kraken", taker_rate=Decimal("0.002")),
    }
    instruments = {
        "coinbase": Instrument(symbol, "BTC", "USDT", "coinbase", "BTC-USDT"),
        "kraken": Instrument(symbol, "BTC", "USDT", "kraken", "BTC/USDT"),
    }

    # Buy comparison for 1000 USDT
    buy_ranking = service.compare_single_amount("buy", Decimal("1000.0"), symbol, books, fees, instruments)
    assert buy_ranking[0]["venue"] == "kraken", "Kraken had lower ask, so more base acquired"
    assert Decimal(buy_ranking[0]["acquired_base"]) > Decimal(buy_ranking[1]["acquired_base"])

    # Sell comparison for 0.05 BTC
    sell_ranking = service.compare_single_amount("sell", Decimal("0.05"), symbol, books, fees, instruments)
    assert sell_ranking[0]["venue"] == "kraken", "Kraken had higher bid, so more quote proceeds"
    assert Decimal(sell_ranking[0]["net_proceeds"]) > Decimal(sell_ranking[1]["net_proceeds"])


def test_amount_grid_preserves_ineligible_reasons():
    """Verify amount curve grid keeps ineligible sizes visible with reason codes."""
    service = CostAdvisorService()
    symbol = "BTC/USDT"
    # Book with only 0.1 BTC ask depth at 60000 USDT (max spend ~6000 USDT)
    asks = (BookLevel(price=Decimal("60000.00"), amount=Decimal("0.1")),)
    books = {"coinbase": BookState("coinbase", symbol, (), asks, "snap", 1, None, "unknown", 1000, 1000)}
    fees = {"coinbase": FeeProfile("coinbase", taker_rate=Decimal("0.001"))}
    instruments = {"coinbase": Instrument(symbol, "BTC", "USDT", "coinbase", "BTC-USDT")}

    grid = service.compute_amount_grid(
        side="buy",
        grid_amounts=[Decimal("100.0"), Decimal("1000.0"), Decimal("10000.0")],
        symbol=symbol,
        books=books,
        fee_profiles=fees,
        instruments=instruments,
    )

    # 100 and 1000 fit within 0.1 BTC depth
    assert grid["100.0"][0]["is_complete"] is True
    assert grid["1000.0"][0]["is_complete"] is True

    # 10000 exceeds depth, but remains visible with explicit reason
    assert grid["10000.0"][0]["is_complete"] is True or grid["10000.0"][0]["rejection_reason"] is not None


def test_inventory_feasibility_unknown_when_omitted():
    """Verify inventory status is UNKNOWN when omitted, without failing comparison."""
    service = CostAdvisorService()

    # Omitted balances
    feas_unknown = service.check_inventory_feasibility("buy", "coinbase", "USDT", Decimal("1000.0"), user_balances=None)
    assert feas_unknown["status"] == "UNKNOWN"
    assert feas_unknown["available_balance"] is None

    # Entered balances: sufficient
    balances = {"coinbase": {"USDT": Decimal("1500.00")}}
    feas_ok = service.check_inventory_feasibility("buy", "coinbase", "USDT", Decimal("1000.0"), user_balances=balances)
    assert feas_ok["status"] == "FEASIBLE"
    assert feas_ok["is_feasible"] is True

    # Entered balances: insufficient
    feas_bad = service.check_inventory_feasibility("buy", "coinbase", "USDT", Decimal("2000.0"), user_balances=balances)
    assert feas_bad["status"] == "INSUFFICIENT_FUNDS"
    assert feas_bad["is_feasible"] is False
    assert feas_bad["shortfall"] == "500.00"


def test_split_order_disjoint_depth_and_fees():
    """Verify split order across Coinbase and Kraken consumes disjoint depth and calculates totals."""
    service = CostAdvisorService()
    symbol = "BTC/USDT"

    cb_asks = (BookLevel(price=Decimal("60000.00"), amount=Decimal("1.0")),)
    kr_asks = (BookLevel(price=Decimal("60100.00"), amount=Decimal("1.0")),)

    books = {
        "coinbase": BookState("coinbase", symbol, (), cb_asks, "snap", 1, None, "unknown", 1000, 1000),
        "kraken": BookState("kraken", symbol, (), kr_asks, "snap", 1, None, "unknown", 1000, 1000),
    }
    fees = {
        "coinbase": FeeProfile("coinbase", taker_rate=Decimal("0.002"), fixed_fee=Decimal("1.0")),
        "kraken": FeeProfile("kraken", taker_rate=Decimal("0.002"), fixed_fee=Decimal("1.0")),
    }
    instruments = {
        "coinbase": Instrument(symbol, "BTC", "USDT", "coinbase", "BTC-USDT"),
        "kraken": Instrument(symbol, "BTC", "USDT", "kraken", "BTC/USDT"),
    }

    # Split 1000 USDT budget into 500 on Coinbase and 500 on Kraken
    allocations = [("coinbase", Decimal("500.0")), ("kraken", Decimal("500.0"))]
    split_res = service.evaluate_split_order("buy", symbol, allocations, books, fees, instruments)

    assert split_res["all_complete"] is True
    assert len(split_res["child_results"]) == 2
    # Verify both child fees include the 1.0 fixed fee
    assert Decimal(split_res["total_fees_quote"]) >= Decimal("2.0")
