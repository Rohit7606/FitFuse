"""Template-generated explanations — every score explains itself.

Every scored offer carries a non-empty reason_text.
Template-generated, deterministic, no LLM (AGENTS.md §1.2).

Format money for humans: ₹3,100 and ₹2.00 lakh, never 0.031 or 3100.0.

Owner: Person A
"""

from __future__ import annotations


def generate_offer_reason(
    offer: dict,
    all_offers: list[dict],
    preferences: dict,
) -> str:
    """Generate a human-readable reason_text for a scored offer.

    Target output examples:
        "Costs ₹3,100 more than the cheapest rate but delivers ₹2.00 lakh
         more cash, same day."
        "Advances only 60%, below your 70% minimum."

    Returns:
        Non-empty reason string.
    """
    raise NotImplementedError("Person A: implement generate_offer_reason()")


def generate_risk_reason(risk: dict, buyer: dict, verification: dict) -> str:
    """Generate reason_text for a RiskProfile.

    Target output example:
        "Buyer rated AA with a 4-day average payment delay. Range is widened
         because delivery confirmation is unavailable."

    Returns:
        Non-empty reason string.
    """
    raise NotImplementedError("Person A: implement generate_risk_reason()")


def generate_exclusion_reason(
    provider: dict,
    invoice: dict,
    binding_constraint: str,
    details: dict,
) -> str:
    """Generate exclusion_reason for an ineligible provider.

    Must name the provider and the number. Not "ticket size" but:
        "Invoice of ₹10.00 lakh exceeds Coastal Cooperative Bank's
         ₹8.00 lakh maximum ticket size."

    Returns:
        Non-empty exclusion reason string.
    """
    raise NotImplementedError("Person A: implement generate_exclusion_reason()")
