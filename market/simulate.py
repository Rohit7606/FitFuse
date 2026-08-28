"""Market simulator — the single public entry point for market/.

Pure and deterministic, same rules as engine. Never mutate market.

This is the seam between Person A's valuation engine and Person B's market:
engine/ decides what an offer is worth, market/ decides who wins. Nothing
here invents a valuation, and nothing in engine/ picks a winner.

Owner: Person B
Reviewer: Person A
"""

from __future__ import annotations

import copy

from engine.assess import UnknownEntityError
from engine.assess import assess as engine_assess
from engine.assess import score_offers as engine_score_offers
from market.agents import generate_offers as agents_generate_offers
from market.clearing import run_clearing


def resolve_preferences(
    invoice_id: str,
    market: dict,
    scenario: object | None = None,
) -> dict:
    """The supplier preferences in force for this invoice, sliders included.

    assess() applies scenario overrides internally, but score_offers() needs
    the same resolved preferences separately — so the resolution lives in one
    place rather than being reimplemented on each side of the seam.
    """
    invoice = _find(market.get("invoices", []), "invoice_id", invoice_id)
    supplier = _find(market.get("suppliers", []), "supplier_id",
                     invoice["supplier_id"])
    preferences = copy.deepcopy(supplier.get("preferences", {}))

    for override in _overrides(scenario, "preference_overrides"):
        if _attr(override, "supplier_id") != supplier["supplier_id"]:
            continue
        weights = _attr(override, "weights")
        if weights:
            preferences["weights"] = dict(weights)
            preferences["preset"] = "custom"
        urgent = _attr(override, "urgent")
        if urgent is not None:
            preferences["urgent"] = bool(urgent)
    return preferences


def generate_offers(
    invoice_id: str,
    market: dict,
    assessment: dict,
    scenario: object | None = None,
) -> list[dict]:
    """Have all eligible provider agents generate competing offers.

    Returns:
        List of Offer dicts per SCHEMA.md §4.5.
    """
    invoice = _find(market.get("invoices", []), "invoice_id", invoice_id)
    providers = _with_liquidity_overrides(market.get("providers", []), scenario)
    return agents_generate_offers(providers, invoice, assessment)


def clear(
    invoice_ids: list[str],
    market: dict,
    scenario: object | None = None,
) -> dict:
    """Run deferred-acceptance clearing and return stable matches.

    Assesses each invoice through the real engine, collects agent bids, scores
    them for that supplier, then clears. Invoices whose verification failed
    carry no offers and fall through to `unmatched` with the rejection reason,
    rather than being silently dropped.

    Returns:
        ClearingResult dict per SCHEMA.md §5.5.
    """
    market = copy.deepcopy(market)
    providers = _with_liquidity_overrides(market.get("providers", []), scenario)

    invoices = []
    offers_by_invoice: dict[str, list[dict]] = {}
    eligibility_by_invoice: dict[str, dict] = {}
    risk_by_invoice: dict[str, dict] = {}
    rejected: list[dict] = []

    for invoice_id in sorted(invoice_ids):
        invoice = _find(market.get("invoices", []), "invoice_id", invoice_id)
        assessment = engine_assess(invoice_id, market, scenario)

        if assessment["verification"]["status"] == "rejected":
            rejected.append({
                "invoice_id": invoice_id,
                "reason": assessment["verification"]["reason_text"],
            })
            continue

        raw = agents_generate_offers(providers, invoice, assessment)
        preferences = resolve_preferences(invoice_id, market, scenario)
        scored = engine_score_offers(raw, assessment, preferences)

        invoices.append(invoice)
        offers_by_invoice[invoice_id] = scored["offers"]
        eligibility_by_invoice[invoice_id] = {
            e["provider_id"]: e for e in assessment["eligibility"]
        }
        risk_by_invoice[invoice_id] = assessment["risk"]

    result = run_clearing(invoices, offers_by_invoice, providers,
                          eligibility_by_invoice, risk_by_invoice)

    # Rejected invoices belong in unmatched with an honest reason — a caller
    # asking about ten invoices should get ten answers, not silence for some.
    result["unmatched"] = sorted(
        result["unmatched"] + rejected, key=lambda u: u["invoice_id"]
    )
    return result


def settle(
    match_id: str,
    outcome: str,
    days_late: int,
    market: dict,
    scenario: object | None = None,
) -> dict:
    """Advance a match through settlement and return before/after/delta.

    Returns:
        {
            "before": { "match": Match, "affected_invoices": [RiskProfile...] },
            "after":  { "match": Match, "affected_invoices": [RiskProfile...] },
            "delta":  LearningDelta
        }

    Two full evaluations per request is correct. Do not optimise into one.
    """
    raise NotImplementedError("Person B: implement settle() in Phase 3")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find(records: list[dict], key: str, value: str) -> dict:
    for record in records:
        if record.get(key) == value:
            return record
    raise UnknownEntityError(value)


def _attr(obj: object, name: str):
    """Read a field off either a Scenario dataclass or a plain dict."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _overrides(scenario: object | None, name: str) -> tuple:
    if scenario is None:
        return ()
    return _attr(scenario, name) or ()


def _with_liquidity_overrides(providers: list[dict], scenario: object | None) -> list[dict]:
    """Apply the demo's live liquidity drain without touching the market.

    Returns new provider dicts — the scenario arrives in the request body and
    the API is stateless, so it must never write back (AGENTS.md §3.4).
    """
    overrides = {
        _attr(o, "provider_id"): _attr(o, "available_liquidity_lakh")
        for o in _overrides(scenario, "liquidity_overrides")
    }
    if not overrides:
        return sorted(providers, key=lambda p: p["provider_id"])

    adjusted = []
    for provider in sorted(providers, key=lambda p: p["provider_id"]):
        if provider["provider_id"] in overrides:
            provider = {**provider,
                        "available_liquidity_lakh": overrides[provider["provider_id"]]}
        adjusted.append(provider)
    return adjusted
