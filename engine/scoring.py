"""Whole-offer value scoring — the centrepiece of the product.

Converts every offer into one number representing value to this supplier.
Fully transparent — the arithmetic is shown.

Steps:
    1. Hard constraints (min_advance_rate, max_days_to_cash) → feasible/infeasible
    2. All-in cost in rupees
    3. Normalise each attribute 0–1 across feasible offers (1 = best for supplier)
    4. Urgency multiplier on weights
    5. Weighted sum → fit_score
    6. Naive ranking (by rate_annual ascending) always computed

Owner: Person A
"""

from __future__ import annotations


def score_offers(
    offers: list[dict],
    assessment: dict,
    preferences: dict,
) -> dict:
    """Score and rank competing offers for one supplier.

    Args:
        offers: list of Offer dicts from market/agents.py
        assessment: Assessment dict from assess()
        preferences: SupplierPreferences dict

    Returns:
        {
            "offers": [ScoredOffer...],
            "ranking": [...],
            "naive_ranking": [...],
            "summary": {...}
        }

    Infeasible offers are returned with feasible=false, never dropped.
    Ties break by offer_id ascending for determinism.
    """
    raise NotImplementedError("Person A: implement score_offers()")
