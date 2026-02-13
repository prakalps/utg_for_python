"""Complex example module for the AI test runner.

This module is intentionally pure-Python and IO-free, but contains:
- branching logic
- dataclasses
- validation + exceptions
- a small stateful service class
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping


@dataclass(frozen=True)
class LineItem:
    sku: str
    quantity: int
    unit_price: float

    def total(self) -> float:
        if self.quantity < 0:
            raise ValueError("quantity must be non-negative")
        if self.unit_price < 0:
            raise ValueError("unit_price must be non-negative")
        return float(self.quantity) * float(self.unit_price)


@dataclass(frozen=True)
class DiscountRule:
    sku: str
    percent_off: float


def compute_subtotal(items: Iterable[LineItem]) -> float:
    subtotal = 0.0
    for item in items:
        subtotal += item.total()
    return round(subtotal, 2)


def apply_discounts(items: Iterable[LineItem], rules: Iterable[DiscountRule]) -> float:
    rules_by_sku = {rule.sku: rule for rule in rules}
    total = 0.0
    for item in items:
        line_total = item.total()
        rule = rules_by_sku.get(item.sku)
        if rule is not None:
            if rule.percent_off < 0 or rule.percent_off > 100:
                raise ValueError("percent_off must be between 0 and 100")
            line_total *= (100.0 - rule.percent_off) / 100.0
        total += line_total
    return round(total, 2)


def compute_tax(amount: float, region: str) -> float:
    if amount < 0:
        raise ValueError("amount must be non-negative")

    region = region.upper().strip()
    if region == "US":
        rate = 0.07
    elif region == "EU":
        rate = 0.20
    elif region == "IN":
        rate = 0.18
    else:
        rate = 0.0

    return round(amount * rate, 2)


def compute_total(
    items: Iterable[LineItem],
    rules: Iterable[DiscountRule],
    region: str,
) -> float:
    discounted = apply_discounts(items, rules)
    tax = compute_tax(discounted, region)
    return round(discounted + tax, 2)


class OrderIdGenerator:
    def __init__(self, prefix: str = "ORD") -> None:
        self.prefix = prefix
        self._counter = 0

    def next_id(self, today: date | None = None) -> str:
        self._counter += 1
        d = today or date.today()
        return f"{self.prefix}-{d.strftime('%Y%m%d')}-{self._counter:06d}"


class Inventory:
    def __init__(self, stock_by_sku: Mapping[str, int] | None = None) -> None:
        self._stock = dict(stock_by_sku or {})

    def reserve(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        available = self._stock.get(sku, 0)
        if available < qty:
            raise ValueError("insufficient stock")
        self._stock[sku] = available - qty

    def available(self, sku: str) -> int:
        return int(self._stock.get(sku, 0))
