"""Personal execution cost comparison, amount grid, inventory, and split order scenarios.

Follows Section 3.3 and R07 of PROJECT_EXECUTION_GUIDE.md:
- Multi-venue execution cost comparison (buy or sell)
- Explicit amount curve grid (100, 1000, 10000) preserving ineligible reasons
- Inventory feasibility tracking without blocking unconstrained comparisons
- Split-order scenarios consuming disjoint depth and applying per-child fixed fees
"""

from __future__ import annotations

from decimal import Decimal
import time
from typing import Any, Dict, List, Literal, Optional, Tuple

from ohmycrypto.domain.models import (
    BookLevel,
    BookState,
    FeeProfile,
    FillResult,
    Instrument,
)
from ohmycrypto.domain.kernel import (
    estimate_buy_fill,
    estimate_sell_fill,
)


def _consume_depth_buy(asks: Sequence[BookLevel], base_consumed: Decimal) -> List[BookLevel]:
    rem_asks: List[BookLevel] = []
    to_consume = base_consumed
    for lvl in asks:
        if to_consume <= Decimal("0"):
            rem_asks.append(lvl)
        elif lvl.amount <= to_consume:
            to_consume -= lvl.amount
        else:
            rem_asks.append(BookLevel(price=lvl.price, amount=lvl.amount - to_consume))
            to_consume = Decimal("0")
    return rem_asks


def _consume_depth_sell(bids: Sequence[BookLevel], base_consumed: Decimal) -> List[BookLevel]:
    rem_bids: List[BookLevel] = []
    to_consume = base_consumed
    for lvl in bids:
        if to_consume <= Decimal("0"):
            rem_bids.append(lvl)
        elif lvl.amount <= to_consume:
            to_consume -= lvl.amount
        else:
            rem_bids.append(BookLevel(price=lvl.price, amount=lvl.amount - to_consume))
            to_consume = Decimal("0")
    return rem_bids


