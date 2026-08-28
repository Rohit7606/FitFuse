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

import copy

from engine.config import (
    STRUCTURE_MISMATCH,
    URGENCY_ADVANCE_BOOST,
    URGENCY_SPEED_BOOST,
)
from engine.reasons import generate_offer_reason


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
            "ranking": [offer_id...],
            "naive_ranking": [offer_id...],
            "summary": {
                "offer_count": int,
                "feasible_count": int,
                "best_fit_offer_id": str | None,
                "lowest_rate_offer_id": str | None,
                "fit_beats_rate": bool,
            }
        }

    Infeasible offers are returned with feasible=false, never dropped.
    Ties break by offer_id ascending for determinism.
    """
    if not offers:
        return {
            "offers": [],
            "ranking": [],
            "naive_ranking": [],
            "summary": {
                "offer_count": 0,
                "feasible_count": 0,
                "best_fit_offer_id": None,
                "lowest_rate_offer_id": None,
                "fit_beats_rate": False,
            },
        }

    # Deep copy offers to preserve purity
    scored_offers = [copy.deepcopy(o) for o in offers]

    # Preference constraints
    min_advance_rate = preferences.get("min_advance_rate")
    max_days_to_cash = preferences.get("max_days_to_cash")
    preferred_structure = preferences.get("preferred_structure")
    is_urgent = bool(preferences.get("urgent", False))

    # Base weights (must have cost, advance, speed, tenor, fees, structure)
    raw_weights = preferences.get("weights", {
        "cost": 0.15,
        "advance": 0.30,
        "speed": 0.35,
        "tenor": 0.10,
        "fees": 0.05,
        "structure": 0.05,
    })
    weights = dict(raw_weights)

    # Apply urgency multiplier if urgent
    if is_urgent:
        weights["speed"] = weights.get("speed", 0.0) * URGENCY_SPEED_BOOST
        weights["advance"] = weights.get("advance", 0.0) * URGENCY_ADVANCE_BOOST

    # Renormalise weights to sum to 1.0
    total_w = sum(weights.values()) or 1.0
    weights = {k: v / total_w for k, v in weights.items()}

    # ------------------------------------------------------------------
    # Step 1 & 2: Hard constraints & All-in cost computation
    # ------------------------------------------------------------------
    for offer in scored_offers:
        advance_rate = offer["advance_rate"]
        days_to_settle = offer["days_to_settle"]
        tenor_days = offer.get("tenor_days", 60)
        rate_annual = offer["rate_annual"]
        fee_percent = offer.get("fee_percent", 0.0)
        fee_flat_lakh = offer.get("fee_flat_lakh", 0.0)

        # Derive amount_lakh if not present
        if "amount_lakh" in offer:
            amount_lakh = float(offer["amount_lakh"])
        elif "advance_amount_lakh" in offer and advance_rate > 0:
            amount_lakh = round(float(offer["advance_amount_lakh"]) / advance_rate, 2)
        else:
            amount_lakh = 10.00

        # Denormalised advance amounts
        advance_amount_lakh = round(amount_lakh * advance_rate, 2)
        offer["advance_amount_lakh"] = advance_amount_lakh
        offer["cash_now_lakh"] = advance_amount_lakh

        # Amount committed default if not provided
        if "amount_committed_lakh" not in offer:
            offer["amount_committed_lakh"] = advance_amount_lakh

        # Total cost calculation (SCHEMA.md §4.5 / DEMO_SCENARIO.md §4)
        financing_cost = amount_lakh * advance_rate * rate_annual * (tenor_days / 365.0)
        fee_cost = amount_lakh * fee_percent + fee_flat_lakh
        total_cost_lakh = financing_cost + fee_cost
        offer["total_cost_lakh"] = round(total_cost_lakh, 4)
        offer["_fee_total"] = fee_cost

        # Check hard constraints
        feasible = True
        rejection_reason = None

        if min_advance_rate is not None and advance_rate < (min_advance_rate - 1e-6):
            feasible = False
            rejection_reason = (
                f"Advances only {advance_rate:.0%}, below your "
                f"{min_advance_rate:.0%} minimum."
            )
        elif max_days_to_cash is not None and days_to_settle > max_days_to_cash:
            feasible = False
            rejection_reason = (
                f"Settles in {days_to_settle} days, past your "
                f"{max_days_to_cash}-day requirement."
            )

        offer["feasible"] = feasible
        offer["rejection_reason"] = rejection_reason

    # ------------------------------------------------------------------
    # Step 3: Normalise 6 attributes across FEASIBLE offers only
    # ------------------------------------------------------------------
    feasible_offers = [o for o in scored_offers if o["feasible"]]

    if feasible_offers:
        costs = [o["total_cost_lakh"] for o in feasible_offers]
        advances = [o["advance_rate"] for o in feasible_offers]
        speeds = [o["days_to_settle"] for o in feasible_offers]
        tenors = [o["tenor_days"] for o in feasible_offers]
        fees = [o["_fee_total"] for o in feasible_offers]

        min_cost, max_cost = min(costs), max(costs)
        min_adv, max_adv = min(advances), max(advances)
        min_spd, max_spd = min(speeds), max(speeds)
        min_tnr, max_tnr = min(tenors), max(tenors)
        min_fee, max_fee = min(fees), max(fees)

        span_cost = max_cost - min_cost
        span_adv = max_adv - min_adv
        span_spd = max_spd - min_spd
        span_tnr = max_tnr - min_tnr
        span_fee = max_fee - min_fee

        for offer in feasible_offers:
            cost_score = (
                1.0 - (offer["total_cost_lakh"] - min_cost) / span_cost
                if span_cost > 0
                else 1.0
            )
            adv_score = (
                (offer["advance_rate"] - min_adv) / span_adv
                if span_adv > 0
                else 1.0
            )
            speed_score = (
                1.0 - (offer["days_to_settle"] - min_spd) / span_spd
                if span_spd > 0
                else 1.0
            )
            tenor_score = (
                (offer["tenor_days"] - min_tnr) / span_tnr
                if span_tnr > 0
                else 1.0
            )
            fee_score = (
                1.0 - (offer["_fee_total"] - min_fee) / span_fee
                if span_fee > 0
                else 1.0
            )

            struct = offer.get("repayment_structure")
            if preferred_structure is None or struct == preferred_structure:
                struct_score = 1.0
            else:
                struct_score = STRUCTURE_MISMATCH

            comp_scores = {
                "cost": round(cost_score, 4),
                "advance": round(adv_score, 4),
                "speed": round(speed_score, 4),
                "tenor": round(tenor_score, 4),
                "fees": round(fee_score, 4),
                "structure": round(struct_score, 4),
            }
            offer["component_scores"] = comp_scores

            # Weighted sum fit_score
            fit_score = (
                weights.get("cost", 0.0) * cost_score
                + weights.get("advance", 0.0) * adv_score
                + weights.get("speed", 0.0) * speed_score
                + weights.get("tenor", 0.0) * tenor_score
                + weights.get("fees", 0.0) * fee_score
                + weights.get("structure", 0.0) * struct_score
            )
            offer["fit_score"] = round(max(0.0, min(1.0, fit_score)), 4)
    else:
        for offer in scored_offers:
            offer["component_scores"] = {
                "cost": 0.0, "advance": 0.0, "speed": 0.0,
                "tenor": 0.0, "fees": 0.0, "structure": 0.0,
            }
            offer["fit_score"] = 0.0

    # Handle infeasible offers
    for offer in scored_offers:
        if not offer["feasible"]:
            offer["component_scores"] = {
                "cost": 0.0, "advance": 0.0, "speed": 0.0,
                "tenor": 0.0, "fees": 0.0, "structure": 0.0,
            }
            offer["fit_score"] = 0.0

        # Remove internal helper key
        offer.pop("_fee_total", None)

    # ------------------------------------------------------------------
    # Step 5: Reason Generation
    # ------------------------------------------------------------------
    for offer in scored_offers:
        offer["reason_text"] = generate_offer_reason(
            offer, scored_offers, preferences
        )

    # ------------------------------------------------------------------
    # Step 6: Rankings & Summary
    # ------------------------------------------------------------------
    # Ranking by fit_score descending (ties break by offer_id ascending)
    ranked_feasible = sorted(
        [o for o in scored_offers if o["feasible"]],
        key=lambda x: (-x["fit_score"], x["offer_id"]),
    )
    ranked_infeasible = sorted(
        [o for o in scored_offers if not o["feasible"]],
        key=lambda x: x["offer_id"],
    )
    ranking = [o["offer_id"] for o in ranked_feasible] + [o["offer_id"] for o in ranked_infeasible]

    # Naive ranking by rate_annual ascending (ties break by offer_id ascending)
    naive_feasible = sorted(
        [o for o in scored_offers if o["feasible"]],
        key=lambda x: (x["rate_annual"], x["offer_id"]),
    )
    naive_ranking = [o["offer_id"] for o in naive_feasible] + [o["offer_id"] for o in ranked_infeasible]

    best_fit = ranking[0] if ranking else None
    lowest_rate = naive_ranking[0] if naive_ranking else None
    fit_beats_rate = bool(best_fit and lowest_rate and best_fit != lowest_rate)

    summary = {
        "offer_count": len(scored_offers),
        "feasible_count": len(ranked_feasible),
        "best_fit_offer_id": best_fit,
        "lowest_rate_offer_id": lowest_rate,
        "fit_beats_rate": fit_beats_rate,
    }

    return {
        "offers": scored_offers,
        "ranking": ranking,
        "naive_ranking": naive_ranking,
        "summary": summary,
    }
