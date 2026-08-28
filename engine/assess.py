"""The single public entry point for the valuation engine.

Provides two functions for Person B's market and API:
    assess()       — verify, score risk, determine eligibility
    score_offers() — score and rank competing offers

Owner: Person A
Reviewer: Person B
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from engine.config import WEIGHT_SUM_TOLERANCE
from engine.eligibility import check_eligibility
from engine.errors import InvalidWeightsError, UnknownEntityError
from engine.risk import score_risk
from engine.scoring import score_offers as _score_offers
from engine.verify import verify

# ---------------------------------------------------------------------------
# Custom exceptions — B maps these to HTTP 400 in api/errors.py.
# Defined in engine/errors.py and re-exported here, which is the import path
# PERSON_A.md §2 gives Person B. They cannot live in this module: verify.py
# raises UnknownEntityError and this module imports verify.py.
# ---------------------------------------------------------------------------

__all__ = [
    "InvalidWeightsError",
    "LiquidityOverride",
    "PreferenceOverride",
    "Scenario",
    "UnknownEntityError",
    "assess",
    "score_offers",
]


# ---------------------------------------------------------------------------
# Scenario — frozen and tuple-based so it cannot be mutated mid-scoring
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PreferenceOverride:
    supplier_id: str
    weights: dict
    urgent: bool = False


@dataclass(frozen=True)
class LiquidityOverride:
    provider_id: str
    available_liquidity_lakh: float


@dataclass(frozen=True)
class Scenario:
    """Immutable scenario for preference and liquidity overrides.

    Frozen and tuple-based so it cannot be mutated mid-scoring.
    """
    preference_overrides: tuple[PreferenceOverride, ...] = ()
    liquidity_overrides: tuple[LiquidityOverride, ...] = ()
    naive_mode: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess(
    invoice_id: str,
    market: dict,
    scenario: Scenario | None = None,
) -> dict:
    """Verify an invoice, score its risk, and determine provider eligibility.

    Args:
        invoice_id: must exist in market["invoices"]
        market:     MarketInput dict, validated against schema.json
        scenario:   preference and liquidity overrides; None means baseline

    Returns:
        Assessment dict per SCHEMA.md §4.1, validated against schema.json

    Pure. Deterministic. No I/O, no globals, no mutation of the input.
    """
    # Deep-copy before anything else. Callers hand us the shared market dict
    # and the API is stateless — mutating it here would leak between requests.
    market = copy.deepcopy(market)

    invoice = _find(market.get("invoices", []), "invoice_id", invoice_id)
    supplier = _find(market.get("suppliers", []), "supplier_id",
                     invoice["supplier_id"])
    buyer = _find(market.get("buyers", []), "buyer_id", invoice["buyer_id"])

    supplier = _apply_preference_override(supplier, scenario)
    _validate_weights(supplier)

    verification = verify(invoice_id, market)

    if verification["status"] == "rejected":
        # A rejected invoice produces no risk score and no offers
        # (PERSON_A.md §3.1). schema.json still requires the risk and
        # eligibility keys, so they are present but deliberately empty of
        # any claim — never a number that could be mistaken for an estimate.
        return {
            "invoice_id": invoice_id,
            "verification": verification,
            "risk": _no_risk(verification),
            "eligibility": [],
            "meta": {"assessed": False, "reason": "verification_rejected"},
        }

    risk = score_risk(invoice, supplier, buyer, verification)
    eligibility = check_eligibility(invoice, supplier, risk,
                                    market.get("providers", []), scenario)

    return {
        "invoice_id": invoice_id,
        "verification": verification,
        "risk": risk,
        "eligibility": eligibility,
        "meta": {"assessed": True, "schema_version":
                 market.get("meta", {}).get("schema_version", "1.1")},
    }


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
                "best_fit_offer_id": str,
                "lowest_rate_offer_id": str,
                "fit_beats_rate": bool
            }
        }

    Infeasible offers are returned with feasible=false, never dropped.
    """
    if not isinstance(preferences, dict) or "weights" not in preferences:
        raise InvalidWeightsError(0.0)
    total = sum(preferences["weights"].values())
    if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
        raise InvalidWeightsError(total)

    # Never mutate the caller's offers — market/agents.py reuses them.
    return _score_offers(copy.deepcopy(offers), assessment, preferences)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find(records: list[dict], key: str, value: str) -> dict:
    """Look up one record by id, or raise so the API can map it to a 400."""
    for record in records:
        if record.get(key) == value:
            return record
    raise UnknownEntityError(value)


def _validate_weights(supplier: dict) -> None:
    weights = supplier.get("preferences", {}).get("weights")
    if not weights:
        return
    total = sum(weights.values())
    if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
        raise InvalidWeightsError(total)


def _apply_preference_override(supplier: dict, scenario: Scenario | None) -> dict:
    """Overlay a scenario's slider weights onto this supplier.

    Returns a new supplier — the scenario arrives in the request body and must
    never write back into the market (AGENTS.md §3.4).
    """
    if scenario is None:
        return supplier
    overrides = getattr(scenario, "preference_overrides", None)
    if overrides is None and isinstance(scenario, dict):
        overrides = scenario.get("preference_overrides")
    for override in overrides or ():
        sid = getattr(override, "supplier_id", None)
        if sid is None and isinstance(override, dict):
            sid = override.get("supplier_id")
        if sid != supplier["supplier_id"]:
            continue
        weights = getattr(override, "weights", None)
        if weights is None and isinstance(override, dict):
            weights = override.get("weights")
        urgent = getattr(override, "urgent", None)
        if urgent is None and isinstance(override, dict):
            urgent = override.get("urgent")
        supplier = copy.deepcopy(supplier)
        prefs = supplier.setdefault("preferences", {})
        if weights:
            prefs["weights"] = dict(weights)
            prefs["preset"] = "custom"
        if urgent is not None:
            prefs["urgent"] = bool(urgent)
    return supplier


def _no_risk(verification: dict) -> dict:
    """A schema-valid RiskProfile that makes no claim, for a rejected invoice.

    Zeroed rather than omitted because schema.json requires the key, and a
    fabricated estimate on an invoice we refused to verify would be worse than
    no number at all.
    """
    return {
        "pd": 0.0,
        "pd_lower": 0.0,
        "pd_upper": 0.0,
        "uncertainty": 0.0,
        "risk_band": "decline",
        "expected_loss_lakh": 0.0,
        "reason_text": (
            "Not assessed — " + verification.get("reason_text", "verification failed")
        ),
        "reason_factors": [],
    }
