"""The single public entry point for the valuation engine.

Provides two functions for Person B's market and API:
    assess()       — verify, score risk, determine eligibility
    score_offers() — score and rank competing offers

Owner: Person A
Reviewer: Person B
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Custom exceptions — B maps these to HTTP 400 in api/errors.py
# ---------------------------------------------------------------------------

class UnknownEntityError(Exception):
    """Raised when an invoice_id, provider_id, etc. is not found in the market."""

    def __init__(self, entity_id: str, message: str | None = None):
        self.entity_id = entity_id
        super().__init__(message or f"{entity_id} not in market")


class InvalidWeightsError(Exception):
    """Raised when preference weights do not sum to 1.0 (± tolerance)."""

    def __init__(self, weight_sum: float):
        self.weight_sum = weight_sum
        super().__init__(f"Weights sum to {weight_sum:.2f}, expected 1.0")


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
    raise NotImplementedError("Person A: implement assess()")


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
    raise NotImplementedError("Person A: implement score_offers()")
