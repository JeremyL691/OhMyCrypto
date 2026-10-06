"""Base adapter interface and capability models for OhMyCrypto.

Follows Section 5 and Section 6.1 of PROJECT_EXECUTION_GUIDE.md:
- Explicit public venue metadata and capabilities
- Clock separation: source exchange clock vs local monotonic receipt
- Integrity contracts: sequence tracking, checksums, gap resync
- Degradation and health accounting
"""

from __future__ import annotations

import abc
from decimal import Decimal
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from ohmycrypto.domain.models import BookLevel, BookState, Instrument


@dataclass
class ConnectorHealth:
    """Live health and diagnostic telemetry for an exchange connector."""
    venue: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    sequence_gaps: int = 0
    checksum_failures: int = 0
    reconnect_count: int = 0
    last_success_mono_ns: int = 0
    last_error_mono_ns: int = 0
    last_error_msg: Optional[str] = None
    is_live: bool = True
    is_degraded: bool = False

    def record_success(self, mono_ns: int) -> None:
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0
        self.last_success_mono_ns = mono_ns
        if self.consecutive_failures < 3:
            self.is_degraded = False

    def record_failure(self, mono_ns: int, err_msg: str) -> None:
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.last_error_mono_ns = mono_ns
        self.last_error_msg = err_msg
        if self.consecutive_failures >= 3:
            self.is_degraded = True


class BaseSpotConnector(abc.ABC):
    """Abstract base class for spot market data connectors."""

    def __init__(self, venue: str):
        self.venue = venue
        self.health = ConnectorHealth(venue=venue)
        self._orderbooks: Dict[str, BookState] = {}

    @abc.abstractmethod
    async def fetch_markets(self) -> Dict[str, Instrument]:
        """Fetch supported spot instruments and trading limits."""
        raise NotImplementedError

    @abc.abstractmethod
    async def fetch_orderbook(self, symbol: str, depth: int = 20) -> BookState:
        """Fetch snapshot L2 orderbook via public REST endpoint."""
        raise NotImplementedError

    def get_orderbook(self, symbol: str) -> Optional[BookState]:
        """Get latest verified in-memory book state."""
        return self._orderbooks.get(symbol)

    def set_orderbook(self, symbol: str, state: BookState) -> None:
        self._orderbooks[symbol] = state
