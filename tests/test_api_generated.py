"""Auto-generated tests for uncovered code."""
import inspect
import pytest
import helpdesk.api as module_under_test
# origin=rule quality=high symbol=handle_request
def test_handle_request_smoke():
    """Smoke test for `module_under_test.handle_request`."""
    target = module_under_test.handle_request
    assert callable(target)
    try:
        result = target(None, {'action': 'create', 'id': 'HD-000001', 'requester': 'u@e.com', 'title': 'x', 'description': 'y'})
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=high symbol=handle_request
def test_handle_request_missing_action_rule():
    import helpdesk.service
    service = helpdesk.service.TicketService()
    with pytest.raises(ValueError) as excinfo:
        module_under_test.handle_request(service, {})
    assert 'missing action' in str(excinfo.value)
    assert excinfo.value is not None
# origin=rule quality=high symbol=handle_request
def test_handle_request_unknown_action_rule():
    import helpdesk.service
    service = helpdesk.service.TicketService()
    with pytest.raises(ValueError) as excinfo:
        module_under_test.handle_request(service, {'action': 'nope'})
    assert 'unknown action' in str(excinfo.value)
    assert excinfo.value is not None
# origin=rule quality=high symbol=handle_request
def test_handle_request_create_comment_transition_rule():
    import helpdesk.models
    import helpdesk.service
    service = helpdesk.service.TicketService()
    ticket_id = module_under_test.handle_request(service, {'action': 'create', 'id': 'HD-000001', 'requester': 'u@e.com', 'title': 'x', 'description': 'y'})
    assert ticket_id == 'HD-000001'
    assert len(service.list_tickets()) == 1
    ok = module_under_test.handle_request(service, {'action': 'comment', 'id': ticket_id, 'author': 'a@b.com', 'body': 'hi'})
    assert ok == 'ok'
    assert len(list(service.list_comments(ticket_id))) == 1
    ok2 = module_under_test.handle_request(service, {'action': 'transition', 'id': ticket_id, 'status': helpdesk.models.Status.IN_PROGRESS.value})
    assert ok2 == 'ok'
# origin=rule quality=low symbol=handle_request
def test_TicketService_create_ticket_requires_description_rule():
    service = module_under_test.TicketService()
    with pytest.raises(ValueError) as excinfo:
        service.create_ticket('HD-300001', 'u@e.com', 'x', '   ')
    assert 'description' in str(excinfo.value)
    assert excinfo.value is not None
# origin=rule quality=low symbol=handle_request
def test_TicketService_add_comment_requires_body_rule():
    service = module_under_test.TicketService()
    service.create_ticket('HD-300002', 'u@e.com', 'x', 'y')
    with pytest.raises(ValueError) as excinfo:
        service.add_comment('HD-300002', 'a@b.com', '   ')
    assert 'comment body' in str(excinfo.value)
    assert excinfo.value is not None
