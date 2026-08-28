"""Outcome feedback and reallocation — the learning loop.

When a settlement outcome is recorded, five things happen in order:
    1. Update the buyer (avg delay, trend)
    2. Reprice affected invoices (re-assess through engine)
    3. Return or consume liquidity
    4. Adjust provider bid policy (segment learning rate)
    5. Compose summary_text (template-generated, no LLM)

Deep-copy the market first. apply_outcome returns a NEW market,
never mutates the input — this is what keeps the API stateless.

Owner: Person B
"""

from __future__ import annotations

import copy
import math

from engine.assess import assess as engine_assess
from engine.config import (
    DEFAULT_EXPECTED_COMPETITORS,
    DELAY_LEARNING_RATE,
    SEGMENT_LEARNING_RATE,
)
from market.agents import bid_rate, segment_key
from market.settlement import release_liquidity

# Half of the 4dp quantum engine/risk.py rounds pd to. Below this the two
# numbers print identically, so nothing "actually moved" (SCHEMA.md §4.7).
PD_MOVED = 5e-5

# Below a hundredth of a basis point an adjustment is arithmetic noise, not a
# policy change, and reporting it would pad the delta the judge reads.
RATE_MOVED = 1e-6


def apply_outcome(
    match: dict,
    event: dict,
    market: dict,
) -> tuple[dict, dict]:
    """Apply a settlement outcome and return the updated market + delta.

    Args:
        match: the Match that settled/defaulted/was late, already in its
               post-outcome state and already funded — so `market` is the
               funded market, with the advance drawn down.
        event: { "outcome": str, "days_late": int }
        market: current MarketInput dict — NEVER MUTATED

    Returns:
        (updated_market, LearningDelta) — both new dicts.

    The LearningDelta (SCHEMA.md §4.7) is the entire payload for demo step 8.
    """
    updated = copy.deepcopy(market)

    outcome = event.get("outcome")
    days_late = int(event.get("days_late") or 0)

    invoice = _find(updated["invoices"], "invoice_id", match["invoice_id"])
    buyer = _find(updated["buyers"], "buyer_id", invoice["buyer_id"])

    # -----------------------------------------------------------------
    # 1. Update the buyer
    # -----------------------------------------------------------------
    observed = _observed_delay(outcome, days_late, invoice)
    delay_before = buyer.get("avg_payment_delay_days", 0)
    delay_after = _learned_delay(delay_before, observed)
    trend_before = float(buyer.get("payment_delay_trend", 0.0))
    trend_after = float(delay_after - delay_before)

    buyer["avg_payment_delay_days"] = delay_after
    buyer["payment_delay_trend"] = trend_after

    buyer_updates = [{
        "buyer_id": buyer["buyer_id"],
        "name": buyer.get("name", buyer["buyer_id"]),
        "avg_payment_delay_before": delay_before,
        "avg_payment_delay_after": delay_after,
        "payment_delay_trend_before": trend_before,
        "payment_delay_trend_after": trend_after,
        "observed_delay_days": observed,
    }]

    # The invoice itself is closed by the outcome. There is no `defaulted`
    # status in schema.json's Invoice enum, so a write-off stays `financed`
    # and the state lives on the Match — flagged to A and C as a contract gap
    # rather than papered over with a status that would read as repaid.
    if outcome == "settled":
        invoice["status"] = "settled"

    # -----------------------------------------------------------------
    # 2. Reprice affected invoices
    # -----------------------------------------------------------------
    affected_ids = affected_invoice_ids(market, buyer["buyer_id"],
                                        exclude=match["invoice_id"])
    repriced = []
    for invoice_id in affected_ids:
        before = engine_assess(invoice_id, market)["risk"]
        after = engine_assess(invoice_id, updated)["risk"]
        if abs(after["pd"] - before["pd"]) < PD_MOVED:
            continue  # only invoices whose pd actually moved (SCHEMA.md §4.7)
        repriced.append({
            "invoice_id": invoice_id,
            "pd_before": before["pd"],
            "pd_after": after["pd"],
            "band_before": before["risk_band"],
            "band_after": after["risk_band"],
        })

    # -----------------------------------------------------------------
    # 3. Return or consume liquidity
    # -----------------------------------------------------------------
    liquidity_before = _liquidity(updated, match)
    if outcome == "settled":
        updated = release_liquidity(updated, match)
        # release_liquidity rebuilt the market, so re-bind into the new copy.
        invoice = _find(updated["invoices"], "invoice_id", match["invoice_id"])
        buyer = _find(updated["buyers"], "buyer_id", invoice["buyer_id"])
    liquidity_after = _liquidity(updated, match)

    liquidity_updates = [
        {
            "provider_id": pid,
            "name": (_provider(updated, pid) or {}).get("name", pid),
            "available_before_lakh": liquidity_before[pid],
            "available_after_lakh": liquidity_after[pid],
            "returned_lakh": round(liquidity_after[pid] - liquidity_before[pid], 2),
            "reason": _liquidity_reason(outcome),
        }
        for pid in sorted(liquidity_before)
    ]

    # -----------------------------------------------------------------
    # 4. Adjust provider bid policy
    # -----------------------------------------------------------------
    segment = segment_key(invoice, buyer)
    risk_before = engine_assess(match["invoice_id"], market)["risk"]
    risk_after = engine_assess(match["invoice_id"], updated)["risk"]
    trigger_move = {
        "invoice_id": match["invoice_id"],
        "band_before": risk_before["risk_band"],
        "band_after": risk_after["risk_band"],
    }

    bid_adjustments = []
    for pid in sorted({a["provider_id"] for a in match.get("allocations") or []}):
        provider = _provider(updated, pid)
        if provider is None:
            continue
        # The adjustment is literally the change in what this agent's own
        # pricing function now returns on this segment, damped by the learning
        # rate. Anything else would be a second, unexplained pricing model.
        # The shade term is identical on both sides and cancels.
        was = bid_rate(provider, risk_before, DEFAULT_EXPECTED_COMPETITORS)
        now = bid_rate(provider, risk_after, DEFAULT_EXPECTED_COMPETITORS)
        adjustment = round(SEGMENT_LEARNING_RATE * (now - was), 6)
        if abs(adjustment) < RATE_MOVED:
            continue
        # Carried in the market dict, not a module global — the next call to
        # generate_offers() on this market bids the new number.
        learned = provider.setdefault("segment_adjustments", {})
        learned[segment] = round(learned.get(segment, 0.0) + adjustment, 6)
        bid_adjustments.append({
            "provider_id": pid,
            "name": provider.get("name", pid),
            "segment": segment,
            "rate_adjustment": adjustment,
            "reason": _adjustment_reason(outcome, days_late, buyer),
        })

    # -----------------------------------------------------------------
    # 5. Compose summary_text
    # -----------------------------------------------------------------
    delta = {
        "trigger": {
            "match_id": match["match_id"],
            "invoice_id": match["invoice_id"],
            "buyer_id": buyer["buyer_id"],
            "outcome": outcome,
            "days_late": days_late,
            "band_before": trigger_move["band_before"],
            "band_after": trigger_move["band_after"],
        },
        "buyer_updates": buyer_updates,
        "repriced_invoices": repriced,
        "liquidity_updates": liquidity_updates,
        "provider_bid_adjustments": bid_adjustments,
        "summary_text": _summary(buyer, outcome, days_late, repriced,
                                 bid_adjustments, trigger_move),
    }
    return updated, delta


