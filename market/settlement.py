"""Settlement state machine — legal transitions only.

Legal state transitions (SCHEMA.md §4.6):
    matched  → funded
    matched  → cancelled
    funded   → settled
    funded   → late → settled
    funded   → late → defaulted
    funded   → defaulted

Nothing transitions out of settled, defaulted, or cancelled.

Owner: Person B
"""

from __future__ import annotations


class IllegalTransitionError(Exception):
    """Raised when a settlement state transition is not legal."""

    def __init__(self, current_state: str, target_state: str):
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(
            f"Cannot transition from '{current_state}' to '{target_state}'"
        )


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


def advance(match: dict, event: dict, market: dict) -> dict:
    """Transition a match through the settlement state machine.

    Args:
        match: Match dict with current 'state'
        event: settlement event (outcome, days_late, etc.)
        market: full market dict (for liquidity updates)

    Returns:
        Updated match dict with new state.

    Raises:
        IllegalTransitionError: on an invalid transition path.
    """
    raise NotImplementedError("Person B: implement advance()")
