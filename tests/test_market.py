import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market import (  # noqa: E402
    fetch_prices,
    initialize_exchange_health,
    update_exchange_health,
    validate_exchange_names,
)


class FakeTickerExchange:
    def __init__(self, ticker=None, error=None):
        self.ticker = ticker
        self.error = error

    async def fetch_ticker(self, symbol):
        if self.error is not None:
            raise self.error
        return self.ticker


class MarketTests(unittest.IsolatedAsyncioTestCase):
    def test_validate_exchange_names_rejects_unknown_values(self):
        invalid = validate_exchange_names(["binance", "definitely_not_real"])
        self.assertEqual(invalid, ["definitely_not_real"])

    async def test_fetch_prices_keeps_successes_when_one_exchange_fails(self):
        exchanges = {
            "binance": FakeTickerExchange(
                {
                    "bid": 100.0,
                    "ask": 101.0,
                    "last": 100.5,
                    "timestamp": 1_700_000_000_000,
                }
            ),
            "okx": FakeTickerExchange(error=RuntimeError("boom")),
        }

        prices, results = await fetch_prices(exchanges, "BTC/USDT")

        self.assertEqual(set(prices.keys()), {"binance"})
        self.assertEqual(len(results), 2)
        failed = [item for item in results if item["error"] is not None]
        self.assertEqual(failed[0]["name"], "okx")

    def test_update_exchange_health_marks_exchange_degraded_after_repeated_failures(self):
        health = initialize_exchange_health(["binance", "okx"])
        results = [
            {"name": "binance", "error": None, "latency_ms": 10.0, "price": {}},
            {
                "name": "okx",
                "error": "RuntimeError: boom",
                "latency_ms": 20.0,
                "price": None,
            },
        ]

        update_exchange_health(health, results, max_consecutive_errors=2, now=100.0)
        self.assertFalse(health["okx"]["degraded"])
        self.assertEqual(health["okx"]["consecutive_errors"], 1)

        update_exchange_health(health, results, max_consecutive_errors=2, now=110.0)
        self.assertTrue(health["okx"]["degraded"])
        self.assertEqual(health["okx"]["consecutive_errors"], 2)

        success_results = [
            {"name": "okx", "error": None, "latency_ms": 5.0, "price": {}},
        ]
        update_exchange_health(health, success_results, max_consecutive_errors=2, now=120.0)
        self.assertFalse(health["okx"]["degraded"])
        self.assertEqual(health["okx"]["consecutive_errors"], 0)
