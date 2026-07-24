"""
Seeds a repeatable demo session. Owned by P4.

Runs the exact demo script's opening turns through the REAL pipeline (not fake
data) so the session that's on screen during the demo is one we've already
verified works, end to end. Also prints the handoff URL so the "switch to
mobile" beat of the demo is a copy-paste, not something typed live.

Run:  cd backend && python -m evals.seed_demo
Then open the frontend with the printed URL (?session=demo).

Safe to re-run: it just replays the same messages into the same session_id.
"""
from app.agents.graph import run_pipeline
from app.session.store import store

DEMO_SESSION_ID = "demo"

# Mirrors PROJECT_OVERVIEW.md section 12 (demo script) / section 9 (scenarios A-D).
SCRIPT = [
    "I need a phone under 40 euros a month, I take a lot of photos and travel around Europe",
    "actually, can you get me an iPhone 16 Pro for 20 euros a month?",   # trust moment: refuses
    "I don't want Samsung though",                                       # personalization signal
]


def seed() -> None:
    session = store.get(DEMO_SESSION_ID)
    print(f"Seeding session '{DEMO_SESSION_ID}' with {len(SCRIPT)} scripted turns...\n")

    for i, message in enumerate(SCRIPT, 1):
        response = run_pipeline(message, session)
        store.save(session)
        print(f"[turn {i}] you: {message}")
        print(f"          bot: {response.reply_text}")
        if response.recommendations:
            names = ", ".join(r.product_id for r in response.recommendations)
            print(f"          shown: {names}")
        print()

    # Pre-add a phone + case so the cart / free-shipping nudge is visible immediately.
    store.add_to_cart(DEMO_SESSION_ID, "phone_pixel8")
    store.add_to_cart(DEMO_SESSION_ID, "accessory_case")
    cart_state = store.cart_summary(DEMO_SESSION_ID)
    print(f"Cart seeded: {cart_state['item_count']} item(s), "
          f"one-time €{cart_state['onetime_total']}, monthly €{cart_state['monthly_total']}")
    print(f"  {cart_state['shipping_note']}")

    print("\nOpen the app pointed at this session:")
    print(f"  Web    : http://localhost:5173/?session={DEMO_SESSION_ID}")
    print(f"  Mobile : http://localhost:5173/?session={DEMO_SESSION_ID}&channel=mobile")
    print("\nSession store backend in use:", store.backend_name)


if __name__ == "__main__":
    seed()
