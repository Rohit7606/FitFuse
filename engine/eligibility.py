"""Provider eligibility — who may see an opportunity, and why not.

For every provider, produces a ProviderEligibility (SCHEMA.md §4.4) —
including the ineligible ones, with reasons.

Excluded providers are returned, not filtered out. The visible reasoning
is a large part of the product's credibility.

Owner: Person A
"""

from __future__ import annotations


def check_eligibility(
    invoice: dict,
    supplier: dict,
    risk: dict,
    providers: list[dict],
    scenario: object | None = None,
) -> list[dict]:
    """Determine eligibility for every provider.

    Checks run in fixed order; the first failure is the binding_constraint.
    See PERSON_A.md §3.3 for the full check sequence.

    Args:
        invoice: invoice record
        supplier: supplier record (for preferences → advance_needed)
        risk: RiskProfile dict
        providers: all providers from the market
        scenario: optional liquidity overrides

    Returns:
        list of ProviderEligibility dicts — one per provider,
        including ineligible with exclusion_reason and binding_constraint.
    """
    raise NotImplementedError("Person A: implement check_eligibility()")
