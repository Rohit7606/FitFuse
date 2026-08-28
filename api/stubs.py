"""Static, contract-valid responses for Phase 0.

These exist so Person C can build the whole frontend against a running API
before engine/ and market/ are implemented (AGENTS.md §6, PERSON_B.md §9).

Every payload here is shaped exactly like the real thing and validates against
schema.json, so swapping a stub for real logic in Phase 1 is a one-line change
in api/main.py and never a reshaping of the frontend.

The numbers are the canonical demo values from DEMO_SCENARIO.md §4 and §5 —
not invented ones — so what C designs around now is what the engine will
eventually produce.

DELETE THIS MODULE once all five endpoints call engine/ and market/ for real.

Owner: Person B
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Demo constants — DEMO_SCENARIO.md §4. Person A owns these values; they are
# mirrored here only until the engine computes them.
# ---------------------------------------------------------------------------

_TENOR_DAYS = 60
_AMOUNT_LAKH = 10.00

# offer_id, provider_id, rate, advance, days_to_settle, fee_pct, structure, fit
_DEMO_OFFERS = [
    ("OFR001", "PRV001", 0.0900, 0.80, 3, 0.0050, "bullet", 0.71),
    ("OFR002", "PRV002", 0.0820, 0.70, 2, 0.0080, "bullet", 0.64),
    ("OFR003", "PRV003", 0.0860, 0.90, 0, 0.0040, "bullet", 0.89),
    ("OFR004", "PRV004", 0.0940, 0.75, 1, 0.0030, "instalment", 0.68),
]

_OFFER_REASONS = {
    "OFR001": "Costs ₹1,14,000 less than the cheapest rate but advances only 80%, "
              "settling in 3 days.",
    "OFR002": "Lowest headline rate at 8.20%, but advances only 70% and charges "
              "0.80% in fees — ₹7,15 more in rupees than Kestrel.",
    "OFR003": "Costs ₹715 less than the lowest-rate offer and delivers ₹2.00 lakh "
              "more cash, same day.",
    "OFR004": "Cheapest in rupees at ₹14,589, but advances only 75% and repays in "
              "instalments rather than a single payment.",
}

# provider_id, eligible, max_fundable_lakh, binding_constraint, exclusion_reason
_DEMO_ELIGIBILITY = [
    ("PRV001", True, 500.00, None, None),
    ("PRV002", True, 200.00, None, None),
    ("PRV003", True, 6.00, "sector_limit", None),
    ("PRV004", True, 100.00, None, None),
    ("PRV005", False, 0.00, "max_ticket",
     "Invoice of ₹10.00 lakh exceeds Coastal Cooperative Bank's ₹8.00 lakh "
     "maximum ticket size."),
    ("PRV006", False, 0.00, "risk_appetite",
     "Sentinel Asset Managers accepts a default probability up to 1.50%; this "
     "invoice's upper estimate is 2.80%."),
]


def _total_cost_lakh(rate: float, advance: float, fee_pct: float) -> float:
    """All-in rupee cost — DEMO_SCENARIO.md §4. The headline rate is not the cost."""
    financing = _AMOUNT_LAKH * advance * rate * (_TENOR_DAYS / 365)
    fees = _AMOUNT_LAKH * fee_pct
    return round(financing + fees, 5)


def stub_assessment(invoice_id: str) -> dict:
    """A complete Assessment (SCHEMA.md §4.1) with all six providers screened."""
    return {
        "invoice_id": invoice_id,
        "verification": {
            "status": "verified",
            "irn_valid": True,
            "duplicate_detected": False,
            "duplicate_of": None,
            "field_confidence": {
                "amount_lakh": "verified",
                "irn": "verified",
                "buyer_gstin": "verified",
                "delivery_confirmed": "unknown",
            },
            "unknown_field_count": 1,
            "reason_text": (
                "Invoice registered under a valid IRN and not previously financed. "
                "Delivery confirmation is unavailable."
            ),
        },
        "risk": {
            "pd": 0.0210,
            "pd_lower": 0.0140,
            "pd_upper": 0.0280,
            "uncertainty": 0.0070,
            "risk_band": "prime",
            "expected_loss_lakh": 0.1260,
            "reason_text": (
                "Buyer rated AA with a 4-day average payment delay. The range is "
                "widened because delivery confirmation is unavailable."
            ),
            "reason_factors": [
                {"kind": "buyer_grade", "detail": "Buyer rated AA", "weight": 0.45},
                {"kind": "payment_delay", "detail": "4-day average payment delay",
                 "weight": 0.25},
                {"kind": "tenor", "detail": "60-day tenor", "weight": 0.18},
                {"kind": "unverified", "detail": "Delivery confirmation unavailable",
                 "weight": 0.12},
            ],
        },
        "eligibility": [
            {
                "provider_id": pid,
                "eligible": ok,
                "max_fundable_lakh": cap,
                "exclusion_reason": reason,
                "binding_constraint": binding,
            }
            for pid, ok, cap, binding, reason in _DEMO_ELIGIBILITY
        ],
        "meta": {"stub": True, "source": "api/stubs.py", "data_source": "synthetic"},
    }


def stub_offers(invoice_id: str) -> dict:
    """Scored offers plus both rankings (SCHEMA.md §5.4).

    naive_ranking is returned unconditionally so the frontend can toggle the
    counterfactual with no second request.
    """
    offers = []
    for oid, pid, rate, advance, days, fee_pct, structure, fit in _DEMO_OFFERS:
        cost = _total_cost_lakh(rate, advance, fee_pct)
        advance_lakh = round(_AMOUNT_LAKH * advance, 2)
        offers.append({
            "offer_id": oid,
            "invoice_id": invoice_id,
            "provider_id": pid,
            "rate_annual": rate,
            "advance_rate": advance,
            "tenor_days": _TENOR_DAYS,
            "fee_percent": fee_pct,
            "fee_flat_lakh": 0.0,
            "days_to_settle": days,
            "repayment_structure": structure,
            "amount_committed_lakh": advance_lakh,
            "advance_amount_lakh": advance_lakh,
            "total_cost_lakh": cost,
            "cash_now_lakh": advance_lakh,
            "fit_score": fit,
            "component_scores": {
                "cost": 0.0, "advance": 0.0, "speed": 0.0,
                "tenor": 0.0, "fees": 0.0, "structure": 0.0,
            },
            "feasible": True,
            "rejection_reason": None,
            "reason_text": _OFFER_REASONS[oid],
        })

    ranking = sorted(offers, key=lambda o: (-o["fit_score"], o["offer_id"]))
    naive = sorted(offers, key=lambda o: (o["rate_annual"], o["offer_id"]))
    ranking_ids = [o["offer_id"] for o in ranking]
    naive_ids = [o["offer_id"] for o in naive]

    return {
        "invoice_id": invoice_id,
        "assessment": stub_assessment(invoice_id),
        "offers": offers,
        "ranking": ranking_ids,
        "naive_ranking": naive_ids,
        "summary": {
            "offer_count": len(offers),
            "feasible_count": sum(1 for o in offers if o["feasible"]),
            "best_fit_offer_id": ranking_ids[0],
            "lowest_rate_offer_id": naive_ids[0],
            "fit_beats_rate": ranking_ids[0] != naive_ids[0],
        },
    }


def _stub_match(invoice_id: str, state: str) -> dict:
    """The syndicated demo match: Kestrel capped at 6.00, Meridian takes 3.00."""
    return {
        "match_id": "MCH001",
        "invoice_id": invoice_id,
        "allocations": [
            {"provider_id": "PRV003", "amount_lakh": 6.00, "offer_id": "OFR003"},
            {"provider_id": "PRV001", "amount_lakh": 3.00, "offer_id": "OFR001"},
        ],
        "syndicated": True,
        "total_advance_lakh": 9.00,
        "blended_rate_annual": 0.0873,
        "blended_cost_lakh": 0.16750,
        "supplier_fit_score": 0.89,
        "state": state,
        "days_to_settle": 0,
        "reason_text": (
            "Kestrel Credit Fund could fund only ₹6.00 lakh before hitting its "
            "auto-components sector limit, so Meridian Bank funded the remaining "
            "₹3.00 lakh."
        ),
    }


def stub_clearing(invoice_ids: list[str]) -> dict:
    """Clearing result with one syndicated match (SCHEMA.md §5.5)."""
    primary = invoice_ids[0]
    return {
        "matches": [_stub_match(primary, "matched")],
        "unmatched": [
            {"invoice_id": i,
             "reason": "Stub response: only the first invoice is matched in Phase 0."}
            for i in invoice_ids[1:]
        ],
        "provider_utilisation": [
            {"provider_id": "PRV001", "committed_lakh": 3.00,
             "remaining_lakh": 1997.00, "utilisation": 0.0015},
            {"provider_id": "PRV003", "committed_lakh": 6.00,
             "remaining_lakh": 494.00, "utilisation": 0.0120},
        ],
        "summary": {
            "matched_count": 1,
            "syndicated_count": 1,
            "iterations": 3,
            "stable": True,
        },
    }


def stub_settle(match_id: str, outcome: str, days_late: int) -> dict:
    """Before / after / delta for the closing demo beat (SCHEMA.md §5.6)."""
    before_risk = {
        "pd": 0.0210, "pd_lower": 0.0140, "pd_upper": 0.0280,
        "uncertainty": 0.0070, "risk_band": "prime", "expected_loss_lakh": 0.0630,
        "reason_text": "Buyer rated AA with a 4-day average payment delay.",
        "reason_factors": [
            {"kind": "buyer_grade", "detail": "Buyer rated AA", "weight": 0.60},
            {"kind": "payment_delay", "detail": "4-day average payment delay",
             "weight": 0.40},
        ],
    }
    after_risk = {
        "pd": 0.0265, "pd_lower": 0.0190, "pd_upper": 0.0340,
        "uncertainty": 0.0075, "risk_band": "standard", "expected_loss_lakh": 0.0795,
        "reason_text": (
            "Buyer rated AA, but the average payment delay has risen to 5 days "
            "after a late settlement."
        ),
        "reason_factors": [
            {"kind": "buyer_grade", "detail": "Buyer rated AA", "weight": 0.55},
            {"kind": "payment_delay", "detail": "5-day average payment delay",
             "weight": 0.45},
        ],
    }
    return {
        "before": {
            "match": _stub_match("INV001", "funded"),
            "affected_invoices": [before_risk],
        },
        "after": {
            "match": _stub_match("INV001", outcome),
            "affected_invoices": [after_risk],
        },
        "delta": {
            "trigger": {
                "match_id": match_id,
                "outcome": outcome,
                "days_late": days_late,
                "buyer_id": "BUY001",
            },
            "buyer_updates": [
                {"buyer_id": "BUY001", "field": "avg_payment_delay_days",
                 "before": 4, "after": 5},
            ],
            "repriced_invoices": [
                {"invoice_id": "INV014", "pd_before": 0.0210, "pd_after": 0.0265,
                 "band_before": "prime", "band_after": "standard"},
            ],
            "liquidity_updates": [
                {"provider_id": "PRV003", "returned_lakh": 6.00,
                 "available_before_lakh": 494.00, "available_after_lakh": 500.00},
            ],
            "provider_bid_adjustments": [
                {"provider_id": "PRV003",
                 "segment": "auto_components/AA/60d",
                 "rate_adjustment": 0.0015},
            ],
            "summary_text": (
                f"Vireon Motors paid {days_late} days late. One other open invoice "
                "on that buyer was repriced from prime to standard, and Kestrel "
                "Credit Fund raised its next bid on this segment by 15 basis points."
            ),
        },
    }
