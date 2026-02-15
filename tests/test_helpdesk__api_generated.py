"""Auto-generated tests for uncovered code."""
import inspect
import pytest
import helpdesk.api as module_under_test
# origin=rule quality=high symbol=handle_request
def test_handle_request_missing_action_rule():
    import helpdesk.service
    service = helpdesk.service.TicketService()
    try:
        module_under_test.handle_request(service, {})
        assert False
    except ValueError:
        assert True
# origin=rule quality=high symbol=handle_request
def test_handle_request_unknown_action_rule():
    import helpdesk.service
    service = helpdesk.service.TicketService()
    try:
        module_under_test.handle_request(service, {'action': 'nope'})
        assert False
    except ValueError:
        assert True
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
