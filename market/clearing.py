"""Deferred-acceptance clearing with syndication.

Greedy "highest score wins" produces unstable outcomes when several invoices
compete for the same provider's capital: a provider's budget gets committed to
invoice A when it would have preferred invoice B, and B's supplier would have
preferred that provider. Deferred acceptance produces a stable match — no
supplier/provider pair would both rather defect. That stability argument is
one of the strongest answers available in Q&A, so it is worth the extra code
(PERSON_B.md §3.2).

Every loop iterates in sorted ID order and every tie breaks by ID ascending.
Determinism is mandatory — AGENTS.md §3.1.

Owner: Person B
"""

from __future__ import annotations

from engine.config import EPSILON, MAX_ROUNDS


def _risk_adjusted_return(offer: dict, risk: dict) -> float:
    """How much a provider wants this deal, per rupee committed.

    Providers rank proposals by this; suppliers rank offers by fit_score. The
    two sides wanting different things is what makes the match non-trivial.
    """
    expected_loss = risk.get("pd", 0.0)
    return offer["rate_annual"] - expected_loss


def _capacity(provider: dict, eligibility: dict) -> float:
    """What this provider may still commit, respecting every binding limit."""
    return min(
        provider.get("available_liquidity_lakh", 0.0),
        eligibility.get("max_fundable_lakh", 0.0),
    )


def _blend(allocations: list[dict], offers_by_id: dict, amount_lakh: float) -> tuple:
    """Weighted-average rate and summed cost across a syndicate.

    Each slice is costed at its own provider's terms — a syndicate is several
    financings that happen to share an invoice, not one financing at an
    averaged rate.
    """
    total = sum(a["amount_lakh"] for a in allocations)
    if total <= 0:
        return 0.0, 0.0

    weighted_rate = 0.0
    cost = 0.0
    for alloc in allocations:
        offer = offers_by_id[alloc["offer_id"]]
        amount = alloc["amount_lakh"]
        weighted_rate += amount * offer["rate_annual"]
        financing = amount * offer["rate_annual"] * (offer["tenor_days"] / 365)
        fees = amount_lakh * offer.get("fee_percent", 0.0) * (amount / total)
        cost += financing + fees + offer.get("fee_flat_lakh", 0.0) * (amount / total)

    return round(weighted_rate / total, 4), round(cost, 5)


def _settle_residual(allocations: list[dict], target: float) -> None:
    """Force allocations to sum to exactly `target`, in place.

    Rounding each slice independently leaves stray paise, and schema.json
    requires the allocations to sum to total_advance_lakh exactly. The residual
    goes to the largest slice, where it is proportionally least distorting.
    """
    for alloc in allocations:
        alloc["amount_lakh"] = round(alloc["amount_lakh"], 2)
    drift = round(target - sum(a["amount_lakh"] for a in allocations), 2)
    if abs(drift) >= 0.005:
        largest = max(allocations, key=lambda a: (a["amount_lakh"], a["provider_id"]))
        largest["amount_lakh"] = round(largest["amount_lakh"] + drift, 2)


def _syndicate(
    invoice_id: str,
    ranked: list[dict],
    offers_by_id: dict,
    capacity: dict,
    amount_lakh: float,
) -> tuple[list[dict], float]:
    """Fill `advance_needed` from the ranked offers, best fit first.

    Syndication is not a nice-to-have. Thin liquidity is the historical killer
    of invoice marketplaces — single-invoice auction platforms have closed for
    exactly this reason. Splitting a deal is the answer, and it is demo step 7.
    """
    if not ranked:
        return [], 0.0

    # The supplier accepts the winning offer's terms, so the amount to raise is
    # that offer's advance — not the supplier's minimum floor.
    advance_needed = ranked[0]["advance_amount_lakh"]
    remaining = advance_needed
    allocations = []

    for offer in ranked:
        if remaining <= EPSILON:
            break
        take = min(offer["amount_committed_lakh"], capacity[offer["provider_id"]],
                   remaining)
        if take <= EPSILON:
            continue
        allocations.append({
            "provider_id": offer["provider_id"],
            "amount_lakh": take,
            "offer_id": offer["offer_id"],
        })
        capacity[offer["provider_id"]] -= take
        remaining -= take

    return allocations, remaining


