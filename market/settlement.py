"""Settlement state machine — legal transitions only.

Legal state transitions (SCHEMA.md §4.6):
    matched  → funded
    matched  → cancelled
    funded   → settled
    funded   → late → settled
    funded   → late → defaulted
    funded   → defaulted

Nothing transitions out of settled, defaulted, or cancelled.

`matched` is not `funded`. Selecting an offer does not complete a financing,
and that is enforced here rather than trusted to the caller — asking to settle
a match that was never funded is a 400, not a silent success.

Division of labour with market/learning.py: this module owns the *funding*
drawdown, because disbursing cash is a settlement act. learning.py owns the
liquidity movement that an *outcome* causes (PERSON_B.md §3.4 step 3).

Owner: Person B
"""

from __future__ import annotations

import copy

from engine.config import EPSILON

# Legal transitions — no others are permitted
LEGAL_TRANSITIONS = {
    "matched":   {"funded", "cancelled"},
    "funded":    {"settled", "late", "defaulted"},
    "late":      {"settled", "defaulted"},
    # Terminal states — nothing out
    "settled":   set(),
    "defaulted": set(),
    "cancelled": set(),
}

TERMINAL_STATES = frozenset({"settled", "defaulted", "cancelled"})

# The outcomes /api/settle accepts. `funded` and `cancelled` are reached by
# settling's own sequencing, not by asking for them as an outcome.
SETTLEMENT_OUTCOMES = ("settled", "late", "defaulted")

# Rounding tolerance on money, in lakh. A lakh is ₹100,000, so this is ₹500 —
# the same 2dp quantum clearing rounds allocations to.
MONEY_TOLERANCE = 0.005


