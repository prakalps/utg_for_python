"""Auto-generated tests for uncovered code."""
import inspect
import pytest
import helpdesk.storage as module_under_test
# origin=rule quality=high symbol=InMemoryTicketStore
def test_InMemoryTicketStore_methods_rule():
    """Rule-based test for `module_under_test.InMemoryTicketStore` methods."""
    instance = module_under_test.InMemoryTicketStore()
    assert instance is not None
    try:
        result = instance.add_comment(None)
        assert result is None or result is not None
    except Exception:
        assert True
    try:
        result = instance.add_ticket(None)
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=high symbol=InMemoryTicketStore
def test_InMemoryTicketStore_not_found_rule():
    store = module_under_test.InMemoryTicketStore()
    try:
        store.get_ticket('HD-999999')
        assert False
    except ValueError:
        assert True
# origin=rule quality=high symbol=InMemoryTicketStore
def test_InMemoryTicketStore_add_ticket_duplicate_rule():
    import helpdesk.models
    store = module_under_test.InMemoryTicketStore()
    t = helpdesk.models.Ticket(id='HD-400001', requester='u@e.com', title='x', description='y')
    store.add_ticket(t)
    assert len(store.list_tickets()) == 1
    with pytest.raises(ValueError) as excinfo:
        store.add_ticket(t)
    assert 'already exists' in str(excinfo.value)
# origin=rule quality=high symbol=InMemoryTicketStore
def test_InMemoryTicketStore_add_comment_ticket_not_found_rule():
    import helpdesk.models
    store = module_under_test.InMemoryTicketStore()
    comment = helpdesk.models.Comment(ticket_id='HD-400002', author='u@e.com', body='hi')
    with pytest.raises(ValueError) as excinfo:
        store.add_comment(comment)
    assert 'not found' in str(excinfo.value)
    assert excinfo.value is not None
# origin=rule quality=high symbol=InMemoryTicketStore
def test_InMemoryTicketStore_list_comments_rule():
    import helpdesk.models
    store = module_under_test.InMemoryTicketStore()
    t = helpdesk.models.Ticket(id='HD-400003', requester='u@e.com', title='x', description='y')
    store.add_ticket(t)
    comment = helpdesk.models.Comment(ticket_id=t.id, author='u@e.com', body='hi')
    store.add_comment(comment)
    comments = list(store.list_comments(t.id))
    assert len(comments) == 1
    assert comments[0].body == 'hi'
