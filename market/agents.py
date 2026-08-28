"""Provider bidding agents — each provider independently decides terms.

Each agent constructs a full multi-term offer based on its type, risk profile,
and capacity. Constants come from engine/config.py (AGENTS.md §7).

Agents differentiate on rate, advance, speed, fees, and structure — not just
rate. Four offers that differ only by 30 basis points makes the product
pointless (PERSON_B §10).

Owner: Person B
"""

from __future__ import annotations

import math

from engine.config import (
    CAPITAL_CHARGE_RATE,
    DEFAULT_EXPECTED_COMPETITORS,
    PROVIDER_TYPE_DEFAULTS,
    RECOVERY_RATE,
    SHADE_K,
)


def segment_key(invoice: dict, buyer: dict) -> str:
    """The bucket an agent learns over: sector, buyer grade, tenor.

    Coarse on purpose. A provider that learned per buyer would need years of
    outcomes before it had an opinion; per sector alone it would never notice
    that AA and BB behave differently. This is the grain PERSON_B.md §3.4
    names, and it is the grain the LearningDelta reports.
    """
    return (f"{buyer.get('sector', 'unknown')}/"
            f"{buyer.get('credit_grade', 'unknown')}/"
            f"{invoice.get('tenor_days', 0)}d")


def bid_rate(provider: dict, risk: dict, expected_competitors: int,
              segment_adjustment: float = 0.0) -> float:
    """Price the deal — PERSON_B.md §3.1.

    The shade is the winner's-curse premium: in an auction the winner is
    disproportionately whoever most underestimated the risk, so each agent
    adds a margin proportional to how uncertain the estimate is and to how
    many rivals it expects. A market that ignores this quietly bankrupts its
    own lenders.
    """
    expected_loss = risk["pd"] * (1 - RECOVERY_RATE)
    capital_charge = CAPITAL_CHARGE_RATE * risk["pd_upper"]
    required = (
        provider["cost_of_funds"]
        + expected_loss
        + capital_charge
        + provider.get("target_margin", 0.0)
    )
    shade = SHADE_K * risk["uncertainty"] * math.log(1 + expected_competitors)
    # What this provider has learned about this segment from past outcomes.
    # Zero on a market that has not settled anything, which is every market
    # loaded from disk — learning is carried in the market dict, not in a
    # module-level accumulator, because the API is stateless (AGENTS.md §3.4).
    # Bidding below your own funding cost is a bug, not a strategy.
    return max(required + shade + segment_adjustment, provider["cost_of_funds"])


def _non_price_terms(provider: dict) -> tuple[float, int, float, str]:
    """Differentiate on everything except rate, by provider type.

    This is what produces four genuinely different offers instead of four
    rates thirty basis points apart. A conservative bank advances less but
    settles predictably; an opportunistic fund advances more, same day, and
    charges for it.
    """
    terms = PROVIDER_TYPE_DEFAULTS[provider["type"]]

    advance_rate = terms["advance"]

    # An agent may never promise to settle faster than its own capability.
    days_to_settle = max(terms["settle_days"], provider.get("speed_capability_days", 0))

    fee_percent = terms["fee_percent"]

    # Offer the type's usual structure only if this provider actually supports
    # it; otherwise fall back to whatever it does support.
    preferred = provider.get("preferred_structures") or terms["structures"]
    structure = terms["structures"][0]
    if structure not in preferred:
        structure = preferred[0]

    return advance_rate, days_to_settle, fee_percent, structure


def generate_offer(
    provider: dict,
    invoice: dict,
    assessment: dict,
    eligibility: dict,
    expected_competitors: int = DEFAULT_EXPECTED_COMPETITORS,
    segment: str | None = None,
) -> dict | None:
    """Generate an Offer from this provider, or None if ineligible.

    Returns None only when eligibility.eligible is False.
    An eligible-but-capacity-limited provider still bids — for
    max_fundable_lakh, not the full amount. That partial bid is what
    produces syndication.

    Returns:
        Offer dict per SCHEMA.md §4.5, or None.
    """
    if not eligibility.get("eligible", False):
        return None

    learned = provider.get("segment_adjustments", {}).get(segment, 0.0)
    rate_annual = bid_rate(provider, assessment["risk"], expected_competitors,
                            segment_adjustment=learned)
    advance_rate, days_to_settle, fee_percent, structure = _non_price_terms(provider)

    amount_lakh = invoice["amount_lakh"]
    advance_amount_lakh = round(amount_lakh * advance_rate, 2)

    # Capacity, not appetite, is what caps the commitment here. A provider that
    # wants the whole deal but is up against a concentration limit bids for the
    # part it can fund and lets the clearing engine syndicate the remainder.
    max_fundable = eligibility.get("max_fundable_lakh", advance_amount_lakh)
    amount_committed_lakh = round(min(advance_amount_lakh, max_fundable), 2)

    return {
        # One offer per provider per invoice, so the offer number follows the
        # provider number rather than depending on iteration order.
        "offer_id": "OFR" + provider["provider_id"][3:],
        "invoice_id": invoice["invoice_id"],
        "provider_id": provider["provider_id"],
        "rate_annual": round(rate_annual, 4),
        "advance_rate": round(advance_rate, 4),
        "tenor_days": invoice["tenor_days"],
        "fee_percent": round(fee_percent, 4),
        "fee_flat_lakh": 0.00,
        "days_to_settle": days_to_settle,
        "repayment_structure": structure,
        "amount_committed_lakh": amount_committed_lakh,
        "advance_amount_lakh": advance_amount_lakh,
    }


def generate_offers(
    providers: list[dict],
    invoice: dict,
    assessment: dict,
    segment: str | None = None,
) -> list[dict]:
    """Collect bids from every eligible provider, sorted by offer_id.

    `expected_competitors` is derived from how many providers cleared
    eligibility — an agent shades harder when it expects a crowded auction.
    """
    eligibility = {e["provider_id"]: e for e in assessment["eligibility"]}
    eligible_count = sum(1 for e in eligibility.values() if e.get("eligible"))

    offers = []
    for provider in sorted(providers, key=lambda p: p["provider_id"]):
        entry = eligibility.get(provider["provider_id"])
        if entry is None:
            continue
        offer = generate_offer(
            provider,
            invoice,
            assessment,
            entry,
            expected_competitors=max(eligible_count - 1, 0),
            segment=segment,
        )
        if offer is not None:
            offers.append(offer)
    return sorted(offers, key=lambda o: o["offer_id"])