def run_clearing(
    invoices: list[dict],
    offers_by_invoice: dict[str, list[dict]],
    providers: list[dict],
    eligibility_by_invoice: dict[str, dict],
    risk_by_invoice: dict[str, dict],
) -> dict:
    """Deferred acceptance across every invoice, then syndicate each match.

    Args:
        offers_by_invoice: scored offers per invoice; each carries fit_score
                           and feasible from engine/scoring.py.

    Returns:
        ClearingResult per SCHEMA.md §5.5.
    """
    provider_by_id = {p["provider_id"]: p for p in providers}

    # Remaining capacity is tracked per provider across the whole run, and
    # re-checked on every hold — tentative holds accumulate within a round, so
    # checking only at round start over-allocates.
    capacity = {}
    for pid, provider in sorted(provider_by_id.items()):
        caps = [
            _capacity(provider, elig.get(pid, {}))
            for elig in eligibility_by_invoice.values()
            if pid in elig
        ]
        capacity[pid] = max(caps) if caps else 0.0

    # Suppliers rank by fit; each invoice works down its own preference list.
    preferences = {}
    for invoice in sorted(invoices, key=lambda i: i["invoice_id"]):
        feasible = [o for o in offers_by_invoice.get(invoice["invoice_id"], [])
                    if o.get("feasible", True)]
        preferences[invoice["invoice_id"]] = sorted(
            feasible, key=lambda o: (-o.get("fit_score", 0.0), o["offer_id"])
        )

    proposal_index = {i["invoice_id"]: 0 for i in invoices}
    held: dict[str, str] = {}   # provider_id -> invoice_id currently held
    unassigned = sorted(preferences)
    iterations = 0
    stable = True

    while unassigned:
        iterations += 1
        if iterations > MAX_ROUNDS:
            # Deferred acceptance provably terminates; MAX_ROUNDS is a safety
            # net, not a design assumption. Reaching it is a bug, so say so
            # rather than pretending the result is stable.
            stable = False
            break

        still_unassigned = []
        for invoice_id in sorted(unassigned):
            ranked = preferences[invoice_id]
            idx = proposal_index[invoice_id]
            if idx >= len(ranked):
                continue  # exhausted its list; will end up unmatched
            offer = ranked[idx]
            pid = offer["provider_id"]
            incumbent = held.get(pid)

            if incumbent is None:
                held[pid] = invoice_id
                continue

            risk = risk_by_invoice.get(invoice_id, {})
            challenger_value = _risk_adjusted_return(offer, risk)
            incumbent_offer = next(
                (o for o in preferences[incumbent] if o["provider_id"] == pid), None
            )
            incumbent_value = (
                _risk_adjusted_return(incumbent_offer, risk_by_invoice.get(incumbent, {}))
                if incumbent_offer else -1.0
            )

            # Ties break by invoice_id ascending, so the outcome never depends
            # on iteration order.
            if (challenger_value, incumbent) > (incumbent_value, invoice_id):
                held[pid] = invoice_id
                proposal_index[incumbent] += 1
                still_unassigned.append(incumbent)
            else:
                proposal_index[invoice_id] += 1
                still_unassigned.append(invoice_id)

        unassigned = [i for i in still_unassigned
                      if proposal_index[i] < len(preferences[i])]

    matches = []
    unmatched = []
    committed: dict[str, float] = {pid: 0.0 for pid in provider_by_id}

    for n, invoice in enumerate(sorted(invoices, key=lambda i: i["invoice_id"]), 1):
        invoice_id = invoice["invoice_id"]
        ranked = preferences[invoice_id]
        offers_by_id = {o["offer_id"]: o for o in ranked}

        allocations, shortfall = _syndicate(
            invoice_id, ranked, offers_by_id, capacity, invoice["amount_lakh"]
        )

        if not allocations or shortfall > EPSILON:
            for alloc in allocations:  # hand back what we tentatively took
                capacity[alloc["provider_id"]] += alloc["amount_lakh"]
            unmatched.append({
                "invoice_id": invoice_id,
                "reason": (
                    "No provider had capacity within the supplier's advance floor."
                    if not allocations else
                    f"Providers could fund only ₹{ranked[0]['advance_amount_lakh'] - shortfall:.2f} "
                    f"lakh of the ₹{ranked[0]['advance_amount_lakh']:.2f} lakh advance."
                ),
            })
            continue

        total_advance = round(sum(a["amount_lakh"] for a in allocations), 2)
        _settle_residual(allocations, total_advance)
        for alloc in allocations:
            committed[alloc["provider_id"]] += alloc["amount_lakh"]

        blended_rate, blended_cost = _blend(allocations, offers_by_id,
                                            invoice["amount_lakh"])
        top = ranked[0]
        syndicated = len(allocations) > 1

        if syndicated:
            lead = provider_by_id[allocations[0]["provider_id"]]["name"]
            rest = ", ".join(
                f"{provider_by_id[a['provider_id']]['name']} funds ₹{a['amount_lakh']:.2f} lakh"
                for a in allocations[1:]
            )
            reason = (f"{lead} funds ₹{allocations[0]['amount_lakh']:.2f} lakh at its "
                      f"capacity limit; {rest}.")
        else:
            reason = (f"{provider_by_id[allocations[0]['provider_id']]['name']} funds the "
                      f"full ₹{total_advance:.2f} lakh advance.")

        matches.append({
            "match_id": f"MCH{n:03d}",
            "invoice_id": invoice_id,
            "allocations": allocations,
            "syndicated": syndicated,
            "total_advance_lakh": total_advance,
            "blended_rate_annual": blended_rate,
            "blended_cost_lakh": blended_cost,
            "supplier_fit_score": round(top.get("fit_score", 0.0), 4),
            # Selecting an offer is not financing — this starts at "matched"
            # and only settlement.py may advance it. SCHEMA.md §4.6.
            "state": "matched",
            "days_to_settle": top["days_to_settle"],
            "reason_text": reason,
        })

    utilisation = []
    for pid, provider in sorted(provider_by_id.items()):
        liquidity = provider.get("available_liquidity_lakh", 0.0)
        used = round(committed[pid], 2)
        utilisation.append({
            "provider_id": pid,
            "committed_lakh": used,
            "remaining_lakh": round(liquidity - used, 2),
            "utilisation": round(used / liquidity, 4) if liquidity else 0.0,
        })

    return {
        "matches": matches,
        "unmatched": unmatched,
        "provider_utilisation": utilisation,
        "summary": {
            "matched_count": len(matches),
            "syndicated_count": sum(1 for m in matches if m["syndicated"]),
            "iterations": iterations,
            "stable": stable,
        },
    }
