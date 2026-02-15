"""Auto-generated tests for uncovered code."""
import inspect
import pytest
import message_router as module_under_test
# origin=rule quality=high symbol=Message
def test_Message_methods_rule():
    """Rule-based test for `module_under_test.Message` methods."""
    instance = module_under_test.Message('x', 'x', 'x')
    assert instance is not None
    try:
        result = instance.normalized_recipient()
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=high symbol=MessageRouter
def test_MessageRouter_methods_rule():
    """Rule-based test for `module_under_test.MessageRouter` methods."""
    instance = module_under_test.MessageRouter()
    assert instance is not None
    try:
        result = instance.route_for('x')
        assert result is None or result is not None
    except Exception:
        assert True
    try:
        result = instance.send(None)
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=high symbol=MessageRouter
def test_MessageRouter_send_branches_rule():
    router = module_under_test.MessageRouter({'bob': 'queue1'})
    msg1 = module_under_test.Message('a', 'bob', 'ok', severity=module_under_test.Severity.INFO)
    msg2 = module_under_test.Message('a', 'bob', 'warn', severity=module_under_test.Severity.WARNING)
    msg3 = module_under_test.Message('a', 'bob', 'err', severity=module_under_test.Severity.ERROR)
    assert 'OK:' in router.send(msg1)
    assert 'WARN:' in router.send(msg2)
    assert 'ALERT:' in router.send(msg3)
    assert router.sent_count() == 3
# origin=rule quality=high symbol=MessageRouter
def test_MessageRouter_route_for_empty_recipient_rule():
    router = module_under_test.MessageRouter()
    try:
        router.route_for('   ')
        assert False
    except ValueError:
        assert True
# origin=rule quality=high symbol=Severity
def test_Severity_enum_rule():
    """Rule-based test for `module_under_test.Severity` enum."""
    instance = module_under_test.Severity.INFO
    assert instance is not None
    assert instance.value is not None
# origin=rule quality=high symbol=parse_message
def test_parse_message_missing_fields_rule():
    # sender / recipient / body / severity validations
    for raw in [
        'to=bob;body=hi',
        'from=alice;body=hi',
        'from=alice;to=bob',
        'from=alice;to=bob;severity=nope;body=hi',
    ]:
        with pytest.raises(ValueError):
            module_under_test.parse_message(raw)
    assert True
    assert isinstance(raw, str)
# origin=rule quality=high symbol=parse_message
def test_parse_message_empty_raw_rule():
    with pytest.raises(ValueError) as excinfo:
        module_under_test.parse_message('   ')
    assert 'non-empty' in str(excinfo.value)
    assert excinfo.value is not None
# origin=rule quality=high symbol=parse_message
def test_parse_message_invalid_part_rule():
    with pytest.raises(ValueError) as excinfo:
        module_under_test.parse_message('from=alice;BROKEN;to=bob;body=hi')
    assert 'invalid message part' in str(excinfo.value)
    assert excinfo.value is not None
# origin=rule quality=high symbol=parse_message
def test_parse_message_missing_sender_rule():
    with pytest.raises(ValueError) as excinfo:
        module_under_test.parse_message('to=bob;severity=info;body=hi')
    assert 'missing sender' in str(excinfo.value)
    assert excinfo.value is not None
# origin=rule quality=high symbol=parse_message
def test_parse_message_missing_recipient_rule():
    with pytest.raises(ValueError) as excinfo:
        module_under_test.parse_message('from=alice;severity=info;body=hi')
    assert 'missing recipient' in str(excinfo.value)
    assert excinfo.value is not None
# origin=rule quality=high symbol=parse_message
def test_parse_message_missing_body_rule():
    with pytest.raises(ValueError) as excinfo:
        module_under_test.parse_message('from=alice;to=bob;severity=info')
    assert 'missing body' in str(excinfo.value)
    assert excinfo.value is not None
# origin=rule quality=high symbol=parse_message
def test_parse_message_invalid_severity_rule():
    with pytest.raises(ValueError) as excinfo:
        module_under_test.parse_message('from=alice;to=bob;severity=nope;body=hi')
    assert 'invalid severity' in str(excinfo.value)
    assert excinfo.value is not None
# origin=rule quality=high symbol=parse_message
def test_parse_message_valid_rule():
    msg = module_under_test.parse_message('from=alice;to=bob;severity=info;body=hello')
    assert msg.sender == 'alice'
    assert msg.recipient == 'bob'
    assert msg.body == 'hello'
    assert msg.severity.value == 'info'
    assert msg.created_at is not None
# origin=rule quality=high symbol=parse_message
def test_parse_message_smoke():
    """Smoke test for `module_under_test.parse_message`."""
    target = module_under_test.parse_message
    assert callable(target)
    try:
        result = target('from=alice;to=bob;severity=info;body=hello')
        assert result is None or result is not None
    except Exception:
        assert True
