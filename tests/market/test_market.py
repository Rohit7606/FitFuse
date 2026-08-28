"""Tests for the market simulator — Person B's test suite.

Test list from PERSON_B.md §7:
    test_agents_differentiate   — four demo providers produce four offers differing on more than rate
    test_never_below_cost       — no agent bids below cost_of_funds
    test_shading_increases      — higher uncertainty → higher bid rate
    test_capacity_respected     — no allocation exceeds max_fundable, liquidity, or limits
    test_clearing_terminates    — deferred acceptance converges under MAX_ROUNDS
    test_clearing_stable        — no supplier/provider pair would both prefer to defect
    test_syndication_sums       — allocations sum exactly to total_advance_lakh
    test_demo_match             — clearing on INV001 reproduces expected_match
    test_illegal_transition     — settled → funded raises IllegalTransitionError
    test_learning_delta         — settling INV001 late reproduces expected_after_learning
    test_no_market_mutation     — market dict unchanged after clear and settle
    test_determinism            — two identical clear calls → byte-identical results

Owner: Person B
"""

import json
import math
import os

import pytest

from engine.config import CAPITAL_CHARGE_RATE, RECOVERY_RATE, SHADE_K

_MARKET_PATH = os.path.join(os.path.dirname(__file__), "..", "..",
                            "data", "mock", "market.json")


def _required_rate(provider, pd, pd_upper, uncertainty, competitors):
    """The bidding formula from PERSON_B.md §3.1, with no agent code needed.

    Kept here rather than in market/agents.py so the arithmetic can be checked
    before the agents exist — this is what proves the demo rates are reachable.
    """
    expected_loss = pd * (1 - RECOVERY_RATE)
    capital_charge = CAPITAL_CHARGE_RATE * pd_upper
    shade = SHADE_K * uncertainty * math.log(1 + competitors)
    base = (provider["cost_of_funds"] + expected_loss + capital_charge
            + provider["target_margin"] + shade)
    return max(base, provider["cost_of_funds"])


@pytest.fixture(scope="module")
def providers():
    with open(_MARKET_PATH, encoding="utf-8") as f:
        return {p["provider_id"]: p for p in json.load(f)["providers"]}


class TestBiddingIsReachable:
    """The DEMO_SCENARIO.md §4 rates must be achievable by honest bidding.

    Before schema 1.1 they were not: target_margin had no field in the contract,
    and SHADE_K=8.0 made the winner's-curse shade 776 bp — larger than the whole
    bid — so every provider would have needed a negative cost of funds.
    """

    # DEMO_SCENARIO.md §5 assessment of INV001
    PD, PD_UPPER, UNCERTAINTY, RIVALS = 0.0210, 0.0280, 0.0070, 3

    # provider_id -> the rate DEMO_SCENARIO.md §4 requires it to bid
    DEMO_RATES = {"PRV001": 0.0900, "PRV002": 0.0820,
                  "PRV003": 0.0860, "PRV004": 0.0940}

    def test_target_margin_present(self, providers):
        for pid, p in sorted(providers.items()):
            assert "target_margin" in p, f"{pid} has no target_margin (schema 1.1)"

    def test_shade_is_plausible(self):
        """A winner's-curse premium is tens of basis points, not hundreds."""
        shade = SHADE_K * self.UNCERTAINTY * math.log(1 + self.RIVALS)
        assert shade < 0.0100, f"shade of {shade * 100:.2f} pp dwarfs the bid"

    @pytest.mark.parametrize("provider_id", sorted(DEMO_RATES))
    def test_demo_rate_reachable(self, providers, provider_id):
        rate = _required_rate(providers[provider_id], self.PD, self.PD_UPPER,
                              self.UNCERTAINTY, self.RIVALS)
        expected = self.DEMO_RATES[provider_id]
        assert round(rate, 4) == expected, (
            f"{provider_id} prices at {rate:.4f}, demo requires {expected:.4f}"
        )

    def test_never_below_cost_of_funds(self, providers):
        """Hard invariant — an agent bidding under its own funding cost is a bug."""
        for pid, p in sorted(providers.items()):
            rate = _required_rate(p, self.PD, self.PD_UPPER, self.UNCERTAINTY,
                                  self.RIVALS)
            assert rate >= p["cost_of_funds"], f"{pid} bids below cost of funds"

    def test_arcline_is_lowest_rate(self, providers):
        """The demo's trap: Arcline must still post the cheapest headline rate."""
        rates = {pid: _required_rate(providers[pid], self.PD, self.PD_UPPER,
                                     self.UNCERTAINTY, self.RIVALS)
                 for pid in self.DEMO_RATES}
        assert min(rates, key=rates.get) == "PRV002"


class TestAgents:
    """Provider agent tests."""

    @pytest.mark.skip(reason="Person B: implement after agents")
    def test_agents_differentiate(self):
        pass

    @pytest.mark.skip(reason="Person B: implement after agents")
    def test_never_below_cost(self):
        pass

    @pytest.mark.skip(reason="Person B: implement after agents")
    def test_shading_increases(self):
        pass


class TestClearing:
    """Clearing engine tests."""

    @pytest.mark.skip(reason="Person B: implement after clearing")
    def test_capacity_respected(self):
        pass

    @pytest.mark.skip(reason="Person B: implement after clearing")
    def test_clearing_terminates(self):
        pass

    @pytest.mark.skip(reason="Person B: implement after clearing")
    def test_clearing_stable(self):
        pass

    @pytest.mark.skip(reason="Person B: implement after clearing")
    def test_syndication_sums(self):
        pass

    @pytest.mark.skip(reason="Person B: implement after clearing")
    def test_demo_match(self):
        pass


class TestSettlement:
    """Settlement state machine tests."""

    @pytest.mark.skip(reason="Person B: implement after settlement")
    def test_illegal_transition(self):
        pass


class TestLearning:
    """Learning loop tests."""

    @pytest.mark.skip(reason="Person B: implement after learning")
    def test_learning_delta(self):
        pass


class TestPurity:
    """No side effects."""

    @pytest.mark.skip(reason="Person B: implement after clear/settle")
    def test_no_market_mutation(self):
        pass

    @pytest.mark.skip(reason="Person B: implement after clear")
    def test_determinism(self):
        pass
