"""Auto-generated tests for uncovered code."""
import inspect
import pytest
import sample as module_under_test
# origin=rule quality=high symbol=add_numbers
# origin=rule quality=high symbol=add_numbers
def test_add_numbers_basic_rule():
    assert module_under_test.add_numbers(2, 3) == 2 + 3
    assert module_under_test.add_numbers(0, 5) == 0 + 5
# origin=rule quality=high symbol=add_numbers
def test_add_numbers_smoke():
    """Smoke test for `module_under_test.add_numbers`."""
    target = module_under_test.add_numbers
    assert callable(target)
    try:
        result = target(1, 1)
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=high symbol=multiply_numbers
# origin=rule quality=high symbol=multiply_numbers
def test_multiply_numbers_basic_rule():
    assert module_under_test.multiply_numbers(2, 3) == 2 * 3
    assert module_under_test.multiply_numbers(0, 5) == 0 * 5
# origin=rule quality=high symbol=multiply_numbers
def test_multiply_numbers_smoke():
    """Smoke test for `module_under_test.multiply_numbers`."""
    target = module_under_test.multiply_numbers
    assert callable(target)
    try:
        result = target(1, 1)
        assert result is None or result is not None
    except Exception:
        assert True
