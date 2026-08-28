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
import json

from engine.assess import UnknownEntityError
from engine.assess import assess as engine_assess
from engine.assess import score_offers as engine_score_offers
from market.agents import generate_offers as agents_generate_offers
from market.agents import segment_key
from market.clearing import match_id_for, run_clearing
from market.learning import apply_outcome
from market.settlement import (
    SETTLEMENT_OUTCOMES,
    IllegalTransitionError,
    advance,
    commit_liquidity,
)


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

    Returns UNSCORED Offer dicts (SCHEMA.md §4.5) — rate, advance, speed, fees,
    structure and committed amount, with no fit_score, feasible or
    rejection_reason. Pricing is the agents' job; valuing an offer for a
    particular supplier is engine/scoring.py's.

    Callers that need ScoredOffers should use scored_offers() below rather than
    calling engine.score_offers() themselves — clearing and /api/offers must
    never score the same invoice two different ways.
    """
    invoice = _find(market.get("invoices", []), "invoice_id", invoice_id)
    buyer = _find(market.get("buyers", []), "buyer_id", invoice["buyer_id"])
    providers = _with_liquidity_overrides(market.get("providers", []), scenario)
    # The segment is what an agent has learned over; on a market straight off
    # disk no provider has any adjustment and this changes nothing.
    return agents_generate_offers(providers, invoice, assessment,
                                  segment=segment_key(invoice, buyer))


def scored_offers(
    invoice_id: str,
    market: dict,
    assessment: dict,
    scenario: object | None = None,
) -> dict:
    """The seam: agents bid, then Person A's engine values those bids.

    This is the one place the two halves of the system meet. market/ decides
    what each provider will offer; engine/ decides what those offers are worth
    to this supplier. Both clear() and /api/offers go through here, so a single
    invoice can never be scored two different ways depending on which endpoint
    asked (AGENTS.md §2.1 wants this seam to be one explicit signature).

    Returns:
        { "offers": [ScoredOffer...], "ranking": [...],
          "naive_ranking": [...], "summary": {...} }  — SCHEMA.md §5.4
    """
    raw = generate_offers(invoice_id, market, assessment, scenario)
    preferences = resolve_preferences(invoice_id, market, scenario)
    return engine_score_offers(raw, assessment, preferences)


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
    exposure_by_invoice: dict[str, dict] = {}
    rejected: list[dict] = []

    # Deduplicated, not just sorted. Asking to clear the same invoice twice is
    # the same request, but iterating it twice matched it twice under one
    # match_id and committed the providers' capital against both.
    for invoice_id in sorted(set(invoice_ids)):
        invoice = _find(market.get("invoices", []), "invoice_id", invoice_id)
        assessment = engine_assess(invoice_id, market, scenario)

        if assessment["verification"]["status"] == "rejected":
            rejected.append({
                "invoice_id": invoice_id,
                "reason": assessment["verification"]["reason_text"],
            })
            continue

        scored = scored_offers(invoice_id, market, assessment, scenario)

        buyer = _find(market.get("buyers", []), "buyer_id", invoice["buyer_id"])
        invoices.append(invoice)
        exposure_by_invoice[invoice_id] = {
            "buyer_id": buyer["buyer_id"],
            "sector": buyer.get("sector", "unknown"),
        }
        offers_by_invoice[invoice_id] = scored["offers"]
        eligibility_by_invoice[invoice_id] = {
            e["provider_id"]: e for e in assessment["eligibility"]
        }
        risk_by_invoice[invoice_id] = assessment["risk"]

    result = run_clearing(invoices, offers_by_invoice, providers,
                          eligibility_by_invoice, risk_by_invoice,
                          exposure_by_invoice)

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

    There is no stored match to look up — the API holds no state (AGENTS.md
    §3.4) — so the match is reconstructed by clearing its invoice again. That
    is only well-defined because match_id is a function of the invoice rather
    than of clearing order; see clearing.match_id_for.
    """
    if outcome not in SETTLEMENT_OUTCOMES:
        raise IllegalTransitionError(
            "funded", outcome,
            f"'{outcome}' is not a settlement outcome; expected one of "
            f"{', '.join(SETTLEMENT_OUTCOMES)}.",
        )

    market = copy.deepcopy(market)
    invoice_id = invoice_id_for_match(match_id, market)

    cleared = clear([invoice_id], market, scenario)
    if not cleared["matches"]:
        reason = next((u["reason"] for u in cleared["unmatched"]
                       if u["invoice_id"] == invoice_id), "no provider matched it")
        raise IllegalTransitionError(
            "cancelled", outcome,
            f"{match_id} has no match to settle: {invoice_id} did not clear — "
            f"{reason}",
        )
    match = cleared["matches"][0]

    # matched is not funded. Settling walks the state machine properly rather
    # than jumping states, so a match that cannot be funded fails here with a
    # reason instead of silently settling money that never moved.
    event = {"outcome": outcome, "days_late": days_late}
    funded_match = advance(match, {"outcome": "funded"}, market)
    funded_market = commit_liquidity(market, match)

    settled_match = advance(funded_match, event, funded_market)
    after_market, delta = apply_outcome(settled_match, event, funded_market)

    # The same invoice set on both sides, so before and after line up row for
    # row in the UI. The settled invoice leads; the rest are the ones the
    # outcome repriced.
    affected = [invoice_id] + [r["invoice_id"] for r in delta["repriced_invoices"]]

    return {
        "before": {
            "match": funded_match,
            "affected_invoices": _risk_profiles(affected, funded_market),
        },
        "after": {
            "match": settled_match,
            "affected_invoices": _risk_profiles(affected, after_market),
        },
        "delta": delta,
    }