def affected_invoice_ids(market: dict, buyer_id: str, exclude: str) -> list[str]:
    """Every other open invoice on this buyer, sorted.

    Sorted because the delta is compared byte-for-byte in tests and read on
    stage — iteration order must not depend on dict insertion (AGENTS.md §3.1).
    """
    return sorted(
        i["invoice_id"]
        for i in market.get("invoices", [])
        if i["buyer_id"] == buyer_id
        and i["invoice_id"] != exclude
        and i.get("status") == "open"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find(records: list[dict], key: str, value: str) -> dict:
    for record in records:
        if record.get(key) == value:
            return record
    raise KeyError(f"{key}={value} not in market")


def _provider(market: dict, provider_id: str) -> dict | None:
    for provider in market.get("providers", []):
        if provider["provider_id"] == provider_id:
            return provider
    return None


def _liquidity(market: dict, match: dict) -> dict[str, float]:
    ids = {a["provider_id"] for a in match.get("allocations") or []}
    return {
        p["provider_id"]: p.get("available_liquidity_lakh", 0.0)
        for p in market.get("providers", [])
        if p["provider_id"] in ids
    }


def _observed_delay(outcome: str, days_late: int, invoice: dict) -> int:
    """How many days late this outcome says the buyer actually was.

    A default is not "n days late" — the buyer never paid. Taking the invoice's
    own tenor as the observation is the most conservative reading the data
    supports, and it scales with the deal instead of needing a magic constant.
    """
    if outcome == "defaulted":
        return int(invoice.get("tenor_days", 0))
    return max(int(days_late), 0)


def _learned_delay(before: float, observed: int) -> int:
    """Move the buyer's average toward what we just observed, then round up.

    Rounded up, always. The field is an integer count of days and engine/risk.py
    reads it directly, so rounding a rising delay back down would quietly
    un-learn the very thing we just saw: 4 days moving 30% toward an observed 5
    gives 4.3, and reporting that as 4 makes the outcome a no-op.
    """
    moved = before + DELAY_LEARNING_RATE * (observed - before)
    return int(math.ceil(moved - 1e-9))


def _liquidity_reason(outcome: str) -> str:
    if outcome == "settled":
        return "Buyer paid; the committed capital is back on the provider's book."
    if outcome == "late":
        return "Capital stays committed while the invoice is late but recoverable."
    return "Written off; the committed capital is not returned."


def _adjustment_reason(outcome: str, days_late: int, buyer: dict) -> str:
    name = buyer.get("name", buyer["buyer_id"])
    if outcome == "defaulted":
        return f"{name} defaulted on this segment."
    if days_late > 0:
        return f"Observed a {days_late}-day delay on {name}."
    return f"{name} paid on time on this segment."


def _summary(buyer: dict, outcome: str, days_late: int, repriced: list[dict],
             adjustments: list[dict], trigger: dict | None = None) -> str:
    """Template-generated, no LLM. What happened, what repriced, who repriced it."""
    name = buyer.get("name", buyer["buyer_id"])

    if outcome == "defaulted":
        opening = f"{name} defaulted."
    elif days_late > 0:
        opening = f"{name} paid {days_late} days late."
    else:
        opening = f"{name} paid on time."

    if trigger and trigger["band_before"] != trigger["band_after"]:
        opening += (f" {trigger['invoice_id']} moved from "
                    f"{trigger['band_before']} to {trigger['band_after']}.")

    if not repriced:
        middle = "No other open invoice on that buyer changed price."
    else:
        plural = "s" if len(repriced) != 1 else ""
        verb = "were" if len(repriced) != 1 else "was"
        middle = (f"{len(repriced)} other open invoice{plural} on that buyer "
                  f"{verb} repriced")
        crossed = [r for r in repriced if r["band_before"] != r["band_after"]]
        if crossed:
            worst = crossed[0]
            middle += (f", {len(crossed)} of them across a risk band "
                       f"({worst['invoice_id']} {worst['band_before']} → "
                       f"{worst['band_after']})")
        middle += "."

    if not adjustments:
        closing = "No provider changed its bid on this segment."
    else:
        lead = adjustments[0]
        bps = lead["rate_adjustment"] * 10_000
        verb = "raised" if bps >= 0 else "lowered"
        if len(adjustments) == 1:
            who, what = lead["name"], "its next bid"
        else:
            others = len(adjustments) - 1
            who = (f"{lead['name']} and {others} other "
                   f"provider{'s' if others > 1 else ''}")
            what = "their next bids"
        points = "point" if abs(round(bps)) == 1 else "points"
        closing = (f"{who} {verb} {what} on {lead['segment']} by "
                   f"{abs(bps):.0f} basis {points}.")

    return f"{opening} {middle} {closing}"
