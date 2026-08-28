"""Template-generated explanations — every score explains itself.

Every scored offer carries a non-empty reason_text.
Template-generated, deterministic, no LLM (AGENTS.md §1.2).

Format money for humans: ₹3,100 and ₹2.00 lakh, never 0.031 or 3100.0.

Owner: Person A
"""

from __future__ import annotations


def format_rupees(amount_rupees: float) -> str:
    """Format rupee amount with comma separators, e.g. ₹16,722 or ₹715."""
    rounded = int(round(amount_rupees))
    return f"₹{rounded:,}"


def format_lakh(amount_lakh: float) -> str:
    """Format lakh amount with two decimals, e.g. ₹2.00 lakh."""
    return f"₹{amount_lakh:.2f} lakh"


def generate_offer_reason(
    offer: dict,
    all_offers: list[dict],
    preferences: dict,
) -> str:
    """Generate a human-readable reason_text for a scored offer.

    Args:
        offer: ScoredOffer dict
        all_offers: list of all Offer/ScoredOffer dicts for this invoice
        preferences: SupplierPreferences dict

    Returns:
        Non-empty reason string explaining why this offer scores as it does.
    """
    if not offer.get("feasible", True):
        return offer.get(
            "rejection_reason",
            "Offer does not meet hard preference constraints.",
        )

    feasible_offers = [o for o in all_offers if o.get("feasible", True)]
    if not feasible_offers:
        return "Only feasible offer available."

    # Identify benchmarks: lowest rate offer, cheapest cost offer
    lowest_rate_offer = min(feasible_offers, key=lambda o: (o["rate_annual"], o["offer_id"]))
    cheapest_cost_offer = min(feasible_offers, key=lambda o: (o.get("total_cost_lakh", 0.0), o["offer_id"]))

    # If this offer is the lowest rate offer
    if offer["offer_id"] == lowest_rate_offer["offer_id"]:
        parts = [f"Lowest headline rate of {offer['rate_annual']:.1%}"]
        if offer["offer_id"] == cheapest_cost_offer["offer_id"]:
            parts.append(f"and lowest total cost of {format_rupees(offer.get('total_cost_lakh', 0.0) * 100000)}")
        else:
            cost_diff_rs = (offer.get("total_cost_lakh", 0.0) - cheapest_cost_offer.get("total_cost_lakh", 0.0)) * 100000
            parts.append(
                f"but advances only {offer['advance_rate']:.0%} "
                f"(costs {format_rupees(cost_diff_rs)} more than {cheapest_cost_offer['provider_id']})"
            )
        return ", ".join(parts) + "."

    clauses = []

    # 1. Cost comparison vs lowest rate offer
    cost_diff_rs = (offer.get("total_cost_lakh", 0.0) - lowest_rate_offer.get("total_cost_lakh", 0.0)) * 100000
    if cost_diff_rs > 50:
        clauses.append(f"Costs {format_rupees(cost_diff_rs)} more than the cheapest rate")
    elif cost_diff_rs < -50:
        clauses.append(f"Costs {format_rupees(abs(cost_diff_rs))} less than the lowest-rate offer")
    else:
        clauses.append("Matches the lowest-rate offer on cost")

    # 2. Advance / Cash comparison
    cash_diff_lakh = offer.get("cash_now_lakh", 0.0) - lowest_rate_offer.get("cash_now_lakh", 0.0)
    if cash_diff_lakh >= 0.01:
        clauses.append(f"delivers {format_lakh(cash_diff_lakh)} more cash")
    elif cash_diff_lakh <= -0.01:
        clauses.append(f"advances {format_lakh(abs(cash_diff_lakh))} less cash")

    # 3. Speed comparison
    days = offer.get("days_to_settle", 0)
    lowest_days = lowest_rate_offer.get("days_to_settle", 0)
    if days == 0:
        clauses.append("same day")
    elif days < lowest_days:
        clauses.append(f"settles {lowest_days - days} days sooner")
    elif days > lowest_days:
        clauses.append(f"settles {days - lowest_days} days slower")

    # Structure consideration
    pref_struct = preferences.get("preferred_structure")
    if pref_struct and offer.get("repayment_structure") != pref_struct:
        clauses.append(f"repays in {offer.get('repayment_structure')}")

    if len(clauses) >= 3:
        return f"{clauses[0]} but {clauses[1]}, {clauses[2]}."
    elif len(clauses) == 2:
        return f"{clauses[0]} but {clauses[1]}."
    elif len(clauses) == 1:
        return f"{clauses[0]}."
    else:
        return f"Fit score: {offer.get('fit_score', 0.0):.2f} based on supplier preference weights."


def generate_risk_reason(risk: dict, buyer: dict, verification: dict) -> str:
    """Generate reason_text for a RiskProfile."""
    grade = buyer.get("credit_grade", "Unknown")
    delay = buyer.get("avg_payment_delay_days", 0)
    unknown_count = verification.get("unknown_field_count", 0)

    parts = [f"Buyer rated {grade} with a {delay}-day average payment delay."]
    if unknown_count > 0:
        parts.append("Range is widened because delivery confirmation is unavailable.")
    return " ".join(parts)


def generate_exclusion_reason(
    provider: dict,
    invoice: dict,
    binding_constraint: str,
    details: dict,
) -> str:
    """Generate exclusion_reason for an ineligible provider."""
    pname = provider.get("name", provider.get("provider_id", "Provider"))
    amount_lakh = invoice.get("amount_lakh", 0.0)

    if binding_constraint == "max_ticket":
        max_ticket = details.get("max_ticket_lakh", provider.get("max_ticket_lakh", 0.0))
        return f"Invoice of {format_lakh(amount_lakh)} exceeds {pname}'s {format_lakh(max_ticket)} maximum ticket size."
    elif binding_constraint == "min_ticket":
        min_ticket = details.get("min_ticket_lakh", provider.get("min_ticket_lakh", 0.0))
        return f"Invoice of {format_lakh(amount_lakh)} is below {pname}'s {format_lakh(min_ticket)} minimum ticket size."
    elif binding_constraint == "liquidity":
        liq = details.get("available_liquidity_lakh", provider.get("available_liquidity_lakh", 0.0))
        return f"{pname} has {format_lakh(liq)} available liquidity, insufficient to fund new invoices."
    elif binding_constraint == "risk_appetite":
        pd_upper = details.get("pd_upper", 0.0)
        appetite = provider.get("risk_appetite", 0.0)
        return f"Invoice risk (PD upper bound of {pd_upper:.4f}) exceeds {pname}'s risk appetite of {appetite:.4f}."
    elif binding_constraint == "sector_limit":
        sector = details.get("sector", "this").replace("_", " ")
        headroom = details.get("headroom_sector", 0.0)
        return f"{pname} has reached its {sector} sector concentration limit (headroom: {format_lakh(headroom)})."
    elif binding_constraint == "buyer_limit":
        buyer_id = details.get("buyer_id", "this buyer")
        headroom = details.get("headroom_buyer", 0.0)
        return f"{pname} has reached its concentration limit for buyer {buyer_id} (headroom: {format_lakh(headroom)})."
    elif binding_constraint == "target_return":
        ret = details.get("max_feasible_return", 0.0)
        target = provider.get("target_return", 0.0)
        return f"Projected return ({ret:.2%}) cannot meet {pname}'s required target return of {target:.2%}."

    return f"{pname} is ineligible due to {binding_constraint} constraint."