class CostAdvisorService:
    """Evaluates and compares execution costs across venues and order scenarios."""

    def compare_single_amount(
        self,
        side: Literal["buy", "sell"],
        amount: Decimal,
        symbol: str,
        books: Dict[str, BookState],
        fee_profiles: Dict[str, FeeProfile],
        instruments: Dict[str, Instrument],
    ) -> List[Dict[str, Any]]:
        """Compare all-in execution cost across all provided venues."""
        results: List[Dict[str, Any]] = []

        for venue, book in books.items():
            fee = fee_profiles.get(venue, FeeProfile(venue=venue))
            inst = instruments.get(venue, Instrument(symbol, symbol.split("/")[0], symbol.split("/")[1], venue, symbol))

            if side == "buy":
                fill = estimate_buy_fill(
                    asks=book.asks,
                    all_in_quote_budget=amount,
                    fee_profile=fee,
                    instrument=inst,
                )
                results.append({
                    "venue": venue,
                    "side": "buy",
                    "budget": str(amount),
                    "units": inst.quote,
                    "is_complete": fill.is_complete,
                    "rejection_reason": fill.rejection_reason,
                    "acquired_base": str(fill.acquired_base),
                    "quote_spent": str(fill.quote_spent),
                    "fee_quote": str(fill.fee_quote),
                    "fee_base": str(fill.fee_base),
                    "residual_quote": str(fill.residual_quote),
                    "avg_price": str(fill.avg_price),
                    "levels_consumed": fill.levels_consumed,
                    "total_cost": str(fill.quote_spent + fill.fee_quote),
                })
            else:
                fill = estimate_sell_fill(
                    bids=book.bids,
                    available_base=amount,
                    fee_profile=fee,
                    instrument=inst,
                )
                results.append({
                    "venue": venue,
                    "side": "sell",
                    "base_amount": str(amount),
                    "units": inst.base,
                    "is_complete": fill.is_complete,
                    "rejection_reason": fill.rejection_reason,
                    "quote_received": str(fill.quote_received),
                    "fee_quote": str(fill.fee_quote),
                    "fee_base": str(fill.fee_base),
                    "residual_base": str(fill.residual_base),
                    "avg_price": str(fill.avg_price),
                    "levels_consumed": fill.levels_consumed,
                    "net_proceeds": str(fill.quote_received),
                })

        # Sort: for buy, descending by acquired_base (more base for same budget is best)
        # for sell, descending by net_proceeds (more quote proceeds is best)
        if side == "buy":
            results.sort(key=lambda r: Decimal(r["acquired_base"]) if r["is_complete"] else Decimal("-1"), reverse=True)
        else:
            results.sort(key=lambda r: Decimal(r["net_proceeds"]) if r["is_complete"] else Decimal("-1"), reverse=True)

        return results

    def compute_amount_grid(
        self,
        side: Literal["buy", "sell"],
        grid_amounts: List[Decimal],
        symbol: str,
        books: Dict[str, BookState],
        fee_profiles: Dict[str, FeeProfile],
        instruments: Dict[str, Instrument],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Compute execution costs across an amount grid (e.g. 100, 1000, 10000)."""
        grid_results: Dict[str, List[Dict[str, Any]]] = {}
        for amt in grid_amounts:
            res = self.compare_single_amount(
                side=side,
                amount=amt,
                symbol=symbol,
                books=books,
                fee_profiles=fee_profiles,
                instruments=instruments,
            )
            grid_results[str(amt)] = res
            grid_results[f"{amt:.2f}"] = res
        return grid_results

    def check_inventory_feasibility(
        self,
        side: Literal["buy", "sell"],
        venue: str,
        required_currency: str,
        required_amount: Decimal,
        user_balances: Optional[Dict[str, Dict[str, Decimal]]] = None,
    ) -> Dict[str, Any]:
        """Check user-entered inventory feasibility without blocking unconstrained comparisons."""
        if user_balances is None or venue not in user_balances or required_currency not in user_balances[venue]:
            return {
                "venue": venue,
                "currency": required_currency,
                "status": "UNKNOWN",
                "available_balance": None,
                "is_feasible": None,
                "shortfall": None,
            }

        bal = user_balances[venue][required_currency]
        is_feasible = bal >= required_amount
        shortfall = Decimal("0") if is_feasible else (required_amount - bal)

        return {
            "venue": venue,
            "currency": required_currency,
            "status": "FEASIBLE" if is_feasible else "INSUFFICIENT_FUNDS",
            "available_balance": str(bal),
            "is_feasible": is_feasible,
            "shortfall": str(shortfall),
        }

    def evaluate_split_order(
        self,
        side: Literal["buy", "sell"],
        symbol: str,
        allocations: List[Tuple[str, Decimal]],  # (venue, amount)
        books: Dict[str, BookState],
        fee_profiles: Dict[str, FeeProfile],
        instruments: Dict[str, Instrument],
    ) -> Dict[str, Any]:
        """Evaluate multi-child split order scenario consuming disjoint depth with per-child fees."""
        children: List[Dict[str, Any]] = []
        total_spent_or_received = Decimal("0")
        total_base_acquired_or_sold = Decimal("0")
        total_fees_quote = Decimal("0")
        total_fees_base = Decimal("0")
        all_complete = True

        # Track remaining available depth per venue so child orders consume disjoint depth
        venue_asks: Dict[str, Sequence[BookLevel]] = {
            venue: book.asks for venue, book in books.items()
        }
        venue_bids: Dict[str, Sequence[BookLevel]] = {
            venue: book.bids for venue, book in books.items()
        }

        for venue, child_amt in allocations:
            book = books.get(venue)
            fee = fee_profiles.get(venue, FeeProfile(venue=venue))
            inst = instruments.get(venue, Instrument(symbol, symbol.split("/")[0], symbol.split("/")[1], venue, symbol))

            if book is None:
                all_complete = False
                child_dto = {
                    "venue": venue,
                    "allocated_amount": str(child_amt),
                    "acquired_base": "0.00",
                    "quote_spent": "0.00",
                    "quote_received": "0.00",
                    "fee_quote": "0.00",
                    "is_complete": False,
                    "rejection_reason": "missing_book",
                    "error": "missing_book",
                }
                children.append(child_dto)
                continue

            if side == "buy":
                current_asks = venue_asks.get(venue, ())
                fill = estimate_buy_fill(current_asks, child_amt, fee, inst)
                fill_dict = fill.to_dict() if hasattr(fill, "to_dict") else asdict(fill)
                child_dto = {
                    "venue": venue,
                    "allocated_amount": str(child_amt),
                    "budget": str(child_amt),
                    "acquired_base": str(fill.acquired_base),
                    "quote_spent": str(fill.quote_spent),
                    "fee_quote": str(fill.fee_quote),
                    "is_complete": fill.is_complete,
                    "rejection_reason": fill.rejection_reason,
                    "fill": fill_dict,
                }
                children.append(child_dto)
                base_consumed = fill.acquired_base + fill.fee_base
                venue_asks[venue] = _consume_depth_buy(current_asks, base_consumed)

                total_spent_or_received += fill.quote_spent
                total_base_acquired_or_sold += fill.acquired_base
                total_fees_quote += fill.fee_quote
                total_fees_base += fill.fee_base
                if not fill.is_complete:
                    all_complete = False
            else:
                current_bids = venue_bids.get(venue, ())
                fill = estimate_sell_fill(current_bids, child_amt, fee, inst)
                fill_dict = fill.to_dict() if hasattr(fill, "to_dict") else asdict(fill)
                child_dto = {
                    "venue": venue,
                    "allocated_amount": str(child_amt),
                    "base_amount": str(child_amt),
                    "acquired_base": "0.00",
                    "quote_received": str(fill.quote_received),
                    "fee_quote": str(fill.fee_quote),
                    "is_complete": fill.is_complete,
                    "rejection_reason": fill.rejection_reason,
                    "fill": fill_dict,
                }
                children.append(child_dto)
                base_consumed = child_amt - fill.residual_base
                venue_bids[venue] = _consume_depth_sell(current_bids, base_consumed)

                total_spent_or_received += fill.quote_received
                total_base_acquired_or_sold += (child_amt - fill.residual_base - fill.fee_base)
                total_fees_quote += fill.fee_quote
                total_fees_base += fill.fee_base
                if not fill.is_complete:
                    all_complete = False

        effective_avg_price = Decimal("0")
        if total_base_acquired_or_sold > Decimal("0"):
            effective_avg_price = (total_spent_or_received / total_base_acquired_or_sold).quantize(Decimal("0.01"))

        return {
            "side": side,
            "symbol": symbol,
            "all_complete": all_complete,
            "total_base": str(total_base_acquired_or_sold),
            "total_spent_or_received": str(total_spent_or_received),
            "total_quote": str(total_spent_or_received),
            "total_fees_quote": str(total_fees_quote),
            "total_fees_base": str(total_fees_base),
            "effective_avg_price": str(effective_avg_price),
            "children": children,
            "child_results": children,
        }
