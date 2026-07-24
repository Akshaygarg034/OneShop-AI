"""
The pipeline orchestrator. Owned by P1.

This is the BACKBONE that ties all 4 slices together:
    intent (P1) -> retrieve (P2) -> filter_eligible (P2) -> recommend (P3) -> response

Right now it's a plain function calling each step. That's intentional for mock-first:
the whole app works today. P1's REAL job is to convert this into a LangGraph StateGraph
(nodes = steps, edges = flow, with a branch for clarification and retry). The node
functions stay the same - only the wiring changes.

GUARDRAIL enforced here: recommendations may only reference eligible product ids.
"""
import uuid

from app.agents.intent import extract_intent
from app.agents.profile import update_profile
from app.contracts.models import ChatResponse, Receipts
from app.engine.eligibility import filter_eligible
from app.recommend.recommender import recommend
from app.retrieval.retriever import retrieve


def run_pipeline(message: str, session, conversation_id: str) -> ChatResponse:
    # Each conversation is a separate thread with its own history for AI context.
    # Profile is global across conversations (accumulated learnings persist).
    conv_history = session.get_conversation(conversation_id)

    # 1. Understand + learn (P1)
    # Pass THIS thread's history (loaded fresh from the persisted session) so
    # multi-turn context survives restarts without bleeding across unrelated
    # conversation threads.
    intent = extract_intent(message, conv_history, session.profile)
    session.profile = update_profile(session.profile, message, intent)
    intent.profile = session.profile

    # 1a. Ask instead of guess (trust behaviour)
    if intent.clarification_needed:
        conv_history.append({"role": "user", "content": message})
        conv_history.append({"role": "assistant", "content": intent.clarification_question, "recommendations": []})
        return ChatResponse(
            reply_text=intent.clarification_question,
            recommendations=[],
            nba=[],
            cart=session.cart,
            receipts=Receipts(),
            conversation_id=conversation_id,
        )

    # 2. Find candidates (P2)
    candidates = retrieve(intent)

    # 3. Filter to what's actually offerable - SOURCE OF TRUTH (P2)
    evaluated = filter_eligible(candidates, intent)
    eligible = [e for e in evaluated if e.eligible]

    # 3a. Scope to what THIS turn actually asked for. retrieve() only softly
    # biases toward intent.product_types (a +2 score bump among several other
    # signals) - it never hard-filters. Without this, a session-wide learned
    # preference (e.g. "camera" from an earlier phone question) keeps
    # outscoring the very plans/accessories the user is asking about right
    # now, because rank_products()'s `preference` signal reads the whole
    # accumulated profile, not just this message. That produced the same 1-2
    # phones as the top pick regardless of what was actually asked. A budget
    # or feature mentioned earlier should keep biasing ranking WITHIN a
    # category; it should never hijack the category itself.
    if intent.product_types:
        scoped = [e for e in eligible if e.product.type.value in intent.product_types]
        if scoped:  # never narrow to nothing - fall back to the full set
            eligible = scoped

    # 4. Rank + explain + nudge (P3)
    recs, nba = recommend(eligible, session.profile, session.cart)

    # 4a. GUARDRAIL: the LLM can never introduce a product the engine rejected.
    eligible_ids = {e.product.id for e in eligible}
    recs = [r for r in recs if r.product_id in eligible_ids]

    # 5. Compose reply + receipts
    reply = _compose_reply(recs, eligible, intent)
    receipts = Receipts(
        retrieved_ids=[c.id for c in candidates],
        rules_fired=sorted({rule for e in evaluated for rule in (e.reasons + e.failed_rules)}),
        shown_ids=[r.product_id for r in recs],
    )

    # Record turn; persist recommendations so the frontend can restore product cards from history.
    conv_history.append({"role": "user", "content": message})
    conv_history.append({
        "role": "assistant",
        "content": reply,
        "recommendations": [r.model_dump() for r in recs],
    })

    return ChatResponse(
        reply_text=reply,
        recommendations=recs,
        nba=nba,
        cart=session.cart,
        receipts=receipts,
        conversation_id=conversation_id,
    )


def _compose_reply(recs, eligible, intent) -> str:
    if not eligible:
        # Brand-aware, honest refusal - the deterministic engine found nothing
        # offerable, and we say so rather than silently swapping in something else.
        subject = f"{intent.brand} option" if intent.brand else "option"
        budget = f" under €{int(intent.budget_monthly_max)}/mo" if intent.budget_monthly_max else ""
        return (
            f"I couldn't find an in-stock {subject}{budget} that fits. "
            "Want me to relax the budget, or show the closest alternatives?"
        )
    if not recs:
        return "I found some options but need a bit more detail to recommend the best one."
    lead = "Here's my top pick" if len(recs) == 1 else "Here are my top picks"
    return f"{lead} — {recs[0].why}"