def invoice_id_for_match(match_id: str, market: dict) -> str:
    """Which invoice a match_id refers to, or raise so the API returns a 400."""
    for invoice in sorted(market.get("invoices", []),
                          key=lambda i: i["invoice_id"]):
        try:
            candidate = match_id_for(invoice["invoice_id"])
        except ValueError:
            continue
        if candidate == match_id:
            return invoice["invoice_id"]
    raise UnknownEntityError(match_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _risk_profiles(invoice_ids: list[str], market: dict) -> list[dict]:
    """RiskProfiles for a set of invoices, each tagged with its invoice_id.

    SCHEMA.md §5.6 types affected_invoices as a bare RiskProfile list, but a
    RiskProfile carries no id — three of them side by side would be unlabelled
    on screen. schema.json allows the extra property, so it is added rather
    than leaving the frontend to infer identity from array position.
    """
    profiles = []
    for invoice_id in invoice_ids:
        risk = dict(engine_assess(invoice_id, market)["risk"])
        risk["invoice_id"] = invoice_id
        profiles.append(risk)
    return profiles


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


# ---------------------------------------------------------------------------
# CLI — `python -m market.simulate data/mock/market.json` (AGENTS.md §5.2)
# ---------------------------------------------------------------------------

def _main(argv: list[str] | None = None) -> int:
    """Run one invoice end to end and print the result as JSON.

    AGENTS.md §5.2 documents this command. It printed nothing at all until
    now, because the module had no entry point — the determinism check in the
    same section was diffing two empty files against each other.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="market.simulate",
                                     description="Run the market simulator end to end.")
    parser.add_argument("market", help="path to market.json")
    parser.add_argument("--invoice", default="INV001", help="invoice to run")
    parser.add_argument("--settle", metavar="OUTCOME",
                        choices=("settled", "late", "defaulted"),
                        help="also settle the resulting match with this outcome")
    parser.add_argument("--days-late", type=int, default=5)
    args = parser.parse_args(argv)

    with open(args.market, encoding="utf-8") as handle:
        market = json.load(handle)

    assessment = engine_assess(args.invoice, market)
    result = {
        "invoice_id": args.invoice,
        "assessment": assessment,
        **scored_offers(args.invoice, market, assessment),
        "clearing": clear([args.invoice], market),
    }
    if args.settle:
        match = result["clearing"]["matches"]
        if not match:
            raise SystemExit(f"{args.invoice} did not clear; nothing to settle.")
        result["settlement"] = settle(match[0]["match_id"], args.settle,
                                      args.days_late, market)

    # sort_keys so two runs are byte-identical and the documented determinism
    # check actually checks something (AGENTS.md §3.1).
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
