"""
LangChain-compatible chat message history backed by the app's session store.

WHY THIS EXISTS
--------------
LangChain's BaseChatMessageHistory is the standard contract for "give me the
conversation so far as proper message objects". By implementing it against our
Supabase-backed session store we get two things for free:

  1. LangChain OpenAI calls receive proper HumanMessage / AIMessage objects
     (not a hand-rolled context string), so the model sees multi-turn context
     exactly as the API intends.

  2. History is durable across server restarts. The session is read fresh from
     Supabase on every request, so even if uvicorn crashes mid-conversation the
     next message arrives to a fully-populated history.  This is what "omnichannel
     continuity" means at the state layer: it's not about screen size, it's about
     the conversation surviving any device switch or service interruption.

USAGE (inside an agent function)
---------------------------------
    from app.agents.history import session_history

    msgs = session_history(session_id).messages   # list[BaseMessage] from Supabase
"""
from __future__ import annotations

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.session.store import store


# ── conversion helpers ────────────────────────────────────────────────────────

def to_lc_message(turn: dict) -> BaseMessage:
    """Convert a {role, content} session dict to a LangChain BaseMessage."""
    role = turn.get("role", "user")
    content = turn.get("content", "")
    if role == "assistant":
        return AIMessage(content=content)
    if role == "system":
        return SystemMessage(content=content)
    return HumanMessage(content=content)


def from_lc_message(msg: BaseMessage) -> dict:
    """Convert a LangChain BaseMessage back to a {role, content} session dict."""
    if isinstance(msg, AIMessage):
        return {"role": "assistant", "content": msg.content}
    if isinstance(msg, SystemMessage):
        return {"role": "system", "content": msg.content}
    return {"role": "user", "content": msg.content}


# ── BaseChatMessageHistory implementation ────────────────────────────────────

class SessionChatHistory(BaseChatMessageHistory):
    """LangChain history interface over the Supabase-backed session store.

    Reading  → loads session from Supabase, converts {role,content} dicts to
               LangChain message objects.
    Writing  → appends to the session and immediately persists to Supabase so
               history survives server restarts and is visible from any device
               sharing the same session_id.
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    @property
    def messages(self) -> list[BaseMessage]:
        session = store.get(self.session_id)
        return [to_lc_message(t) for t in session.history]

    def add_messages(self, messages: list[BaseMessage]) -> None:
        session = store.get(self.session_id)
        for msg in messages:
            session.history.append(from_lc_message(msg))
        store.save(session)

    def clear(self) -> None:
        session = store.get(self.session_id)
        session.history = []
        store.save(session)


def session_history(session_id: str) -> SessionChatHistory:
    """Factory — returns a SessionChatHistory for the given session."""
    return SessionChatHistory(session_id)
