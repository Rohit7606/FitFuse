"""Deferred-acceptance clearing — stable matching, not greedy selection.

Greedy "highest score wins" produces unstable outcomes when several invoices
compete for the same provider's capital. Deferred acceptance produces a
stable match — no supplier/provider pair would both rather defect.

Algorithm:
    1. Each invoice proposes to its highest-fit_score feasible offer not yet rejected
    2. Each provider tentatively holds preferred proposals by risk-adjusted return,
       subject to remaining capacity, and rejects the rest
    3. Rejected invoices propose to their next-best offer
    4. Repeat until no invoice has an unanswered proposal, or MAX_ROUNDS hit

Non-negotiable: ties break by ID ascending. Sorted iteration always.
See AGENTS.md §3.1.

Owner: Person B
"""

from __future__ import annotations


def clear(
    invoice_ids: list[str],
    market: dict,
    scored_results: dict,
    scenario: object | None = None,
) -> dict:
    """Run deferred-acceptance clearing across invoices.

    Returns:
        ClearingResult dict per SCHEMA.md §5.5:
        {
            "matches": [Match...],
            "unmatched": [...],
            "provider_utilisation": [...],
            "summary": { "matched_count", "syndicated_count", "iterations", "stable" }
        }

    Never mutates market. Deep-copy first.
    """
    raise NotImplementedError("Person B: implement clear()")
