"""Domain models and data contracts for OhMyCrypto.

Follows Section 5 of PROJECT_EXECUTION_GUIDE.md:
- Typed immutable structures
- Strict Decimal precision for prices, amounts, fees, and results
- Rejection of NaN / Infinity / boolean-as-number
- Complete separation of local monotonic, local UTC, and exchange clocks
"""

from __future__ import annotations

import decimal
from decimal import Decimal
import hashlib
import json
import math
from typing import Any, Dict, List, Literal, Optional, Tuple
from dataclasses import asdict, dataclass, field


def decimal_validator(val: Any, field_name: str, allow_zero: bool = True, allow_negative: bool = False) -> Decimal:
    """Validate and convert to finite Decimal."""
    if isinstance(val, bool):
        raise ValueError(f"{field_name} must be a number, not boolean")
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            raise ValueError(f"{field_name} cannot be NaN or Infinity")
        val = str(val)
    elif isinstance(val, int):
        val = str(val)
    elif not isinstance(val, (str, Decimal)):
        raise TypeError(f"{field_name} must be Decimal, str, or int, got {type(val).__name__}")

    try:
        d = Decimal(str(val))
    except (decimal.InvalidOperation, ValueError) as err:
        raise ValueError(f"{field_name} is not a valid decimal: {val}") from err

    if not d.is_finite():
        raise ValueError(f"{field_name} must be finite")
    if not allow_zero and not allow_negative and d <= Decimal("0"):
        raise ValueError(f"{field_name} must be positive, got {d}")
    if not allow_negative and d < Decimal("0"):
        raise ValueError(f"{field_name} must be non-negative, got {d}")
    if not allow_zero and d == Decimal("0"):
        raise ValueError(f"{field_name} must be positive, got {d}")
    return d


