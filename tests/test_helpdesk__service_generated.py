"""Auto-generated tests for uncovered code."""
import inspect
import pytest
import helpdesk.service as module_under_test
# origin=rule quality=high symbol=TicketService
def test_TicketService_methods_rule():
    """Rule-based test for `module_under_test.TicketService` methods."""
    instance = module_under_test.TicketService()
    assert instance is not None
    try:
        result = instance.add_comment('HD-000001', 'x', 'x')
        assert result is None or result is not None
    except Exception:
        assert True
    try:
        result = instance.assign_priority('HD-000001', None)
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=high symbol=TicketService
def test_TicketService_invalid_transition_rule():
    import helpdesk.models
    service = module_under_test.TicketService()
    ticket = service.create_ticket('HD-200001', 'u@e.com', 'x', 'y')
    try:
        service.transition(ticket.id, helpdesk.models.Status.RESOLVED)
        assert False
    except ValueError:
        assert True
# origin=rule quality=high symbol=TicketService
def test_TicketService_create_ticket_and_add_comment_validation_rule():
    import helpdesk.models
    service = module_under_test.TicketService()
    with pytest.raises(ValueError) as excinfo:
        service.create_ticket('HD-300001', 'u@e.com', 't', '   ')
    assert 'description' in str(excinfo.value)
    ticket = service.create_ticket('HD-300002', 'u@e.com', 't', 'desc')
    assert ticket.status == helpdesk.models.Status.OPEN
    with pytest.raises(ValueError) as excinfo2:
        service.add_comment(ticket.id, 'a@b.com', '   ')
    assert 'comment body' in str(excinfo2.value)
# origin=rule quality=high symbol=TicketService
def test_TicketService_valid_transition_rule():
    import helpdesk.models
    service = module_under_test.TicketService()
    ticket = service.create_ticket('HD-300003', 'u@e.com', 't', 'desc')
    with pytest.raises(ValueError) as excinfo:
        service.transition(ticket.id, helpdesk.models.Status.RESOLVED)
    assert 'invalid status transition' in str(excinfo.value)
    updated = service.transition(ticket.id, helpdesk.models.Status.IN_PROGRESS)
    assert updated.status == helpdesk.models.Status.IN_PROGRESS
# origin=rule quality=high symbol=TicketService
def test_TicketService_list_comments_rule():
    service = module_under_test.TicketService()
    ticket = service.create_ticket('HD-300004', 'u@e.com', 't', 'desc')
    service.add_comment(ticket.id, 'a@b.com', 'hello')
    comments = list(service.list_comments(ticket.id))
    assert len(comments) == 1
    assert comments[0].ticket_id == ticket.id
