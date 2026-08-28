"""Outcome feedback and reallocation — the learning loop.

When a settlement outcome is recorded, five things happen in order:
    1. Update the buyer (avg delay, trend)
    2. Reprice affected invoices (re-assess through engine)
    3. Return or consume liquidity
    4. Adjust provider bid policy (segment learning rate)
    5. Compose summary_text (template-generated, no LLM)

Deep-copy the market first. apply_outcome returns a NEW market,
never mutates the input — this is what keeps the API stateless.

Owner: Person B
"""

from __future__ import annotations


def apply_outcome(
    match: dict,
    event: dict,
    market: dict,
) -> tuple[dict, dict]:
    """Apply a settlement outcome and return the updated market + delta.

    Args:
        match: the Match that settled/defaulted/was late
        event: { "outcome": str, "days_late": int }
        market: current MarketInput dict — NEVER MUTATED

    Returns:
        (updated_market, LearningDelta) — both new dicts.

    The LearningDelta (SCHEMA.md §4.7) is the entire payload for demo step 8.
    """
    raise NotImplementedError("Person B: implement apply_outcome()")
