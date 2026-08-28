"""Provider bidding agents — each provider independently decides terms.

Each agent constructs a full multi-term offer based on its type, risk profile,
and capacity. Constants come from engine/config.py (AGENTS.md §7).

Agents differentiate on rate, advance, speed, fees, and structure — not just
rate. Four offers that differ only by 30 basis points makes the product
pointless (PERSON_B §10).

Owner: Person B
"""

from __future__ import annotations


def generate_offer(
    provider: dict,
    invoice: dict,
    assessment: dict,
    eligibility: dict,
    expected_competitors: int,
) -> dict | None:
    """Generate an Offer from this provider, or None if ineligible.

    Returns None only when eligibility.eligible is False.
    An eligible-but-capacity-limited provider still bids — for
    max_fundable_lakh, not the full amount.

    The offer must respect the provider's own limits:
        - days_to_settle >= provider.speed_capability_days
        - repayment_structure in provider.preferred_structures
        - amount_committed_lakh <= eligibility.max_fundable_lakh
        - rate_annual >= provider.cost_of_funds

    Returns:
        Offer dict per SCHEMA.md §4.5, or None.
    """
    raise NotImplementedError("Person B: implement generate_offer()")
