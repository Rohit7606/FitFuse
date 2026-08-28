"""Risk scoring — default probability with an honest uncertainty band.

# Credit risk sits primarily with the BUYER, not the supplier.
# The financier pays the supplier now and collects from the buyer later.
# See SCHEMA.md §2.6.

Uses a transparent scorecard: hand-set coefficients committed in config.py,
applied as a weighted logistic. Not a trained model (AGENTS.md §1.5).

Owner: Person A
"""

from __future__ import annotations

import math

from engine.config import (
    B0,
    B_DELAY,
    B_DISPUTE,
    B_GRADE,
    B_HISTORY,
    B_SIZE,
    B_TENOR,
    B_THIN,
    B_TREND,
    BASE_UNCERTAINTY,
    DELAY_REF_DAYS,
    DISPUTE_REF,
    EPSILON,
    GRADE_PENALTY,
    INFERRED_FIELD_PENALTY,
    NEW_SUPPLIER_PENALTY,
    NO_HISTORY_PRIOR,
    PD_CEILING,
    PD_FLOOR,
    RISK_BAND_THRESHOLDS,
    TENOR_REF_DAYS,
    THIN_FILE_PENALTY,
    TREND_REF_DAYS,
    UNKNOWN_FIELD_PENALTY,
)


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp *value* to [lo, hi]."""
    return max(lo, min(value, hi))


def _grade_penalty(credit_grade: str) -> float:
    """Look up the buyer's credit-grade penalty.

    The table is in config.py — it is a lookup, not a formula.
    """
    if credit_grade not in GRADE_PENALTY:
        raise ValueError(f"Unknown credit grade: {credit_grade!r}")
    return GRADE_PENALTY[credit_grade]


def _size_anomaly(amount_lakh: float, annual_revenue_lakh: float) -> float:
    """Flag an invoice that is unusually large relative to the supplier's revenue.

    ratio = amount / max(annual_revenue / 12, EPSILON)
    anomaly = clamp((ratio - 1.0) / 3.0, 0.0, 1.0)

    One month of revenue → 0.  Four months of revenue → 1.
    """
    monthly_revenue = max(annual_revenue_lakh / 12.0, EPSILON)
    ratio = amount_lakh / monthly_revenue
    return _clamp((ratio - 1.0) / 3.0, 0.0, 1.0)


def _default_rate(supplier: dict) -> float:
    """Compute the supplier's historical default rate.

    Must handle null vs zero explicitly — see AGENTS.md §3.6.

    prior_defaults=0, prior_financings>0   → 0.0
        A declared clean record — it should help.
    prior_defaults=null (any financings)   → NO_HISTORY_PRIOR (0.02)
        Absence of history is not a clean record.
    prior_defaults=n>0, prior_financings=m>0 → n/m
    prior_financings=0 (regardless of defaults) → NO_HISTORY_PRIOR
        No track record either way.
    """
    prior_financings = supplier.get("prior_financings") or 0
    prior_defaults = supplier.get("prior_defaults")

    # No track record at all — no way to distinguish good from unknown.
    if prior_financings == 0:
        return NO_HISTORY_PRIOR

    # prior_defaults is null — supplier did not answer. Treat as unknown.
    if prior_defaults is None:
        return NO_HISTORY_PRIOR

    # Explicit zero — a real clean record.
    if prior_defaults == 0:
        return 0.0

    # n > 0 defaults out of m financings.
    return prior_defaults / prior_financings


def _risk_band(pd_upper: float) -> str:
    """Map pd_upper to a named risk band.

    Thresholds from config.py / SCHEMA.md §4.8.
    Banding is on pd_upper, not pd — see SCHEMA.md §4.3.
    """
    if pd_upper < RISK_BAND_THRESHOLDS["prime"]:
        return "prime"
    if pd_upper < RISK_BAND_THRESHOLDS["standard"]:
        return "standard"
    if pd_upper < RISK_BAND_THRESHOLDS["watch"]:
        return "watch"
    return "decline"


def score_risk(
    invoice: dict,
    supplier: dict,
    buyer: dict,
    verification: dict,
) -> dict:
    """Compute default probability with uncertainty band.

    Args:
        invoice: invoice record from market["invoices"]
        supplier: supplier record from market["suppliers"]
        buyer: buyer record from market["buyers"]
        verification: Verification dict from verify.verify()

    Returns:
        RiskProfile dict per SCHEMA.md §4.3

    Deterministic. No I/O, no globals, no mutation of inputs.
    """
    # ------------------------------------------------------------------
    # Logistic scorecard — PERSON_A.md §3.2
    # ------------------------------------------------------------------
    grade_pen = _grade_penalty(buyer["credit_grade"])

    delay = buyer.get("avg_payment_delay_days", 0)
    trend = buyer.get("payment_delay_trend", 0.0)
    tenor_days = invoice["tenor_days"]
    amount_lakh = invoice["amount_lakh"]
    annual_revenue_lakh = supplier["annual_revenue_lakh"]
    data_completeness = supplier.get("data_completeness", 1.0)
    disputes = buyer.get("disputes_last_year")
    # disputes_last_year can be null — treat null as 0 for the logit,
    # but the unknown is already captured via field_confidence.
    if disputes is None:
        disputes = 0

    logit = (
        B0
        + B_GRADE * grade_pen
        + B_DELAY * min(delay / DELAY_REF_DAYS, 1.0)
        # payment_delay_trend can be negative (buyer improving) — allow it
        # to reduce the logit. Do NOT clamp negative trend to 0.
        + B_TREND * _clamp(trend / TREND_REF_DAYS, 0.0, 1.0)
        + B_TENOR * min(tenor_days / TENOR_REF_DAYS, 1.0)
        + B_SIZE * _size_anomaly(amount_lakh, annual_revenue_lakh)
        + B_THIN * (1.0 - data_completeness)
        + B_HISTORY * _default_rate(supplier)
        + B_DISPUTE * min(disputes / DISPUTE_REF, 1.0)
    )

    pd = _clamp(1.0 / (1.0 + math.exp(-logit)), PD_FLOOR, PD_CEILING)

    # ------------------------------------------------------------------
    # Uncertainty band — PERSON_A.md §3.2
    # ------------------------------------------------------------------
    unknown_field_count = verification.get("unknown_field_count", 0)
    inferred_field_count = verification.get("inferred_field_count", 0)
    years_operating = supplier.get("years_operating", 0)

    uncertainty = (
        BASE_UNCERTAINTY
        + UNKNOWN_FIELD_PENALTY * unknown_field_count
        + INFERRED_FIELD_PENALTY * inferred_field_count
        + THIN_FILE_PENALTY * (1.0 - data_completeness)
        # New suppliers (< 3 years) get an extra penalty because their
        # track record is too short to be trustworthy.
        + (NEW_SUPPLIER_PENALTY if years_operating < 3 else 0.0)
    )

    pd_lower = _clamp(pd - uncertainty, PD_FLOOR, 1.0)
    pd_upper = _clamp(pd + uncertainty, 0.0, PD_CEILING)

    band = _risk_band(pd_upper)

    # Expected loss = pd × amount (SCHEMA.md §4.3).
    expected_loss_lakh = round(pd * amount_lakh, 2)

    # ------------------------------------------------------------------
    # Reason text and factors — SCHEMA.md §4.3
    # ------------------------------------------------------------------
    # Build reason_factors with normalised weights that sum to 1.0.
    raw_factors = []
    raw_factors.append({
        "kind": "buyer_grade",
        "detail": f"Buyer rated {buyer['credit_grade']}",
        "raw": abs(B_GRADE * grade_pen),
    })
    raw_factors.append({
        "kind": "payment_history",
        "detail": f"{delay}-day average delay",
        "raw": abs(B_DELAY * min(delay / DELAY_REF_DAYS, 1.0)),
    })
    raw_factors.append({
        "kind": "tenor",
        "detail": f"{tenor_days}-day tenor",
        "raw": abs(B_TENOR * min(tenor_days / TENOR_REF_DAYS, 1.0)),
    })

    # Only include the unverified-fields factor if there are unknown fields.
    if unknown_field_count > 0:
        raw_factors.append({
            "kind": "unverified_fields",
            "detail": "Delivery confirmation unavailable"
            if unknown_field_count == 1
            else f"{unknown_field_count} fields unverified",
            "raw": UNKNOWN_FIELD_PENALTY * unknown_field_count,
        })

    # Normalise so weights sum to 1.0.
    total_raw = sum(f["raw"] for f in raw_factors) or 1.0
    reason_factors = [
        {
            "kind": f["kind"],
            "detail": f["detail"],
            "weight": round(f["raw"] / total_raw, 2),
        }
        for f in raw_factors
    ]
    # Adjust last factor so weights sum exactly to 1.0.
    weight_sum = sum(f["weight"] for f in reason_factors)
    if reason_factors:
        reason_factors[-1]["weight"] = round(
            reason_factors[-1]["weight"] + (1.0 - weight_sum), 2
        )

    # Build the summary reason_text.
    parts = [
        f"Buyer rated {buyer['credit_grade']} with a "
        f"{delay}-day average payment delay."
    ]
    if unknown_field_count > 0:
        parts.append(
            "Range is widened because delivery confirmation is unavailable."
        )

    return {
        "pd": round(pd, 4),
        "pd_lower": round(pd_lower, 4),
        "pd_upper": round(pd_upper, 4),
        "uncertainty": round(uncertainty, 4),
        "risk_band": band,
        "expected_loss_lakh": expected_loss_lakh,
        "reason_text": " ".join(parts),
        "reason_factors": reason_factors,
    }
