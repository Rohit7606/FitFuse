"""Market simulator — the single public entry point for market/.

Pure and deterministic, same rules as engine. Never mutate market.

Owner: Person B
Reviewer: Person A
"""

from __future__ import annotations


def generate_offers(
    invoice_id: str,
    market: dict,
    assessment: dict,
    scenario: object | None = None,
) -> list[dict]:
    """Have all eligible provider agents generate competing offers.

    Returns:
        List of Offer dicts per SCHEMA.md §4.5.
    """
    raise NotImplementedError("Person B: implement generate_offers()")


def clear(
    invoice_ids: list[str],
    market: dict,
    scenario: object | None = None,
) -> dict:
    """Run deferred-acceptance clearing and return stable matches.

    Returns:
        ClearingResult dict per SCHEMA.md §5.5.
    """
    raise NotImplementedError("Person B: implement clear()")


def settle(
    match_id: str,
    outcome: str,
    days_late: int,
    market: dict,
    scenario: object | None = None,
) -> dict:
    """Advance a match through settlement and return before/after/delta.

    Returns:
        {
            "before": { "match": Match, "affected_invoices": [RiskProfile...] },
            "after":  { "match": Match, "affected_invoices": [RiskProfile...] },
            "delta":  LearningDelta
        }

    Two full evaluations per request is correct. Do not optimise into one.
    """
    raise NotImplementedError("Person B: implement settle()")
