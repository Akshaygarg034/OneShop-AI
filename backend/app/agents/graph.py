"""The chat agent: a LangGraph StateGraph.

    load_context → understand → (route by intent)
        shopping        → retrieve → evaluate → rank → respond_shopping → persist
        greeting        → respond_greeting → persist
        off_topic       → respond_off_topic → persist
        clarify         → respond_clarify → persist
        preference_only → respond_preference → persist
        cart_question   → respond_cart → persist

Guardrail: recommendations can only reference products the deterministic
eligibility engine approved — enforced when ranking and re-checked before the
response is assembled.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agents import respond
from app.agents.schemas import Understanding
from app.agents.understand import understand
from app.config import get_settings
from app.contracts.models import (
    Cart,
    ChatResponse,
    EligibleProduct,
    Product,
    QueryFilters,
    Receipts,
    Recommendation,
)
from app.conversations.memory import index_message, recall, update_summary_if_due
from app.conversations.store import Message, conversation_store
from app.engine.eligibility import effective_filters, filter_eligible
from app.preferences.engine import apply_deltas, decayed
from app.preferences.models import Preferences
from app.preferences.store import preference_store
from app.recommend.recommender import recommend
from app.retrieval.retriever import retrieve
from app.session.store import session_store

logger = logging.getLogger(__name__)


class AgentState(TypedDict, total=False):
    session_id: str
    conversation_id: str
    message: str
    cart: Cart
    prefs: Preferences
    summary: str
    recent: list[Message]
    recall: list[str]
    recently_shown: list[str]
    understanding: Understanding
    filters: QueryFilters
    candidates: list[Product]
    evaluated: list[EligibleProduct]
    recommendations: list[Recommendation]
    products: list[Product]
    nba: list[str]
    reply: str
    receipts: Receipts
    all_seen: bool


async def _load_context(state: AgentState) -> AgentState:
    settings = get_settings()
    session_id = state["session_id"]
    conversation_id = state["conversation_id"]
    store = conversation_store()

    cart, prefs, meta = await asyncio.gather(
        session_store().get_cart(session_id),
        preference_store().get(session_id),
        store.get_meta(conversation_id),
    )

    recent: list[Message] = []
    summary = ""
    if meta is not None:
        recent = await store.recent(conversation_id, settings.history_window)
        summary = meta.summary

    # Products shown earlier in this thread (most recent last) — the deterministic
    # basis for "show me something other than these" requests.
    recently_shown: list[str] = []
    for m in recent:
        if m.role == "assistant":
            for rec in m.recommendations:
                pid = rec.get("product_id")
                if pid and pid not in recently_shown:
                    recently_shown.append(pid)

    # Semantic recall only pays off when there's history beyond the verbatim window.
    recalled: list[str] = []
    has_older_turns = meta is not None and meta.message_count > settings.history_window
    has_other_threads = meta is None and bool(await store.list_ids(session_id))
    if has_older_turns or has_other_threads:
        recalled = await recall(session_id, state["message"])

    return {
        "cart": cart, "prefs": prefs, "summary": summary,
        "recent": recent, "recall": recalled, "recently_shown": recently_shown,
    }


async def _understand(state: AgentState) -> AgentState:
    prefs = state["prefs"]
    understanding = await understand(
        state["message"], state["summary"], state["recent"], state["recall"], prefs,
    )
    prefs = apply_deltas(prefs, understanding.preference_deltas)
    filters = effective_filters(understanding.filters, prefs, browse_all=understanding.wants_all)
    return {"understanding": understanding, "prefs": prefs, "filters": filters}


def _route(state: AgentState) -> str:
    return state["understanding"].intent


async def _retrieve(state: AgentState) -> AgentState:
    candidates = await retrieve(state["filters"], state["understanding"].semantic_query)
    return {"candidates": candidates}


async def _evaluate(state: AgentState) -> AgentState:
    evaluated = filter_eligible(state["candidates"], state["filters"], state["prefs"])

    # "Show me something OTHER than these": drop products already shown in this
    # thread. Deterministic — the ids come from persisted turns, never the LLM.
    if state["understanding"].exclude_shown:
        shown = set(state.get("recently_shown", []))
        for e in evaluated:
            if e.product.id in shown:
                e.eligible = False
                e.failed_rules.append("already_shown")
    return {"evaluated": evaluated}


async def _rank(state: AgentState) -> AgentState:
    settings = get_settings()
    understanding = state["understanding"]
    evaluated = state["evaluated"]
    eligible = [e for e in evaluated if e.eligible]

    # "Show me others" when everything matching has already been shown: don't
    # dead-end — re-show the complete matching set and say so honestly.
    all_seen = False
    if not eligible and understanding.exclude_shown:
        rescued = [e for e in evaluated if e.failed_rules == ["already_shown"]]
        if rescued:
            for e in rescued:
                e.eligible = True
                e.failed_rules = []
            eligible = rescued
            all_seen = True

    requested = understanding.requested_count
    if all_seen or understanding.wants_all:
        count = min(max(len(eligible), 1), settings.max_recommendations)
    elif requested > 0:
        count = min(requested, settings.max_recommendations)
    else:
        count = settings.recommendation_count

    ranking_prefs = decayed(state["prefs"])
    recommendations, nba = await recommend(
        eligible, ranking_prefs, state["cart"], count=count,
        exhaustive=all_seen or understanding.wants_all or requested > 0,
    )

    # Guardrail: never surface a product the engine rejected.
    eligible_ids = {e.product.id for e in eligible}
    recommendations = [r for r in recommendations if r.product_id in eligible_ids]

    by_id = {e.product.id: e.product for e in eligible}
    products = [by_id[r.product_id] for r in recommendations]
    receipts = Receipts(
        retrieved_ids=[c.id for c in state["candidates"]],
        rules_fired=sorted({rule for e in evaluated for rule in (e.reasons + e.failed_rules)}),
        shown_ids=[r.product_id for r in recommendations],
    )
    return {
        "recommendations": recommendations, "products": products,
        "nba": nba, "receipts": receipts, "all_seen": all_seen,
    }


def _stream_handler(config: RunnableConfig) -> respond.StreamHandler:
    return (config.get("configurable") or {}).get("stream_handler")


async def _respond_shopping(state: AgentState, config: RunnableConfig) -> AgentState:
    stream = _stream_handler(config)
    recommendations = state["recommendations"]
    if not recommendations:
        reply = respond.no_results_reply(state["understanding"], state["evaluated"])
        if stream:
            await stream(reply)
        return {"reply": reply}
    if state.get("all_seen"):
        reply = respond.all_seen_reply(len(recommendations))
        if stream:
            await stream(reply)
        return {"reply": reply}
    products = {p.id: p for p in state["products"]}
    reply = await respond.compose_shopping_reply(
        state["message"], state["understanding"], recommendations, products, state["prefs"], stream,
    )
    return {"reply": reply}


async def _static_reply(state: AgentState, config: RunnableConfig, reply: str) -> AgentState:
    stream = _stream_handler(config)
    if stream:
        await stream(reply)
    return {"reply": reply}


async def _respond_greeting(state: AgentState, config: RunnableConfig) -> AgentState:
    return await _static_reply(state, config, respond.GREETING_REPLY)


async def _respond_off_topic(state: AgentState, config: RunnableConfig) -> AgentState:
    return await _static_reply(state, config, respond.OFF_TOPIC_REPLY)


async def _respond_clarify(state: AgentState, config: RunnableConfig) -> AgentState:
    question = state["understanding"].clarification_question or (
        "Could you tell me a bit more — what type of product, and roughly what budget?"
    )
    return await _static_reply(state, config, question)


async def _respond_preference(state: AgentState, config: RunnableConfig) -> AgentState:
    reply = respond.preference_only_reply(state["prefs"], state["understanding"])
    return await _static_reply(state, config, reply)


async def _respond_cart(state: AgentState, config: RunnableConfig) -> AgentState:
    return await _static_reply(state, config, respond.cart_question_reply(state["cart"]))


async def _persist(state: AgentState) -> AgentState:
    session_id = state["session_id"]
    conversation_id = state["conversation_id"]
    store = conversation_store()

    reply = state.get("reply", "")
    nba = state.get("nba", [])
    # Nudges are shown to the user, so they're stored as part of the assistant turn —
    # a follow-up "yes" must be resolvable against them.
    assistant_content = reply + (("\n\n" + "\n".join(nba)) if nba else "")
    rec_dumps = [r.model_dump() for r in state.get("recommendations", [])]

    user_msg = await store.append(session_id, conversation_id, "user", state["message"])
    assistant_msg = await store.append(
        session_id, conversation_id, "assistant", assistant_content, rec_dumps,
    )
    await preference_store().save(session_id, state["prefs"])

    # Non-critical long-term-memory work happens off the request path.
    # It needs the full stack (Qdrant + OpenAI), which memory-backend runs don't have.
    if get_settings().uses_supabase:
        asyncio.create_task(index_message(user_msg))
        asyncio.create_task(index_message(assistant_msg))
        asyncio.create_task(update_summary_if_due(conversation_id))
    return {}


def _build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("load_context", _load_context)
    graph.add_node("understand", _understand)
    graph.add_node("retrieve", _retrieve)
    graph.add_node("evaluate", _evaluate)
    graph.add_node("rank", _rank)
    graph.add_node("respond_shopping", _respond_shopping)
    graph.add_node("respond_greeting", _respond_greeting)
    graph.add_node("respond_off_topic", _respond_off_topic)
    graph.add_node("respond_clarify", _respond_clarify)
    graph.add_node("respond_preference", _respond_preference)
    graph.add_node("respond_cart", _respond_cart)
    graph.add_node("persist", _persist)

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "understand")
    graph.add_conditional_edges("understand", _route, {
        "shopping": "retrieve",
        "greeting": "respond_greeting",
        "off_topic": "respond_off_topic",
        "clarify": "respond_clarify",
        "preference_only": "respond_preference",
        "cart_question": "respond_cart",
    })
    graph.add_edge("retrieve", "evaluate")
    graph.add_edge("evaluate", "rank")
    graph.add_edge("rank", "respond_shopping")
    for node in ("respond_shopping", "respond_greeting", "respond_off_topic",
                 "respond_clarify", "respond_preference", "respond_cart"):
        graph.add_edge(node, "persist")
    graph.add_edge("persist", END)
    return graph.compile()


_agent = _build_graph()


async def run_turn(
    session_id: str,
    message: str,
    conversation_id: str,
    stream_handler: respond.StreamHandler = None,
) -> ChatResponse:
    """Execute one chat turn and assemble the API response."""
    state: AgentState = {
        "session_id": session_id,
        "conversation_id": conversation_id,
        "message": message,
    }
    config: RunnableConfig = {"configurable": {"stream_handler": stream_handler}}
    final = await _agent.ainvoke(state, config)
    return ChatResponse(
        reply_text=final.get("reply", ""),
        recommendations=final.get("recommendations", []),
        products=final.get("products", []),
        nba=final.get("nba", []),
        cart=final["cart"],
        receipts=final.get("receipts", Receipts()),
        conversation_id=conversation_id,
    )
