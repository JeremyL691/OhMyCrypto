"""Independent regression tests for F01-F08 defects defined in PROJECT_EXECUTION_GUIDE.md Section 2.2.

These tests assert correct behavior with independent expected oracles.
Each test specifically targets one of the reproduced defects:
- F01: Persistent event loop and client lifecycle across repeated acquisitions.
- F02: Complete capture, version, price/quantity-inclusive hashes, and exact replay equality.
- F03: Native IPC failure handling (must not silently substitute fake COMPLETE fixtures).
- F04: Disjoint shared depth consumption in split orders (one BTC cannot fund two 80-unit orders).
- F05: Official Kraken CRC32 book checksum example (must equal 3310070434).
- F06: Feature wiring: amount-grid calculations, split calculations, persistent quiet mode.
- F07: Verifier and bounded scenario gating (rejecting incomplete / zero-data runs).
- F08: Packaging and release configuration consistency (CLI architecture names and bundle flags).
"""

from decimal import Decimal
import zlib
import pytest

from ohmycrypto.domain.models import BookLevel, BookState, FeeProfile, Instrument
from ohmycrypto.domain.kernel import (
    evaluate_cross_venue_opportunity,
    KERNEL_VERSION,
)
from ohmycrypto.adapters.stream import OrderbookMaintenance
from ohmycrypto.adapters.kraken import (
    calculate_kraken_checksum,
    format_kraken_num,
)
from ohmycrypto.services.cost import CostAdvisorService


# ----------------------------------------------------------------------
# F05: Kraken official CRC32 checksum (expected: 3310070434)
# ----------------------------------------------------------------------

OFFICIAL_KRAKEN_ASKS = [
    ("45285.2", "0.00100000"),
    ("45286.4", "1.54571953"),
    ("45286.6", "1.54571109"),
    ("45289.6", "1.54560911"),
    ("45290.2", "0.15890660"),
    ("45291.8", "1.54553491"),
    ("45294.7", "0.04454749"),
    ("45296.1", "0.35380000"),
    ("45297.5", "0.09945542"),
    ("45299.5", "0.18772827"),
]

OFFICIAL_KRAKEN_BIDS = [
    ("45283.5", "0.10000000"),
    ("45283.4", "1.54582015"),
    ("45282.1", "0.10000000"),
    ("45281.0", "0.10000000"),
    ("45280.3", "1.54592586"),
    ("45279.0", "0.07990000"),
    ("45277.6", "0.03310103"),
    ("45277.5", "0.30000000"),
    ("45277.3", "1.54602737"),
    ("45276.6", "0.15445238"),
]

EXPECTED_OFFICIAL_KRAKEN_CRC32 = 3310070434


def test_f05_official_kraken_checksum_oracle():
    """F05: Kraken v2 documentation example must calculate exactly 3310070434."""
    asks = [BookLevel(price=Decimal(p), amount=Decimal(q)) for p, q in OFFICIAL_KRAKEN_ASKS]
    bids = [BookLevel(price=Decimal(p), amount=Decimal(q)) for p, q in OFFICIAL_KRAKEN_BIDS]

    computed = calculate_kraken_checksum(bids=bids, asks=asks)
    assert computed == EXPECTED_OFFICIAL_KRAKEN_CRC32, (
        f"Kraken checksum mismatch: got {computed}, expected {EXPECTED_OFFICIAL_KRAKEN_CRC32}"
    )


# ----------------------------------------------------------------------
# F04: Disjoint depth consumption in split orders
# ----------------------------------------------------------------------

def test_f04_split_orders_consume_disjoint_depth():
    """F04: 1.0 BTC of depth at price 100 cannot satisfy two 80-unit child orders."""
    advisor = CostAdvisorService()
    symbol = "BTC/USDT"
    inst = Instrument(
        symbol=symbol,
        base="BTC",
        quote="USDT",
        venue="coinbase",
        native_symbol="BTC-USDT",
    )
    instruments = {"coinbase": inst}
    fee_profiles = {"coinbase": FeeProfile(venue="coinbase", taker_rate=Decimal("0.0"))}

    # Only 1.0 BTC available on coinbase asks at price 100
    book = BookState(
        venue="coinbase",
        symbol=symbol,
        bids=(),
        asks=(BookLevel(price=Decimal("100.00"), amount=Decimal("1.00")),),
        snapshot_origin="test",
        applied_sequence=1,
        source_time_ms=1000,
        source_time_meaning="unknown",
        local_receipt_utc_ms=1000,
        local_receipt_mono_ns=1000,
    )
    books = {"coinbase": book}

    # Two child budgets of 80 USDT each targeting the SAME venue
    allocations = [("coinbase", Decimal("80.00")), ("coinbase", Decimal("80.00"))]

    eval_result = advisor.evaluate_split_order(
        side="buy",
        symbol=symbol,
        allocations=allocations,
        books=books,
        fee_profiles=fee_profiles,
        instruments=instruments,
    )

    # Invariant: Total acquired base across all children MUST NOT exceed total available depth (1.00 BTC)
    total_acquired_base = Decimal(eval_result["total_base"])
    assert total_acquired_base <= Decimal("1.00"), (
        f"Depth over-consumption! Acquired {total_acquired_base} BTC from a book with only 1.00 BTC"
    )
    assert eval_result["all_complete"] is False, (
        "Split order should NOT be marked all_complete when depth is exhausted for the second child"
    )


