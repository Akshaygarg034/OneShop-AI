from app.contracts.models import AttributeConstraint, QueryFilters
from app.engine.eligibility import effective_filters, evaluate, filter_eligible
from app.preferences.models import Affinity, BudgetPreference, Preferences


def _filters(**kwargs) -> QueryFilters:
    return QueryFilters(**kwargs)


def test_budget_range(product):
    ok = evaluate(product, _filters(price_min=500, price_max=800, price_period="onetime"), Preferences())
    assert ok.eligible and "within_budget" in ok.reasons

    too_cheap = evaluate(product, _filters(price_min=700, price_max=900), Preferences())
    assert not too_cheap.eligible and "over_budget" in too_cheap.failed_rules

    too_expensive = evaluate(product, _filters(price_max=500), Preferences())
    assert not too_expensive.eligible


def test_budget_period_mismatch_skips_rule(product):
    # A monthly budget must not exclude one-time-priced devices.
    result = evaluate(product, _filters(price_max=20, price_period="monthly"), Preferences())
    assert result.eligible


def test_brand_include_exclude(product):
    assert evaluate(product, _filters(brands_include=["samsung"]), Preferences()).eligible
    assert not evaluate(product, _filters(brands_include=["apple"]), Preferences()).eligible
    excluded = evaluate(product, _filters(brands_exclude=["Samsung"]), Preferences())
    assert not excluded.eligible and "brand_excluded" in excluded.failed_rules


def test_color_filter(product):
    assert evaluate(product, _filters(colors=["black"]), Preferences()).eligible
    missing = evaluate(product, _filters(colors=["red"]), Preferences())
    assert not missing.eligible and "color_mismatch" in missing.failed_rules


def test_color_families_match_marketing_shades(product):
    # A "lemon" phone must be found when the user asks for yellow — and vice versa.
    product.colors = ["navy", "lilac", "lemon"]
    assert evaluate(product, _filters(colors=["yellow"]), Preferences()).eligible
    assert evaluate(product, _filters(colors=["blue"]), Preferences()).eligible
    assert evaluate(product, _filters(colors=["purple"]), Preferences()).eligible
    assert evaluate(product, _filters(colors=["lemon"]), Preferences()).eligible
    assert not evaluate(product, _filters(colors=["red"]), Preferences()).eligible

    product.colors = ["yellow"]
    assert evaluate(product, _filters(colors=["lemon"]), Preferences()).eligible


def test_attribute_constraints(product):
    gte = _filters(attributes=[AttributeConstraint(name="ram_gb", op="gte", number=8)])
    assert evaluate(product, gte, Preferences()).eligible

    gte_fail = _filters(attributes=[AttributeConstraint(name="ram_gb", op="gte", number=12)])
    result = evaluate(product, gte_fail, Preferences())
    assert not result.eligible and "attr_ram_gb_failed" in result.failed_rules

    eq = _filters(attributes=[AttributeConstraint(name="storage_gb", op="eq", number=128)])
    assert evaluate(product, eq, Preferences()).eligible

    os_in = _filters(attributes=[AttributeConstraint(name="os", op="in", values=["android"])])
    assert evaluate(product, os_in, Preferences()).eligible

    missing_attr = _filters(attributes=[AttributeConstraint(name="anc", op="eq", values=["true"])])
    assert not evaluate(product, missing_attr, Preferences()).eligible


def test_rating_stock_and_sale(product):
    assert evaluate(product, _filters(min_rating=4.3), Preferences()).eligible
    assert not evaluate(product, _filters(min_rating=4.8), Preferences()).eligible
    assert evaluate(product, _filters(on_sale_only=True), Preferences()).eligible

    product.stock = 0
    result = evaluate(product, _filters(), Preferences())
    assert not result.eligible and "out_of_stock" in result.failed_rules


def test_rejected_product(product):
    prefs = Preferences(rejected_products={product.id: "too expensive"})
    result = evaluate(product, _filters(), prefs)
    assert not result.eligible and "rejected_by_user" in result.failed_rules


def test_effective_filters_merges_hard_exclusions():
    prefs = Preferences(brands={"apple": Affinity(score=-1.0, hard=True)})
    merged = effective_filters(QueryFilters(), prefs)
    assert "apple" in merged.brands_exclude

    # An explicit ask for the excluded brand wins for this turn.
    merged = effective_filters(QueryFilters(brands_include=["Apple"]), prefs)
    assert "apple" not in merged.brands_exclude


def test_effective_filters_applies_stated_budget():
    prefs = Preferences(budgets={"any": BudgetPreference(min=500, max=800, period="onetime", source="stated")})
    merged = effective_filters(QueryFilters(), prefs)
    assert merged.price_min == 500 and merged.price_max == 800

    # This turn's explicit range wins over the stored budget.
    merged = effective_filters(QueryFilters(price_max=300), prefs)
    assert merged.price_max == 300 and merged.price_min is None

    # Inferred budgets (from purchases) never hard-filter.
    prefs.budgets["any"].source = "inferred"
    merged = effective_filters(QueryFilters(), prefs)
    assert merged.price_max is None


def test_effective_filters_budget_is_scoped_to_its_category():
    prefs = Preferences(budgets={
        "smartphones": BudgetPreference(min=300, max=500, period="onetime", source="stated"),
    })
    # Shopping smartphones (by category, subcategory, or type) — budget applies.
    for f in (QueryFilters(categories=["smartphones"]),
              QueryFilters(subcategories=["smartphone"]),
              QueryFilters(product_types=["phone"])):
        merged = effective_filters(f, prefs)
        assert merged.price_min == 300 and merged.price_max == 500

    # Shopping earbuds — the smartphone budget must NOT apply.
    merged = effective_filters(QueryFilters(subcategories=["earbuds"]), prefs)
    assert merged.price_min is None and merged.price_max is None

    # A general "any" budget does apply everywhere unless a category budget exists.
    prefs.budgets["any"] = BudgetPreference(max=1000, period="onetime", source="stated")
    merged = effective_filters(QueryFilters(subcategories=["earbuds"]), prefs)
    assert merged.price_max == 1000
    merged = effective_filters(QueryFilters(subcategories=["smartphone"]), prefs)
    assert merged.price_max == 500, "category budget wins over the general one"


def test_effective_filters_browse_all_skips_saved_budget():
    prefs = Preferences(
        budgets={"any": BudgetPreference(min=500, max=800, period="onetime", source="stated")},
        brands={"apple": Affinity(score=-1.0, hard=True)},
    )
    merged = effective_filters(QueryFilters(), prefs, browse_all=True)
    # "Show me ALL" browsing must not be narrowed by a remembered budget...
    assert merged.price_min is None and merged.price_max is None
    # ...but explicit hard rules (excluded brands) still hold.
    assert "apple" in merged.brands_exclude


def test_filter_eligible_keeps_rejects_with_reasons(product):
    results = filter_eligible([product], _filters(brands_include=["apple"]), Preferences())
    assert len(results) == 1 and not results[0].eligible
