import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from strategy import (  # noqa: E402
    build_alert_decision,
    filter_fresh_prices,
    record_alert,
    scan_spread_candidates,
    should_alert,
    validate_candidate_with_orderbook,
)


class FakeOrderBookExchange:
    def __init__(self, book):
        self.book = book

    async def fetch_order_book(self, symbol, limit=None):
        return self.book


class StrategyTests(unittest.IsolatedAsyncioTestCase):
    def test_filter_fresh_prices_rejects_invalid_and_stale_quotes(self):
        now_ms = 1_700_000_000_000
        prices = {
            "binance": {
                "bid": 100.0,
                "ask": 101.0,
                "last": 100.5,
                "timestamp": now_ms - 5_000,
            },
            "okx": {
                "bid": 100.0,
                "ask": 99.0,
                "last": 99.5,
                "timestamp": now_ms - 5_000,
            },
            "bybit": {
                "bid": 100.0,
                "ask": 101.0,
                "last": 100.5,
                "timestamp": now_ms - 30_000,
            },
        }

        fresh, rejected = filter_fresh_prices(prices, stale_ms=15_000, now_ms=now_ms)

        self.assertEqual(set(fresh.keys()), {"binance"})
        self.assertEqual(rejected["okx"], "crossed_quote")
        self.assertEqual(rejected["bybit"], "stale_quote")

    def test_scan_spread_candidates_orders_by_net_spread(self):
        prices = {
            "binance": {"bid": 100.0, "ask": 101.0, "last": 100.5, "timestamp": 1},
            "okx": {"bid": 103.0, "ask": 104.0, "last": 103.5, "timestamp": 1},
            "bybit": {"bid": 102.0, "ask": 102.5, "last": 102.2, "timestamp": 1},
        }

        candidates = scan_spread_candidates(prices, fee_rate=0.001)

        self.assertEqual(candidates[0]["buy_exchange"], "binance")
        self.assertEqual(candidates[0]["sell_exchange"], "okx")
        self.assertGreater(candidates[0]["net_spread"], candidates[-1]["net_spread"])

    async def test_validate_candidate_with_orderbook_returns_profit_when_depth_is_enough(self):
        clients = {
            "binance": FakeOrderBookExchange({"asks": [[100.0, 20.0]], "bids": []}),
            "okx": FakeOrderBookExchange({"asks": [], "bids": [[102.0, 20.0]]}),
        }
        candidate = {
            "buy_exchange": "binance",
            "sell_exchange": "okx",
            "buy_price": 100.0,
            "sell_price": 102.0,
            "net_spread": 0.018,
        }

        opportunity = await validate_candidate_with_orderbook(
            clients,
            "BTC/USDT",
            candidate,
            trade_size=1000.0,
            orderbook_limit=10,
            fee_rate=0.001,
        )

        self.assertIsNotNone(opportunity)
        self.assertGreater(opportunity["estimated_profit"], 0)
        self.assertAlmostEqual(opportunity["base_amount"], 10.0)

    async def test_validate_candidate_with_orderbook_returns_none_when_depth_is_insufficient(self):
        clients = {
            "binance": FakeOrderBookExchange({"asks": [[100.0, 2.0]], "bids": []}),
            "okx": FakeOrderBookExchange({"asks": [], "bids": [[102.0, 20.0]]}),
        }
        candidate = {
            "buy_exchange": "binance",
            "sell_exchange": "okx",
            "buy_price": 100.0,
            "sell_price": 102.0,
            "net_spread": 0.018,
        }

        opportunity = await validate_candidate_with_orderbook(
            clients,
            "BTC/USDT",
            candidate,
            trade_size=1000.0,
            orderbook_limit=10,
            fee_rate=0.001,
        )

        self.assertIsNone(opportunity)

    async def test_validate_candidate_with_orderbook_exposes_negative_profit_after_slippage(self):
        clients = {
            "binance": FakeOrderBookExchange(
                {"asks": [[100.0, 5.0], [103.0, 5.0]], "bids": []}
            ),
            "okx": FakeOrderBookExchange(
                {"asks": [], "bids": [[101.0, 5.0], [99.0, 5.0]]}
            ),
        }
        candidate = {
            "buy_exchange": "binance",
            "sell_exchange": "okx",
            "buy_price": 100.0,
            "sell_price": 101.0,
            "net_spread": 0.008,
        }

        opportunity = await validate_candidate_with_orderbook(
            clients,
            "BTC/USDT",
            candidate,
            trade_size=1000.0,
            orderbook_limit=10,
            fee_rate=0.001,
        )

        self.assertIsNotNone(opportunity)
        self.assertLess(opportunity["estimated_profit"], 0)

    def test_should_alert_suppresses_duplicates_and_allows_escalation(self):
        opportunity = {
            "symbol": "BTC/USDT",
            "buy_exchange": "binance",
            "sell_exchange": "okx",
            "estimated_profit": 10.0,
            "effective_spread": 0.01,
            "midpoint_price": 100000.0,
        }
        alert_state = {}

        first = build_alert_decision(
            opportunity,
            alert_state,
            cooldown_sec=30,
            min_profit=2.0,
            alert_price_change_ratio=0.15,
            now=100.0,
        )
        self.assertTrue(first["should_notify"])
        self.assertTrue(
            should_alert(
                opportunity,
                alert_state,
                cooldown_sec=30,
                min_profit=2.0,
                alert_price_change_ratio=0.15,
                now=100.0,
            )
        )

        record_alert(alert_state, opportunity, first["fingerprint"], first["severity"], now=100.0)

        duplicate = build_alert_decision(
            opportunity,
            alert_state,
            cooldown_sec=30,
            min_profit=2.0,
            alert_price_change_ratio=0.15,
            now=110.0,
        )
        self.assertFalse(duplicate["should_notify"])

        improved = dict(opportunity)
        improved["estimated_profit"] = 12.0
        improved["effective_spread"] = 0.012

        escalated = build_alert_decision(
            improved,
            alert_state,
            cooldown_sec=30,
            min_profit=2.0,
            alert_price_change_ratio=0.15,
            now=115.0,
        )
        self.assertTrue(escalated["should_notify"])
        self.assertEqual(escalated["severity"], "escalated")