# ----------------------------------------------------------------------
# F02: Price and quantity changes must alter input hash
# ----------------------------------------------------------------------

def test_f02_price_quantity_changes_alter_input_hash():
    """F02: Changing book prices or quantities must change input_hash."""
    inst = Instrument(
        symbol="BTC/USDT",
        base="BTC",
        quote="USDT",
        venue="generic",
        native_symbol="BTC-USDT",
    )
    fee = FeeProfile(venue="generic", taker_rate=Decimal("0.001"))

    # Initial book with sell price 110
    book_buy = BookState(
        venue="cb",
        symbol="BTC/USDT",
        bids=(),
        asks=(BookLevel(price=Decimal("100.00"), amount=Decimal("1.0")),),
        snapshot_origin="snap",
        applied_sequence=1,
        source_time_ms=1000,
        source_time_meaning="unknown",
        local_receipt_utc_ms=1000,
        local_receipt_mono_ns=1000,
    )
    book_sell_110 = BookState(
        venue="kr",
        symbol="BTC/USDT",
        bids=(BookLevel(price=Decimal("110.00"), amount=Decimal("1.0")),),
        asks=(),
        snapshot_origin="snap",
        applied_sequence=1,
        source_time_ms=1000,
        source_time_meaning="unknown",
        local_receipt_utc_ms=1000,
        local_receipt_mono_ns=1000,
    )

    opp_110 = evaluate_cross_venue_opportunity(
        symbol="BTC/USDT",
        buy_book=book_buy,
        sell_book=book_sell_110,
        all_in_quote_budget=Decimal("50.00"),
        buy_fee_profile=fee,
        sell_fee_profile=fee,
        buy_instrument=inst,
        sell_instrument=inst,
    )

    # Changed book with sell price 120
    book_sell_120 = BookState(
        venue="kr",
        symbol="BTC/USDT",
        bids=(BookLevel(price=Decimal("120.00"), amount=Decimal("1.0")),),
        asks=(),
        snapshot_origin="snap",
        applied_sequence=1,
        source_time_ms=1000,
        source_time_meaning="unknown",
        local_receipt_utc_ms=1000,
        local_receipt_mono_ns=1000,
    )

    opp_120 = evaluate_cross_venue_opportunity(
        symbol="BTC/USDT",
        buy_book=book_buy,
        sell_book=book_sell_120,
        all_in_quote_budget=Decimal("50.00"),
        buy_fee_profile=fee,
        sell_fee_profile=fee,
        buy_instrument=inst,
        sell_instrument=inst,
    )

    assert opp_110.input_hash != opp_120.input_hash, (
        "input_hash must differ when sell price changes from 110 to 120!"
    )
    assert opp_110.net_profit_quote != opp_120.net_profit_quote


# ----------------------------------------------------------------------
# F01: Repeated acquisition loop pattern must not raise Event loop is closed
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_f01_persistent_event_loop_client_lifecycle():
    """F01: Persistent connector must survive repeated acquisitions on its loop."""
    from ohmycrypto.adapters.coinbase import CoinbaseConnector

    connector = CoinbaseConnector()
    # A persistent event loop and properly owned client lifecycle must allow repeated calls
    client1 = await connector._get_client()
    assert client1 is not None
    client2 = await connector._get_client()
    assert client1 is client2
    await connector.close()
    assert connector._ccxt_client is None


# ----------------------------------------------------------------------
# F03: Native IPC failure handling (must not substitute fake COMPLETE fixtures)
# ----------------------------------------------------------------------

