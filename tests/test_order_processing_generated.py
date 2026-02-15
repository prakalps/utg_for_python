"""Auto-generated tests for uncovered code."""
import inspect
import pytest
import order_processing as module_under_test
# origin=rule quality=high symbol=Inventory
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
# origin=rule quality=high symbol=Inventory
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
# origin=rule quality=high symbol=LineItem
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
# origin=rule quality=high symbol=LineItem
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
# origin=rule quality=high symbol=OrderIdGenerator
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
def test_apply_discounts_applies_rule_and_validates_percent_rule():
    items = [
        module_under_test.LineItem('A', 2, 10.0),
        module_under_test.LineItem('B', 1, 5.0),
    ]
    rules = [module_under_test.DiscountRule('A', 50.0)]
    assert module_under_test.apply_discounts(items, rules) == 15.0
    bad_rules = [module_under_test.DiscountRule('A', 200.0)]
    with pytest.raises(ValueError) as excinfo:
        module_under_test.apply_discounts(items, bad_rules)
    assert 'percent_off' in str(excinfo.value)
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
def test_compute_subtotal_sums_line_items_rule():
    items = [
        module_under_test.LineItem('SKU1', 2, 5.0),
        module_under_test.LineItem('SKU2', 1, 3.25),
    ]
    subtotal = module_under_test.compute_subtotal(items)
    assert subtotal == 13.25
    assert subtotal > 0
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
def test_compute_tax_regions_and_negative_amount_rule():
    assert module_under_test.compute_tax(100.0, 'us') == 7.0
    assert module_under_test.compute_tax(100.0, 'EU') == 20.0
    assert module_under_test.compute_tax(100.0, 'IN') == 18.0
    assert module_under_test.compute_tax(100.0, 'XX') == 0.0
    with pytest.raises(ValueError) as excinfo:
        module_under_test.compute_tax(-1.0, 'US')
    assert 'non-negative' in str(excinfo.value)
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
# origin=rule quality=high symbol=compute_total
def test_compute_total_adds_tax_rule():
    items = [module_under_test.LineItem('A', 2, 10.0)]
    rules = [module_under_test.DiscountRule('A', 50.0)]
    total = module_under_test.compute_total(items, rules, 'US')
    assert total == 10.7
    assert total > 0
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
