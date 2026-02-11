"""Auto-generated tests for uncovered code."""
import inspect
import sample

def test_add_numbers_smoke():
    """Smoke test for `sample.add_numbers`."""
    target = sample.add_numbers
    assert callable(target)
    assert len(inspect.signature(target).parameters) >= 1
