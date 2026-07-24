"""
Eval harness. Owned by P4.
This is your PROOF the system works - the answer to "how do you know it works?"

Run:  cd backend && python -m evals.run_evals

Each case sends a message and asserts a GROUNDED behaviour:
  - never recommends an out-of-stock / out-of-budget product
  - refuses / clarifies when it should
Add more cases as features land. Judges love this.
"""
from app.agents.graph import run_pipeline
from app.engine.eligibility import eligible_only
from app.retrieval.catalog import load_catalog
from app.session.store import Session


def _run(message: str) -> "ChatResponse":
    return run_pipeline(message, Session("eval"))


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("recommends something for a normal request")
def t1():
    r = _run("I need a phone under 40 euros with a good camera")
    assert r.recommendations, "expected at least one recommendation"


@case("never recommends an out-of-stock product")
def t2():
    r = _run("I want the iPhone 16 Pro")  # iphone16pro has stock 0 in seed data
    assert "phone_iphone16pro" not in [x.product_id for x in r.recommendations], \
        "recommended an out-of-stock product!"


@case("never recommends over budget")
def t3():
    r = _run("show me a phone under 10 euros a month")
    for rec in r.recommendations:
        prod = next(p for p in load_catalog() if p.id == rec.product_id)
        if prod.price_monthly > 0:
            assert prod.price_monthly <= 10, f"{prod.name} is over the 10 EUR budget"


@case("asks for clarification when too vague")
def t4():
    r = _run("something good")
    assert not r.recommendations and r.reply_text, "expected a clarification question"


@case("receipts are populated")
def t5():
    r = _run("phone with a camera")
    assert r.receipts.retrieved_ids, "receipts should record what was retrieved"


def main():
    passed = 0
    for name, fn in CASES:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}  ->  {e}")
        except Exception as e:  # noqa
            print(f"  ERROR {name}  ->  {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(CASES)} eval cases passed.")


if __name__ == "__main__":
    main()
