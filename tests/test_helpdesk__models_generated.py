"""Auto-generated tests for uncovered code."""
import inspect
import pytest
import helpdesk.models as module_under_test
# origin=rule quality=high symbol=Priority
def test_Priority_enum_rule():
    """Rule-based test for `module_under_test.Priority` enum."""
    instance = module_under_test.Priority.LOW
    assert instance is not None
    assert instance.value is not None
# origin=rule quality=high symbol=Status
def test_Status_enum_rule():
    """Rule-based test for `module_under_test.Status` enum."""
    instance = module_under_test.Status.OPEN
    assert instance is not None
    assert instance.value is not None
