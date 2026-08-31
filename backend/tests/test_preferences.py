from datetime import datetime, timedelta, timezone

from app.preferences.engine import apply_deltas, apply_event, decayed, merge
from app.preferences.models import Affinity, BudgetPreference, PreferenceDelta, Preferences


def test_budget_delta_sets_stated_budget():
    prefs = apply_deltas(Preferences(), [
        PreferenceDelta(target="budget", action="set", number_min=500, number_max=800, period="onetime"),
    ])
    assert prefs.budgets["any"].min == 500 and prefs.budgets["any"].max == 800
    assert prefs.budgets["any"].source == "stated"


def test_budget_is_per_category():
    prefs = apply_deltas(Preferences(), [
        PreferenceDelta(target="budget", action="set", key="smartphones", number_min=300, number_max=500),
    ])
    assert prefs.budgets["smartphones"].max == 500
    # A smartphone budget must not constrain other categories.
    assert prefs.budget_for("audio") is None
    assert prefs.budget_for("smartphones").max == 500

    # Retracting one category keeps the others.
    prefs = apply_deltas(prefs, [PreferenceDelta(target="budget", action="set", key="tablets", number_max=400)])
    prefs = apply_deltas(prefs, [PreferenceDelta(target="budget", action="retract", key="smartphones")])
    assert "smartphones" not in prefs.budgets and "tablets" in prefs.budgets

    # Retracting the general budget clears everything.
    prefs = apply_deltas(prefs, [PreferenceDelta(target="budget", action="retract", key="any")])
    assert prefs.budgets == {}


def test_legacy_global_budget_migrates():
    prefs = Preferences(**{"budget": {"min": 100, "max": 200, "period": "onetime", "source": "stated"}})
    assert prefs.budgets["any"].max == 200


def test_brand_exclude_and_retract():
    prefs = apply_deltas(Preferences(), [PreferenceDelta(target="brand", action="exclude", key="Apple")])
    assert prefs.hard_excluded_brands() == {"apple"}

    # Liking an excluded brand doesn't silently lift the exclusion...
    prefs = apply_deltas(prefs, [PreferenceDelta(target="brand", action="like", key="apple")])
    assert prefs.brands["apple"].hard

    # ...only an explicit retraction does.
    prefs = apply_deltas(prefs, [PreferenceDelta(target="brand", action="retract", key="apple")])
    assert "apple" not in prefs.brands


def test_attribute_and_product_deltas():
    prefs = apply_deltas(Preferences(), [
        PreferenceDelta(target="attribute", action="set", key="ram_gb", number_min=8),
        PreferenceDelta(target="attribute", action="set", key="color", values=["Black", "blue"]),
        PreferenceDelta(target="product", action="dislike", key="phone-x", reason="too expensive"),
    ])
    assert prefs.attributes["ram_gb"] == {"min": 8}
    assert prefs.attributes["color"] == {"values": ["black", "blue"]}
    assert prefs.rejected_products["phone-x"] == "too expensive"


def test_soft_affinities_decay_hard_exclusions_dont():
    old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    prefs = Preferences(brands={
        "samsung": Affinity(score=0.8, last_seen=old),
        "apple": Affinity(score=-1.0, hard=True, last_seen=old),
    })
    result = decayed(prefs)
    assert result.brands["samsung"].score < 0.15
    assert result.brands["apple"].score == -1.0 and result.brands["apple"].hard


def test_behavioral_events(product):
    prefs = apply_event(Preferences(), "cart_add", product)
    assert prefs.brands["samsung"].score > 0
    assert prefs.categories["smartphones"].score > 0

    prefs = apply_event(prefs, "purchase", product)
    assert prefs.brands["samsung"].score > 0.5
    inferred = prefs.budgets[product.category]
    assert inferred.source == "inferred"
    assert inferred.max == round(product.price_onetime * 1.5, 2)


def test_purchase_never_overrides_stated_budget(product):
    prefs = Preferences(budgets={product.category: BudgetPreference(max=500, source="stated")})
    prefs = apply_event(prefs, "purchase", product)
    assert prefs.budgets[product.category].max == 500
    assert prefs.budgets[product.category].source == "stated"


def test_merge_prefers_stated_budget_and_stronger_signals():
    user = Preferences(
        budgets={"any": BudgetPreference(max=900, source="inferred")},
        brands={"sony": Affinity(score=0.2)},
    )
    guest = Preferences(
        budgets={"any": BudgetPreference(min=500, max=800, source="stated")},
        brands={"sony": Affinity(score=0.7), "apple": Affinity(score=-1.0, hard=True)},
    )
    merged = merge(user, guest)
    assert merged.budgets["any"].source == "stated" and merged.budgets["any"].max == 800
    assert merged.brands["sony"].score == 0.7
    assert merged.brands["apple"].hard
