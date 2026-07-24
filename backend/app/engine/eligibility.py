"""
Deterministic Eligibility Engine. Owned by P2.
THIS IS THE SOURCE OF TRUTH. The LLM can never override it.

EXPOSES:  filter_eligible(products, intent) -> list[EligibleProduct]

Pure, deterministic functions: same input -> same output, ALWAYS.
No LLM calls in here, ever. This is what makes the assistant trustworthy.
"""
from app.contracts.models import EligibleProduct, Intent, Product


def _within_budget(p: Product, intent: Intent) -> bool:
    if intent.budget_monthly_max is None:
        return True
    # Only monthly-priced items (phones/plans) are budget-checked here.
    if p.price_monthly <= 0:
        return True
    return p.price_monthly <= intent.budget_monthly_max


def evaluate(p: Product, intent: Intent) -> EligibleProduct:
    """Run every rule against one product and record why it passed/failed."""
    reasons: list[str] = []
    failed: list[str] = []

    # Rule: in stock
    if p.in_stock and p.stock > 0:
        reasons.append("in_stock")
    else:
        failed.append("out_of_stock")

    # Rule: within budget
    if _within_budget(p, intent):
        reasons.append("within_budget")
    else:
        failed.append("over_budget")

    return EligibleProduct(
        product=p,
        eligible=len(failed) == 0,
        reasons=reasons,
        failed_rules=failed,
    )


def filter_eligible(products: list[Product], intent: Intent) -> list[EligibleProduct]:
    """Evaluate all candidates. Returns ALL (eligible flag set), so callers/receipts
    can see what was rejected and why."""
    return [evaluate(p, intent) for p in products]


def eligible_only(products: list[Product], intent: Intent) -> list[EligibleProduct]:
    return [e for e in filter_eligible(products, intent) if e.eligible]
