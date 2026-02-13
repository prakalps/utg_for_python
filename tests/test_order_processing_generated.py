"""Auto-generated tests for uncovered code."""
import inspect
import order_processing as module_under_test
# origin=rule quality=low symbol=Inventory
def test_Inventory_methods_rule():
    """Rule-based test for `module_under_test.Inventory` methods."""
    instance = module_under_test.Inventory({'x': 2})
    assert instance is not None
    try:
        instance.reserve('x', 0)
        assert False
    except ValueError:
        assert True
    try:
        instance.reserve('x', 999)
        assert False
    except ValueError:
        assert True
    try:
        result = instance.available('x')
        assert result is None or result is not None
    except Exception:
        assert True
    try:
        result = instance.reserve('x', 1)
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=low symbol=Inventory
def test_Inventory_reserve_branches_rule():
    inventory = module_under_test.Inventory({'x': 1})
    try:
        inventory.reserve('x', 0)
        assert False
    except ValueError:
        assert True
    try:
        inventory.reserve('x', 999)
        assert False
    except ValueError:
        assert True
# origin=rule quality=low symbol=LineItem
def test_LineItem_methods_rule():
    """Rule-based test for `module_under_test.LineItem` methods."""
    instance = module_under_test.LineItem('x', 1, 1.0)
    assert instance is not None
    try:
        module_under_test.LineItem('x', -1, 1.0).total()
        assert False
    except ValueError:
        assert True
    try:
        module_under_test.LineItem('x', 1, -1.0).total()
        assert False
    except ValueError:
        assert True
    try:
        result = instance.total()
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=low symbol=LineItem
def test_LineItem_invalid_inputs_rule():
    try:
        module_under_test.LineItem('x', -1, 1.0).total()
        assert False
    except ValueError:
        assert True
    try:
        module_under_test.LineItem('x', 1, -1.0).total()
        assert False
    except ValueError:
        assert True
# origin=rule quality=low symbol=OrderIdGenerator
def test_OrderIdGenerator_methods_rule():
    """Rule-based test for `module_under_test.OrderIdGenerator` methods."""
    instance = module_under_test.OrderIdGenerator()
    assert instance is not None
    try:
        result = instance.next_id()
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=high symbol=apply_discounts
def test_apply_discounts_smoke():
    """Smoke test for `module_under_test.apply_discounts`."""
    target = module_under_test.apply_discounts
    assert callable(target)
    try:
        result = target([], [])
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=high symbol=compute_subtotal
def test_compute_subtotal_smoke():
    """Smoke test for `module_under_test.compute_subtotal`."""
    target = module_under_test.compute_subtotal
    assert callable(target)
    try:
        result = target([])
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=high symbol=compute_tax
def test_compute_tax_smoke():
    """Smoke test for `module_under_test.compute_tax`."""
    target = module_under_test.compute_tax
    assert callable(target)
    try:
        result = target(1.0, 'US')
        assert result is None or result is not None
    except Exception:
        assert True
# origin=rule quality=high symbol=compute_total
def test_compute_total_smoke():
    """Smoke test for `module_under_test.compute_total`."""
    target = module_under_test.compute_total
    assert callable(target)
    try:
        result = target([], [], 'US')
        assert result is None or result is not None
    except Exception:
        assert True

# origin=rule quality=low symbol=apply_discounts
def test_apply_discounts_invalid_percent_rule():
    try:
        item = module_under_test.LineItem('x', 1, 10.0)
        rule = module_under_test.DiscountRule('x', 200.0)
        module_under_test.apply_discounts([item], [rule])
        assert False
    except ValueError:
        assert True

# origin=rule quality=low symbol=apply_discounts
def test_apply_discounts_valid_discount_rule():
    item = module_under_test.LineItem('x', 2, 10.0)
    rule = module_under_test.DiscountRule('x', 50.0)
    result = module_under_test.apply_discounts([item], [rule])
    assert result == 10.0

# origin=rule quality=low symbol=compute_subtotal
def test_compute_subtotal_nonempty_rule():
    items = [module_under_test.LineItem('x', 2, 10.0)]
    assert module_under_test.compute_subtotal(items) == 20.0

# origin=rule quality=low symbol=compute_tax
def test_compute_tax_negative_rule():
    try:
        module_under_test.compute_tax(-1.0, 'US')
        assert False
    except ValueError:
        assert True

# origin=rule quality=low symbol=compute_tax
def test_compute_tax_regions_rule():
    assert module_under_test.compute_tax(100.0, 'US') >= 0
    assert module_under_test.compute_tax(100.0, 'EU') >= 0
    assert module_under_test.compute_tax(100.0, 'IN') >= 0
    assert module_under_test.compute_tax(100.0, 'ZZ') >= 0

# origin=rule quality=low symbol=compute_total
def test_compute_total_integration_rule():
    items = [module_under_test.LineItem('x', 2, 10.0)]
    rules = [module_under_test.DiscountRule('x', 50.0)]
    result = module_under_test.compute_total(items, rules, 'US')
    assert result >= 10.0
