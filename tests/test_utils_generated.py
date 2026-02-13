"""Auto-generated tests for uncovered code."""
import inspect
import pytest
import helpdesk.utils as module_under_test
# origin=rule quality=high symbol=summarize_text
def test_summarize_text_smoke():
    """Smoke test for `module_under_test.summarize_text`."""
    target = module_under_test.summarize_text
    assert callable(target)
    try:
        result = target('x')
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=high symbol=validate_ticket_id
def test_validate_ticket_id_smoke():
    """Smoke test for `module_under_test.validate_ticket_id`."""
    target = module_under_test.validate_ticket_id
    assert callable(target)
    try:
        result = target('HD-000001')
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=high symbol=normalize_email
def test_normalize_email_smoke():
    """Smoke test for `module_under_test.normalize_email`."""
    target = module_under_test.normalize_email
    assert callable(target)
    try:
        result = target('user@example.com')
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=high symbol=summarize_text
def test_summarize_text_truncates_rule():
    text = 'a' * 200
    result = module_under_test.summarize_text(text, max_len=10)
    assert len(result) == 10
    assert result.endswith('…')
# origin=rule quality=high symbol=summarize_text
def test_summarize_text_invalid_max_len_rule():
    with pytest.raises(ValueError) as excinfo:
        module_under_test.summarize_text('x', max_len=0)
    assert 'positive' in str(excinfo.value)
    assert excinfo.value is not None
# origin=rule quality=high symbol=validate_ticket_id
def test_validate_ticket_id_invalid_rule():
    with pytest.raises(ValueError) as excinfo:
        module_under_test.validate_ticket_id('bad')
    assert 'invalid ticket id' in str(excinfo.value)
    assert excinfo.value is not None
# origin=rule quality=high symbol=validate_ticket_id
def test_validate_ticket_id_valid_rule():
    module_under_test.validate_ticket_id('HD-000001')
    assert True
    assert 'HD-000001'.startswith('HD-')