class IllegalTransitionError(Exception):
    """Raised when a settlement state transition is not legal.

    `detail` is read by a human under time pressure (PERSON_B.md §5), so it
    says what to do about it rather than restating the state names.
    """

    def __init__(self, current_state: str, target_state: str,
                 detail: str | None = None):
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(
            detail or f"Cannot transition from '{current_state}' to '{target_state}'"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def advance(match: dict, event: dict, market: dict) -> dict:
    """Transition a match through the settlement state machine.

    Args:
        match: Match dict with current 'state'
        event: settlement event; 'outcome' names the target state, and
               'days_late' is carried onto the resulting match
        market: full market dict — read only, to check funding conditions

    Returns:
        A NEW match dict in the target state. The input is never mutated.

    Raises:
        IllegalTransitionError: on an invalid transition path, or when funding
            conditions are not met on matched → funded.
    """
    target = event.get("outcome") or event.get("target_state")
    current = match.get("state")

    if target not in LEGAL_TRANSITIONS.get(current, set()):
        raise IllegalTransitionError(current, target, _explain(current, target))

    if target == "funded":
        problems = funding_shortfalls(match, market)
        if problems:
            # Funding conditions not met is exactly the case SCHEMA.md §4.6
            # routes to `cancelled`. Saying so beats a bare refusal.
            raise IllegalTransitionError(
                current, target,
                "Funding conditions are not met, so this match cannot be funded: "
                + "; ".join(problems)
                + ". Cancel it instead.",
            )

    advanced = copy.deepcopy(match)
    advanced["state"] = target

    days_late = int(event.get("days_late") or 0)
    if target in SETTLEMENT_OUTCOMES:
        advanced["days_late"] = days_late

    # The clearing narration explains *why this syndicate*; it stays put so the
    # UI does not lose it between demo steps 7 and 8. The state gets its own
    # sentence alongside it (schema.json allows the extra property).
    advanced["state_reason_text"] = _state_reason(advanced, days_late)
    return advanced


def funding_shortfalls(match: dict, market: dict) -> list[str]:
    """Every reason this match cannot be funded, in provider order.

    An empty list means fund it. Checking capacity again at funding time is
    not paranoia: clearing reserved the capital, and between clearing and
    disbursement a scenario may have drained the provider (demo step 7's
    liquidity slider does exactly that).
    """
    allocations = match.get("allocations") or []
    problems: list[str] = []

    if not allocations:
        return ["the match has no allocations"]

    total = round(sum(a["amount_lakh"] for a in allocations), 2)
    declared = match.get("total_advance_lakh", 0.0)
    if abs(total - declared) > MONEY_TOLERANCE:
        problems.append(
            f"allocations sum to ₹{total:.2f} lakh but the match declares "
            f"₹{declared:.2f} lakh"
        )

    providers = {p["provider_id"]: p for p in market.get("providers", [])}
    needed: dict[str, float] = {}
    for alloc in allocations:
        pid = alloc["provider_id"]
        needed[pid] = needed.get(pid, 0.0) + alloc["amount_lakh"]

    for pid, amount in sorted(needed.items()):
        provider = providers.get(pid)
        if provider is None:
            problems.append(f"{pid} is no longer in the market")
            continue
        available = provider.get("available_liquidity_lakh", 0.0)
        if available + EPSILON < amount:
            problems.append(
                f"{provider['name']} has ₹{available:.2f} lakh available, short of "
                f"the ₹{amount:.2f} lakh it committed"
            )
    return problems


def commit_liquidity(market: dict, match: dict) -> dict:
    """A NEW market with each allocation drawn down from its provider.

    Funding is the moment cash actually leaves a provider's book. Clearing
    deliberately does not do this — a match is not a financing.
    """
    return _move_liquidity(market, match, -1.0)


def release_liquidity(market: dict, match: dict) -> dict:
    """A NEW market with each allocation returned to its provider."""
    return _move_liquidity(market, match, +1.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _move_liquidity(market: dict, match: dict, sign: float) -> dict:
    updated = copy.deepcopy(market)
    by_id = {p["provider_id"]: p for p in updated.get("providers", [])}
    for alloc in match.get("allocations") or []:
        provider = by_id.get(alloc["provider_id"])
        if provider is None:
            continue
        moved = provider.get("available_liquidity_lakh", 0.0) + sign * alloc["amount_lakh"]
        provider["available_liquidity_lakh"] = round(moved, 2)
    return updated


def _explain(current: str | None, target: str | None) -> str:
    """A refusal a human can act on, not a restatement of the state names."""
    if current not in LEGAL_TRANSITIONS:
        return (
            f"'{current}' is not a settlement state; expected one of "
            f"{', '.join(sorted(LEGAL_TRANSITIONS))}."
        )
    if current in TERMINAL_STATES:
        return (
            f"A match in state '{current}' is closed; nothing transitions out "
            f"of it, so it cannot become '{target}'."
        )
    if current == "matched" and target in SETTLEMENT_OUTCOMES:
        return "Cannot settle a match in state 'matched'; fund it first."
    if target not in LEGAL_TRANSITIONS:
        return (
            f"'{target}' is not a settlement state; expected one of "
            f"{', '.join(sorted(LEGAL_TRANSITIONS))}."
        )
    return (
        f"Cannot transition from '{current}' to '{target}'; the legal next "
        f"states are {', '.join(sorted(LEGAL_TRANSITIONS[current]))}."
    )


def _state_reason(match: dict, days_late: int) -> str:
    """One sentence naming what the current state means for the money."""
    state = match["state"]
    amount = match.get("total_advance_lakh", 0.0)
    slices = len(match.get("allocations") or [])

    if state == "funded":
        across = f" across {slices} providers" if slices > 1 else ""
        return f"Funded — ₹{amount:.2f} lakh disbursed to the supplier{across}."
    if state == "settled":
        when = "on time" if days_late <= 0 else f"{days_late} days late"
        return f"Buyer paid {when}; the financing is closed."
    if state == "late":
        return (
            f"Past due by {days_late} days. Not written off — ₹{amount:.2f} lakh "
            "stays committed while it is still recoverable."
        )
    if state == "defaulted":
        return f"Written off — ₹{amount:.2f} lakh not recovered."
    if state == "cancelled":
        return "Cancelled before disbursement; no money moved."
    return f"State is '{state}'."