class DecimalJSONEncoder(json.JSONEncoder):
    """JSON Encoder that converts Decimal to string, serializes dataclasses/DTOs, and forbids non-finite floats."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if hasattr(obj, "to_dict") and callable(obj.to_dict):
            return obj.to_dict()
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        return super().default(obj)


def dumps_canonical_json(data: Any) -> str:
    """Canonical JSON string with sorted keys and string decimals."""
    return json.dumps(data, cls=DecimalJSONEncoder, sort_keys=True, separators=(",", ":"))


def compute_sha256(data: Any) -> str:
    """Compute sha256 hash of canonical JSON."""
    encoded = dumps_canonical_json(data).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class Instrument:
    """Spot instrument definition."""
    symbol: str
    base: str
    quote: str
    venue: str
    native_symbol: str
    price_precision: int = 8
    amount_precision: int = 8
    price_increment: Decimal = Decimal("0.00000001")
    amount_increment: Decimal = Decimal("0.00000001")
    min_amount: Decimal = Decimal("0.0001")
    min_cost: Decimal = Decimal("1.0")
    capability_version: str = "1.0.0"

    def __post_init__(self):
        if not self.symbol or "/" not in self.symbol:
            raise ValueError(f"Invalid canonical symbol: {self.symbol}")
        if not self.base or not self.quote:
            raise ValueError("Instrument base and quote must not be empty")
        if self.base == self.quote:
            raise ValueError(f"Base and quote cannot be identical: {self.base}")
        decimal_validator(self.price_increment, "price_increment", allow_zero=False)
        decimal_validator(self.amount_increment, "amount_increment", allow_zero=False)
        decimal_validator(self.min_amount, "min_amount", allow_zero=False)
        decimal_validator(self.min_cost, "min_cost", allow_zero=True)


@dataclass(frozen=True)
class CaptureEnvelope:
    """Metadata wrapper for acquired market messages."""
    session_epoch: str
    capture_seq: int
    adapter: str
    channel: str
    source_time_ms: Optional[int]
    source_time_meaning: Literal["last_trade", "book_update", "unknown"]
    local_receipt_utc_ms: int
    local_receipt_mono_ns: int
    request_interval_ms: Optional[float]
    raw_hash: str


@dataclass(frozen=True)
class BookLevel:
    """Single orderbook price and amount level."""
    price: Decimal
    amount: Decimal

    def __post_init__(self):
        p = decimal_validator(self.price, "price", allow_zero=False)
        a = decimal_validator(self.amount, "amount", allow_zero=False)
        object.__setattr__(self, "price", p)
        object.__setattr__(self, "amount", a)


@dataclass(frozen=True)
class BookState:
    """Coherent, validated orderbook state."""
    venue: str
    symbol: str
    bids: Tuple[BookLevel, ...]
    asks: Tuple[BookLevel, ...]
    snapshot_origin: str
    applied_sequence: Optional[int]
    source_time_ms: Optional[int]
    source_time_meaning: Literal["last_trade", "book_update", "unknown"]
    local_receipt_utc_ms: int
    local_receipt_mono_ns: int
    quality_status: Literal["clean", "resynced", "degraded", "stale"] = "clean"
    checksum: Optional[str] = None

    def __post_init__(self):
        if not self.venue or not self.symbol:
            raise ValueError("BookState must have non-empty venue and symbol")
        for i in range(len(self.bids) - 1):
            if self.bids[i].price < self.bids[i + 1].price:
                raise ValueError(f"Unsorted bids on {self.venue} {self.symbol}: {self.bids[i].price} < {self.bids[i + 1].price}")
        for i in range(len(self.asks) - 1):
            if self.asks[i].price > self.asks[i + 1].price:
                raise ValueError(f"Unsorted asks on {self.venue} {self.symbol}: {self.asks[i].price} > {self.asks[i + 1].price}")
        if len(self.bids) > 0 and len(self.asks) > 0:
            best_bid = self.bids[0].price
            best_ask = self.asks[0].price
            if best_ask < best_bid:
                raise ValueError(f"Crossed orderbook on {self.venue} {self.symbol}: ask {best_ask} < bid {best_bid}")


@dataclass(frozen=True)
class FeeProfile:
    """Fee schedule for a specific venue and product."""
    venue: str
    maker_rate: Decimal = Decimal("0.0015")
    taker_rate: Decimal = Decimal("0.0025")
    fixed_fee: Decimal = Decimal("0.0")
    fee_currency: str = "QUOTE"  # "QUOTE", "BASE", or exact ISO currency
    charged_on: Literal["quote", "base"] = "quote"
    source: str = "default_tier"
    as_of_utc_ms: int = 0
    is_override: bool = False
    is_known: bool = True

    def __post_init__(self):
        m = decimal_validator(self.maker_rate, "maker_rate", allow_zero=True)
        t = decimal_validator(self.taker_rate, "taker_rate", allow_zero=True)
        f = decimal_validator(self.fixed_fee, "fixed_fee", allow_zero=True)
        object.__setattr__(self, "maker_rate", m)
        object.__setattr__(self, "taker_rate", t)
        object.__setattr__(self, "fixed_fee", f)


@dataclass(frozen=True)
class FillResult:
    """Deterministic fill outcome from walking orderbook levels."""
    side: Literal["buy", "sell"]
    requested_amount: Decimal
    acquired_base: Decimal
    quote_spent: Decimal
    quote_received: Decimal
    avg_price: Decimal
    fee_quote: Decimal
    fee_base: Decimal
    residual_quote: Decimal
    residual_base: Decimal
    levels_consumed: int
    is_complete: bool
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "side": self.side,
            "requested_amount": str(self.requested_amount),
            "acquired_base": str(self.acquired_base),
            "quote_spent": str(self.quote_spent),
            "quote_received": str(self.quote_received),
            "avg_price": str(self.avg_price),
            "fee_quote": str(self.fee_quote),
            "fee_base": str(self.fee_base),
            "residual_quote": str(self.residual_quote),
            "residual_base": str(self.residual_base),
            "levels_consumed": self.levels_consumed,
            "is_complete": self.is_complete,
            "rejection_reason": self.rejection_reason,
        }


@dataclass(frozen=True)
class OpportunityResult:
    """Calculated economic evaluation of cross-venue opportunity."""
    symbol: str
    buy_venue: str
    sell_venue: str
    budget_amount: Decimal
    budget_units: str
    buy_fill: FillResult
    sell_fill: FillResult
    net_profit_quote: Decimal
    effective_spread: Decimal
    midpoint_price: Decimal
    is_positive: bool
    is_eligible: bool
    eligibility_reasons: Tuple[str, ...]
    input_hash: str
    config_hash: str
    kernel_version: str = "1.0.0"
    result_hash: str = ""


@dataclass(frozen=True)
class DecisionEvent:
    """Persisted opportunity decision with follow-up status."""
    event_id: str
    episode_id: str
    route_key: str
    timestamp_utc_ms: int
    opportunity: OpportunityResult
    follow_up_500ms: Optional[str] = None  # "persisted", "failed", "unknown"
    follow_up_1s: Optional[str] = None
    follow_up_3s: Optional[str] = None
    continuous_persistence_status: Optional[str] = None
    notification_state: str = "unnotified"


@dataclass(frozen=True)
class DiagnosticFinding:
    """Market data quality incident or warning."""
    finding_id: str
    connector: str
    channel: str
    fault_class: str
    trigger: str
    severity: Literal["warning", "error", "critical"]
    timestamp_utc_ms: int
    raw_evidence: Dict[str, Any]
    is_recovered: bool = False
    recovery_timestamp_utc_ms: Optional[int] = None


@dataclass(frozen=True)
class NotificationRecord:
    """Outbox notification item."""
    notification_id: str
    event_id: str
    episode_id: str
    route_key: str
    mode: Literal["audio", "speech", "quiet"]
    state: Literal["pending", "delivering", "delivered", "failed", "suppressed"]
    decision_utc_ms: int
    enqueue_utc_ms: int
    delivery_utc_ms: Optional[int] = None
    attempts: int = 0
    last_error: Optional[str] = None
    suppression_reason: Optional[str] = None
