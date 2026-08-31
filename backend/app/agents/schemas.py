"""Structured-output schema for the `understand` node."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.models import QueryFilters
from app.preferences.models import PreferenceDelta


class Understanding(BaseModel):
    """Everything the LLM extracts from one user message, in one call:
    intent, hard constraints for this turn, and durable preference changes."""
    intent: Literal["shopping", "greeting", "off_topic", "clarify", "preference_only", "cart_question"]
    semantic_query: str = ""
    filters: QueryFilters = Field(default_factory=QueryFilters)
    preference_deltas: list[PreferenceDelta] = Field(default_factory=list)
    clarification_question: str = ""
    stated_currency: str = ""  # e.g. "inr" when the user wrote Rs/₹ — amounts are read as EUR
    # True when the user asks for alternatives to what was just shown ("other than
    # this", "anything else?") — the engine then excludes recently shown products.
    exclude_shown: bool = False
    # How many results the user asked for: an explicit number ("show me 2"),
    # 0 when unspecified (server default applies).
    requested_count: int = 0
    # True for exhaustive browsing ("show me all/every tablet"). Shows the full
    # matching set (capped) and skips soft saved preferences like a remembered
    # budget — an explicit catalog listing must not be silently narrowed.
    wants_all: bool = False
