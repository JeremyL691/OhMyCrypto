"""Unit tests for exchange connectors, orderbook reconstruction, and checksum integrity."""

from decimal import Decimal
import pytest
import zlib

from ohmycrypto.adapters.base import ConnectorHealth
from ohmycrypto.adapters.kraken import (
    KrakenConnector,
    calculate_kraken_checksum,
    format_kraken_num,
)
from ohmycrypto.domain.models import BookLevel, BookState


def test_kraken_num_formatting():
    """Verify format_kraken_num removes '.' and strips leading zeroes per Kraken v2 spec."""
    assert format_kraken_num(Decimal("45285.2")) == "452852"
    assert format_kraken_num(Decimal("0.00100000")) == "100000"
    assert format_kraken_num("0.00100000") == "100000"
    assert format_kraken_num(Decimal("0")) == "0"


def test_calculate_kraken_checksum():
    """Verify CRC32 checksum matches manual calculation."""
    bids = [
        BookLevel(price=Decimal("50000.00"), amount=Decimal("1.5")),
        BookLevel(price=Decimal("49990.00"), amount=Decimal("2.0")),
    ]
    asks = [
        BookLevel(price=Decimal("50010.00"), amount=Decimal("0.8")),
        BookLevel(price=Decimal("50020.00"), amount=Decimal("1.2")),
    ]
    # Asks first (low to high): 5001000 + 8 + 5002000 + 12
    # Then Bids (high to low): 5000000 + 15 + 4999000 + 20
    expected_str = "50010008500200012500000015499900020"
    expected_crc = zlib.crc32(expected_str.encode("utf-8"))

    crc = calculate_kraken_checksum(bids, asks)
    assert crc == expected_crc


def test_kraken_delta_update_and_truncation():
    """Verify applying deltas correctly inserts, updates, deletes, and sorts orderbook."""
    connector = KrakenConnector()
    initial_bids = (
        BookLevel(price=Decimal("100.0"), amount=Decimal("1.0")),
        BookLevel(price=Decimal("99.0"), amount=Decimal("2.0")),
    )
    initial_asks = (
        BookLevel(price=Decimal("101.0"), amount=Decimal("1.5")),
        BookLevel(price=Decimal("102.0"), amount=Decimal("3.0")),
    )
    book = BookState("kraken", "TEST/USD", initial_bids, initial_asks, "test", 10, None, "unknown", 1000, 1000)
    connector.set_orderbook("TEST/USD", book)
    connector._last_sequence["TEST/USD"] = 10

    # Apply delta: update ask 101.0 to 2.5, delete bid 99.0 (amount=0), add new best bid at 100.5
    bid_deltas = [(Decimal("99.0"), Decimal("0")), (Decimal("100.5"), Decimal("0.5"))]
    ask_deltas = [(Decimal("101.0"), Decimal("2.5"))]

    updated = connector.apply_delta_update(
        symbol="TEST/USD",
        bid_deltas=bid_deltas,
        ask_deltas=ask_deltas,
        sequence_num=11,
        max_depth=5,
    )

    assert len(updated.bids) == 2
    assert updated.bids[0].price == Decimal("100.5")
    assert updated.bids[0].amount == Decimal("0.5")
    assert updated.bids[1].price == Decimal("100.0")

    assert len(updated.asks) == 2
    assert updated.asks[0].price == Decimal("101.0")
    assert updated.asks[0].amount == Decimal("2.5")


def test_kraken_sequence_gap_detected():
    """Verify sequence gap raises ValueError and flags connector as degraded."""
    connector = KrakenConnector()
    book = BookState("kraken", "TEST/USD", (), (), "test", 10, None, "unknown", 1000, 1000)
    connector.set_orderbook("TEST/USD", book)
    connector._last_sequence["TEST/USD"] = 10

    # Sequence jumps from 10 to 12 (missing 11)
    with pytest.raises(ValueError, match="Sequence gap on TEST/USD"):
        connector.apply_delta_update("TEST/USD", (), (), sequence_num=12)

    assert connector.health.sequence_gaps == 1
    assert connector.health.is_degraded is True


def test_kraken_checksum_mismatch_detected():
    """Verify checksum mismatch raises error and records health failure."""
    connector = KrakenConnector()
    initial_bids = (BookLevel(price=Decimal("100.0"), amount=Decimal("1.0")),)
    initial_asks = (BookLevel(price=Decimal("101.0"), amount=Decimal("1.0")),)
    book = BookState("kraken", "TEST/USD", initial_bids, initial_asks, "test", 10, None, "unknown", 1000, 1000)
    connector.set_orderbook("TEST/USD", book)
    connector._last_sequence["TEST/USD"] = 10

    # Provide an intentional bogus checksum
    with pytest.raises(ValueError, match="Kraken checksum mismatch"):
        connector.apply_delta_update(
            "TEST/USD",
            (),
            (),
            sequence_num=11,
            expected_checksum=99999999,
        )

    assert connector.health.checksum_failures == 1
    assert connector.health.is_degraded is True


def test_connector_health_degradation_on_consecutive_failures():
    """Verify connector health transitions to degraded after 3 consecutive errors."""
    health = ConnectorHealth(venue="test_venue")
    assert health.is_degraded is False

    health.record_failure(1000, "error 1")
    assert health.consecutive_failures == 1
    assert health.is_degraded is False

    health.record_failure(2000, "error 2")
    assert health.consecutive_failures == 2
    assert health.is_degraded is False

    health.record_failure(3000, "error 3")
    assert health.consecutive_failures == 3
    assert health.is_degraded is True

    # Recovery on success
    health.record_success(4000)
    assert health.consecutive_failures == 0
    assert health.is_degraded is False