def test_f03_sidecar_ipc_errors_surfaced_visibly():
    """F03: Sidecar dispatch must surface errors visibly with status='error'."""
    from ohmycrypto.interfaces.sidecar import SidecarEngine
    import io
    import sys

    engine = SidecarEngine()
    # Test invalid amount / invalid request handling
    captured_stdout = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured_stdout
    try:
        engine.handle_request({
            "id": "req_err_1",
            "action": "compare_costs",
            "payload": {"side": "invalid_side", "amount": "-500"},
        })
    finally:
        sys.stdout = old_stdout

    import json
    line = captured_stdout.getvalue().strip()
    resp = json.loads(line)
    assert resp["status"] == "error"
    assert "error" in resp
    assert resp["id"] == "req_err_1"


# ----------------------------------------------------------------------
# F06: Real amount grid calculations and persistent settings / Quiet Mode
# ----------------------------------------------------------------------

def test_f06_amount_grid_and_split_order_calculations():
    """F06: Amount grid outcomes must be computed dynamically, not hardcoded."""
    advisor = CostAdvisorService()
    symbol = "BTC/USDT"
    inst = Instrument(symbol=symbol, base="BTC", quote="USDT", venue="kraken", native_symbol="BTC-USDT")
    fee = FeeProfile(venue="kraken", taker_rate=Decimal("0.0025"))

    book = BookState(
        venue="kraken",
        symbol=symbol,
        bids=(),
        asks=(BookLevel(price=Decimal("80000.00"), amount=Decimal("0.5")),),
        snapshot_origin="test",
        applied_sequence=1,
        source_time_ms=1000,
        source_time_meaning="unknown",
        local_receipt_utc_ms=1000,
        local_receipt_mono_ns=1000,
    )

    grid = advisor.compute_amount_grid(
        side="buy",
        grid_amounts=[Decimal("100.00"), Decimal("100000.00")],
        symbol=symbol,
        books={"kraken": book},
        fee_profiles={"kraken": fee},
        instruments={"kraken": inst},
    )

    # 100 USDT should be completely filled
    res_100 = grid["100.00"][0]
    assert res_100["is_complete"] is True
    assert Decimal(res_100["acquired_base"]) > 0

    # 100,000 USDT budget exhausts 0.5 BTC depth (0.5 * 80000 = 40,000 max)
    res_huge = grid["100000.00"][0]
    assert res_huge["is_complete"] is False
    assert res_huge["rejection_reason"] == "insufficient_asks_depth"


def test_f06_persistent_settings_and_quiet_mode():
    """F06: Settings including Quiet Mode must be persisted and retrieved via sidecar."""
    from ohmycrypto.interfaces.sidecar import SidecarEngine

    engine = SidecarEngine()
    # Update settings with quiet_mode = True
    update_res = engine._action_update_settings({"quiet_mode": True, "retention_days": 14})
    assert update_res["settings"]["quiet_mode"] is True
    assert update_res["settings"]["retention_days"] == 14

    # Retrieve settings
    get_res = engine._action_get_settings({})
    assert get_res["settings"]["quiet_mode"] is True
    assert get_res["settings"]["retention_days"] == 14


# ----------------------------------------------------------------------
# F07: Verifier and bounded scenario gating (rejecting incomplete / zero-data)
# ----------------------------------------------------------------------

def test_f07_verifier_rejects_empty_manifest_and_zero_usable_data():
    """F07: Verifier must reject empty or zero-data manifests."""
    import subprocess
    import sys
    from pathlib import Path
    import tempfile
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        empty_manifest = Path(tmpdir) / "manifest.json"
        with open(empty_manifest, "w") as f:
            json.dump({
                "release_id": "test_empty",
                "version": "1.0.0",
                "artifacts": [],
            }, f)

        # Empty manifest with zero artifacts must fail with exit code != 0
        res = subprocess.run(
            [sys.executable, "scripts/release.py", "verify", "--manifest", str(empty_manifest)],
            capture_output=True,
            text=True,
        )
        assert res.returncode != 0, "Verifier must fail on empty manifest with no artifacts!"


# ----------------------------------------------------------------------
# F08: Release arch normalization and bundle configuration
# ----------------------------------------------------------------------

def test_f08_release_arch_normalization_and_bundle_config():
    """F08: Release script accepts x64 and maps to x86_64; bundle is active."""
    import subprocess
    import sys
    import json
    from pathlib import Path

    # Verify release.py accepts --arch x64 in help or CLI parser
    res = subprocess.run(
        [sys.executable, "scripts/release.py", "prepare", "--help"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "x64" in res.stdout or "x86_64" in res.stdout

    # Verify tauri.conf.json has bundle.active = true
    tauri_conf_path = Path("desktop/src-tauri/tauri.conf.json")
    with open(tauri_conf_path, "r") as f:
        conf = json.load(f)
    assert conf.get("bundle", {}).get("active") is True


