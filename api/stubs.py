"""The last Phase 0 stub, kept only for /api/settle.

Everything else here has been deleted: /api/assess, /api/offers and /api/clear
now call the real engine and market (Phase 2). What remains exists because
market/settlement.py and market/learning.py are Phase 3 work.

DELETE THIS MODULE once market/simulate.settle() is implemented.

Owner: Person B
"""

from __future__ import annotations


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
