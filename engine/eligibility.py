"""Provider eligibility — who may see an opportunity, and why not.

For every provider, produces a ProviderEligibility (SCHEMA.md §4.4) —
including the ineligible ones, with reasons.

Excluded providers are returned, not filtered out. The visible reasoning
is a large part of the product's credibility.

Owner: Person A
"""

from __future__ import annotations

from engine.config import RECOVERY_RATE


def _possessive(name: str) -> str:
    """Return the correct possessive form of a name (e.g. 'Managers\'' vs 'Bank\'s')."""
    return f"{name}'" if name.endswith(("s", "S")) else f"{name}'s"


def check_eligibility(
    invoice: dict,
    supplier: dict,
    risk: dict,
    providers: list[dict],
    scenario: object | None = None,
) -> list[dict]:
    """Determine eligibility for every provider.

    Checks run in fixed order; the first failure is the binding_constraint.
    See PERSON_A.md §3.3 for the full check sequence:
        1. min_ticket      advance_needed >= provider.min_ticket_lakh
        2. max_ticket      advance_needed <= provider.max_ticket_lakh
        3. liquidity       provider.available_liquidity_lakh > 0
        4. risk_appetite   risk.pd_upper <= provider.risk_appetite
        5. sector_limit    headroom_sector > 0
        6. buyer_limit     headroom_buyer > 0
        7. target_return   max_feasible_return(pd, provider) >= provider.target_return

    Args:
        invoice: invoice record from market["invoices"]
        supplier: supplier record from market["suppliers"]
        risk: RiskProfile dict from risk.score_risk()
        providers: all providers from market["providers"]
        scenario: optional Scenario or dict with liquidity overrides

    Returns:
        list of ProviderEligibility dicts — one per provider, sorted by provider_id.
    """
    amount_lakh = invoice["amount_lakh"]
    sector = invoice.get("sector") or supplier.get("sector", "")
    buyer_id = invoice.get("buyer_id", "")
    pd_upper = risk.get("pd_upper", 0.0)
    pd = risk.get("pd", 0.0)

    # Parse liquidity overrides from scenario if present
    liquidity_overrides: dict[str, float] = {}
    if scenario is not None:
        if hasattr(scenario, "liquidity_overrides"):
            for override in scenario.liquidity_overrides:
                if hasattr(override, "provider_id") and hasattr(override, "available_liquidity_lakh"):
                    liquidity_overrides[override.provider_id] = float(override.available_liquidity_lakh)
                elif isinstance(override, dict):
                    liquidity_overrides[override["provider_id"]] = float(override["available_liquidity_lakh"])
        elif isinstance(scenario, dict) and "liquidity_overrides" in scenario:
            for override in scenario["liquidity_overrides"]:
                liquidity_overrides[override["provider_id"]] = float(override["available_liquidity_lakh"])

    eligibility_list = []

    # Sort providers by provider_id for determinism (AGENTS.md §3.1)
    sorted_providers = sorted(providers, key=lambda p: p["provider_id"])

    for provider in sorted_providers:
        pid = provider["provider_id"]
        pname = provider["name"]
        total_portfolio = provider.get("total_portfolio_lakh", 0.0)

        # 1. Ticket size: minimum
        min_ticket = provider.get("min_ticket_lakh", 0.0)
        if amount_lakh < min_ticket:
            eligibility_list.append({
                "provider_id": pid,
                "eligible": False,
                "max_fundable_lakh": 0.00,
                "exclusion_reason": (
                    f"Invoice of ₹{amount_lakh:.2f} lakh is below {_possessive(pname)} "
                    f"₹{min_ticket:.2f} lakh minimum ticket size."
                ),
                "binding_constraint": "min_ticket",
            })
            continue

        # 2. Ticket size: maximum
        max_ticket = provider.get("max_ticket_lakh", float("inf"))
        if amount_lakh > max_ticket:
            eligibility_list.append({
                "provider_id": pid,
                "eligible": False,
                "max_fundable_lakh": 0.00,
                "exclusion_reason": (
                    f"Invoice of ₹{amount_lakh:.2f} lakh exceeds {_possessive(pname)} "
                    f"₹{max_ticket:.2f} lakh maximum ticket size."
                ),
                "binding_constraint": "max_ticket",
            })
            continue

        # 3. Available liquidity (taking scenario overrides into account)
        available_liquidity = liquidity_overrides.get(pid, provider.get("available_liquidity_lakh", 0.0))
        if available_liquidity <= 0:
            eligibility_list.append({
                "provider_id": pid,
                "eligible": False,
                "max_fundable_lakh": 0.00,
                "exclusion_reason": (
                    f"{pname} has ₹{available_liquidity:.2f} lakh available liquidity, "
                    "insufficient to fund new invoices."
                ),
                "binding_constraint": "liquidity",
            })
            continue

        # 4. Risk appetite: compared against pd_upper, never pd itself (SCHEMA.md §4.3, §4.8)
        risk_appetite = provider.get("risk_appetite", 1.0)
        if pd_upper > risk_appetite:
            eligibility_list.append({
                "provider_id": pid,
                "eligible": False,
                "max_fundable_lakh": 0.00,
                "exclusion_reason": (
                    f"Invoice risk (PD upper bound of {pd_upper:.2%}) exceeds "
                    f"{_possessive(pname)} risk appetite of {risk_appetite:.2%}."
                ),
                "binding_constraint": "risk_appetite",
            })
            continue

        # 5. Sector concentration limit
        sector_limits = provider.get("sector_limits", {})
        if sector and sector in sector_limits:
            sector_cap = sector_limits[sector] * total_portfolio
            current_sector_exp = (
                provider.get("current_exposure", {}).get("by_sector", {}).get(sector, 0.0)
            )
            headroom_sector = max(0.0, sector_cap - current_sector_exp)
            if headroom_sector <= 0:
                eligibility_list.append({
                    "provider_id": pid,
                    "eligible": False,
                    "max_fundable_lakh": 0.00,
                    "exclusion_reason": (
                        f"{pname} has reached its {sector.replace('_', ' ')} "
                        f"sector concentration limit (headroom: ₹{headroom_sector:.2f} lakh)."
                    ),
                    "binding_constraint": "sector_limit",
                })
                continue
        else:
            headroom_sector = float("inf")

        # 6. Buyer concentration limit
        buyer_limit = provider.get("buyer_limit")
        if buyer_limit is not None and buyer_id:
            buyer_cap = buyer_limit * total_portfolio
            current_buyer_exp = (
                provider.get("current_exposure", {}).get("by_buyer", {}).get(buyer_id, 0.0)
            )
            headroom_buyer = max(0.0, buyer_cap - current_buyer_exp)
            if headroom_buyer <= 0:
                eligibility_list.append({
                    "provider_id": pid,
                    "eligible": False,
                    "max_fundable_lakh": 0.00,
                    "exclusion_reason": (
                        f"{pname} has reached its concentration limit for buyer "
                        f"{buyer_id} (headroom: ₹{headroom_buyer:.2f} lakh)."
                    ),
                    "binding_constraint": "buyer_limit",
                })
                continue
        else:
            headroom_buyer = float("inf")

        # 7. Target return: can the economics clear provider's required target return?
        # Max feasible return is benchmarked against maximum commercial rate minus cost of funds & expected loss
        max_market_rate = 0.36
        expected_loss_rate = pd * (1.0 - RECOVERY_RATE)
        cost_of_funds = provider.get("cost_of_funds", 0.0)
        max_feasible_return = max_market_rate - cost_of_funds - expected_loss_rate
        target_return = provider.get("target_return", 0.0)

        if max_feasible_return < target_return:
            eligibility_list.append({
                "provider_id": pid,
                "eligible": False,
                "max_fundable_lakh": 0.00,
                "exclusion_reason": (
                    f"Projected return ({max_feasible_return:.2%}) cannot meet {_possessive(pname)} "
                    f"required target return of {target_return:.2%}."
                ),
                "binding_constraint": "target_return",
            })
            continue

        # Provider is eligible! Compute tightest max_fundable_lakh across all limits
        max_fundable = round(
            min(
                available_liquidity,
                max_ticket,
                headroom_sector,
                headroom_buyer,
            ),
            2,
        )

        eligibility_list.append({
            "provider_id": pid,
            "eligible": True,
            "max_fundable_lakh": max_fundable,
            "exclusion_reason": None,
            "binding_constraint": None,
        })

    return eligibility_list
