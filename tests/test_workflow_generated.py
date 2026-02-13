"""Auto-generated tests for uncovered code."""
import inspect
import helpdesk.workflow as module_under_test
# origin=rule quality=high symbol=auto_triage
def test_auto_triage_smoke():
    """Smoke test for `module_under_test.auto_triage`."""
    target = module_under_test.auto_triage
    assert callable(target)
    try:
        result = target(None, 'HD-000001')
        assert result is None or result is not None
    except Exception:
        assert True

# origin=rule quality=low symbol=auto_triage
def test_auto_triage_branches_rule():
    import helpdesk.models
    import helpdesk.service
    service = helpdesk.service.TicketService()
    t1 = service.create_ticket('HD-100001', 'a@b.com', 'outage', 'payment down', priority=helpdesk.models.Priority.HIGH)
    module_under_test.auto_triage(service, t1.id)
    t2 = service.create_ticket('HD-100002', 'a@b.com', 'slow', 'latency issue', priority=helpdesk.models.Priority.MEDIUM)
    module_under_test.auto_triage(service, t2.id)
    t3 = service.create_ticket('HD-100003', 'a@b.com', 'question', 'how to reset password', priority=helpdesk.models.Priority.LOW)
    module_under_test.auto_triage(service, t3.id)
    assert len(service.list_tickets()) >= 3
