"""Additional sample module for AI test runner."""


def divide_numbers(numerator: float, denominator: float) -> float:
    """Return numerator divided by denominator."""
    if denominator == 0:
        raise ValueError("denominator must not be zero")
    return numerator / denominator


def clamp(value: int, min_value: int, max_value: int) -> int:
    """Clamp value between min_value and max_value."""
    return max(min_value, min(max_value, value))


class Accumulator:
    def __init__(self, start: int = 0) -> None:
        self.total = start

    def add(self, amount: int) -> int:
        self.total += amount
        return self.total
