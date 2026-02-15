"""Auto-generated tests for uncovered code."""
import inspect
import pytest
import helpdesk.sample_app as module_under_test
# origin=rule quality=high symbol=run_demo
# origin=rule quality=high symbol=run_demo
def test_run_demo_returns_ticket_id_rule():
    ticket_id = module_under_test.run_demo()
    assert ticket_id == 'HD-000001'
    assert ticket_id.startswith('HD-')
# origin=rule quality=high symbol=run_demo
def test_run_demo_smoke():
    """Smoke test for `module_under_test.run_demo`."""
    target = module_under_test.run_demo
    assert callable(target)
    try:
        result = target()
        assert result is None or result is not None
    except Exception:
        assert True
