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

import copy
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


def _assessment(providers, eligible_ids, max_fundable=None):
    """A minimal Assessment — engine/assess.py is still a stub (AGENTS.md §3.3)."""
    max_fundable = max_fundable or {}
    return {
        "invoice_id": "INV001",
        "risk": {"pd": 0.0210, "pd_lower": 0.0140, "pd_upper": 0.0280,
                 "uncertainty": 0.0070},
        "eligibility": [
            {"provider_id": pid,
             "eligible": pid in eligible_ids,
             "max_fundable_lakh": max_fundable.get(pid, 999.0)}
            for pid in sorted(providers)
        ],
    }


@pytest.fixture(scope="module")
def invoice():
    with open(_MARKET_PATH, encoding="utf-8") as f:
        return [i for i in json.load(f)["invoices"] if i["invoice_id"] == "INV001"][0]


@pytest.fixture(scope="module")
def demo_offers(providers, invoice):
    from market.agents import generate_offers
    demo = ["PRV001", "PRV002", "PRV003", "PRV004"]
    assessment = _assessment(providers, demo, max_fundable={"PRV003": 6.00})
    return {o["provider_id"]: o
            for o in generate_offers([providers[p] for p in demo], invoice, assessment)}


class TestAgents:
    """Provider agent tests."""

    # DEMO_SCENARIO.md §4 — rate, advance, days_to_settle, fee, structure
    DEMO_TERMS = {
        "PRV001": (0.0900, 0.80, 3, 0.0050, "bullet"),
        "PRV002": (0.0820, 0.70, 2, 0.0080, "bullet"),
        "PRV003": (0.0860, 0.90, 0, 0.0040, "bullet"),
        "PRV004": (0.0940, 0.75, 1, 0.0030, "instalment"),
    }

    @pytest.mark.parametrize("provider_id", sorted(DEMO_TERMS))
    def test_demo_offer_terms(self, demo_offers, provider_id):
        """The acceptance test for this module — PERSON_B.md §3.1."""
        rate, advance, days, fee, structure = self.DEMO_TERMS[provider_id]
        o = demo_offers[provider_id]
        assert o["rate_annual"] == rate
        assert o["advance_rate"] == advance
        assert o["days_to_settle"] == days
        assert o["fee_percent"] == fee
        assert o["repayment_structure"] == structure

    def test_agents_differentiate(self, demo_offers):
        """Four offers differing on more than rate — the whole thesis."""
        for field in ("rate_annual", "advance_rate", "days_to_settle", "fee_percent"):
            values = {o[field] for o in demo_offers.values()}
            assert len(values) == 4, f"all four offers must differ on {field}"
        assert len({o["repayment_structure"] for o in demo_offers.values()}) > 1

    def test_never_below_cost(self, providers, invoice):
        """A hard invariant, at any uncertainty — PERSON_B.md §3.1.

        Note this sweep never actually fires the floor: every term added to
        cost_of_funds is positive, so the sum always clears it. See
        test_floor_binds_on_negative_margin for the case that does.
        """
        from market.agents import generate_offer
        elig = {"eligible": True, "max_fundable_lakh": 99.0}
        for pid, p in sorted(providers.items()):
            for uncertainty in (0.0, 0.007, 0.05, 0.4):
                a = _assessment(providers, [pid])
                a["risk"]["uncertainty"] = uncertainty
                offer = generate_offer(p, invoice, a, elig)
                assert offer["rate_annual"] >= p["cost_of_funds"], pid

    def test_floor_binds_on_negative_margin(self, providers, invoice):
        """Exercise the max(required, cost_of_funds) branch itself.

        Raised by Person A in review: with every additive term positive, the
        floor is unreachable and the guard was effectively untested. A negative
        target_margin drives the unfloored rate below funding cost, which is
        the only way to prove the clamp works rather than assuming it.
        """
        from market.agents import generate_offer
        elig = {"eligible": True, "max_fundable_lakh": 99.0}
        for pid, p in sorted(providers.items()):
            underwater = {**p, "target_margin": -0.50}
            a = _assessment(providers, [pid])
            offer = generate_offer(underwater, invoice, a, elig)
            assert offer["rate_annual"] == round(p["cost_of_funds"], 4), (
                f"{pid} should clamp to its cost of funds, got {offer['rate_annual']}"
            )

    def test_rate_responds_to_risk(self, providers, invoice):
        """Independent of the demo calibration: pricing must track its inputs.

        The demo-rate tests are self-consistent by construction — target_margin
        was calibrated so each provider lands on its DEMO_SCENARIO.md §4 rate,
        so asserting that rate proves arithmetic, not economics. These checks
        vary one input at a time and assert the direction of the response,
        which holds whatever the constants are tuned to.
        """
        from market.agents import generate_offer
        p = providers["PRV003"]
        elig = {"eligible": True, "max_fundable_lakh": 99.0}

        def rate(**risk):
            a = _assessment(providers, ["PRV003"])
            a["risk"].update(risk)
            return generate_offer(p, invoice, a, elig)["rate_annual"]

        base = rate()
        assert rate(pd=0.0500) > base, "higher default probability must cost more"
        assert rate(pd_upper=0.0600) > base, "a wider band must cost more"
        assert rate(pd=0.0050, pd_upper=0.0100) < base, "safer must cost less"

        # And a dearer funder must bid higher, all else equal.
        dearer = {**p, "cost_of_funds": p["cost_of_funds"] + 0.02}
        a = _assessment(providers, ["PRV003"])
        assert generate_offer(dearer, invoice, a, elig)["rate_annual"] > base

    def test_margins_are_economically_ordered(self, providers):
        """A sanity check the calibration cannot fake.

        Whatever the target_margin values are tuned to, funding costs must stay
        in a plausible order — a bank funds itself more cheaply than an NBFC.
        If a future retune inverts that, the market stops being defensible even
        if every demo rate still reproduces.
        """
        bank = providers["PRV001"]["cost_of_funds"]
        nbfc = providers["PRV002"]["cost_of_funds"]
        assert bank < nbfc, "a bank should fund itself more cheaply than an NBFC"
        for pid, p in sorted(providers.items()):
            assert p["target_margin"] >= 0.0, f"{pid} has a negative margin"
            assert p["target_margin"] < 0.10, f"{pid} margin of {p['target_margin']} is implausible"

    def test_shading_increases(self, providers, invoice):
        """Higher uncertainty must raise the bid, all else equal."""
        from market.agents import generate_offer
        p = providers["PRV003"]
        elig = {"provider_id": "PRV003", "eligible": True, "max_fundable_lakh": 99.0}
        rates = []
        for uncertainty in (0.001, 0.007, 0.02):
            a = _assessment(providers, ["PRV003"])
            a["risk"]["uncertainty"] = uncertainty
            rates.append(generate_offer(p, invoice, a, elig)["rate_annual"])
        assert rates == sorted(rates) and rates[0] < rates[-1]

    def test_ineligible_provider_does_not_bid(self, providers, invoice):
        from market.agents import generate_offer
        a = _assessment(providers, [])
        assert generate_offer(providers["PRV005"], invoice, a,
                              {"eligible": False, "max_fundable_lakh": 0.0}) is None

    def test_capacity_limited_provider_still_bids(self, demo_offers):
        """Kestrel wants the whole deal; its sector limit says 6.00 lakh.

        Bidding for the part it can fund is what makes syndication possible.
        """
        kestrel = demo_offers["PRV003"]
        assert kestrel["advance_amount_lakh"] == 9.00
        assert kestrel["amount_committed_lakh"] == 6.00

    def test_respects_speed_capability(self, providers, invoice):
        """An agent may never promise to settle faster than it can."""
        from market.agents import generate_offer
        for pid, p in sorted(providers.items()):
            a = _assessment(providers, [pid])
            offer = generate_offer(p, invoice, a,
                                   {"eligible": True, "max_fundable_lakh": 99.0})
            assert offer["days_to_settle"] >= p["speed_capability_days"], pid

    def test_respects_preferred_structures(self, providers, invoice):
        from market.agents import generate_offer
        for pid, p in sorted(providers.items()):
            a = _assessment(providers, [pid])
            offer = generate_offer(p, invoice, a,
                                   {"eligible": True, "max_fundable_lakh": 99.0})
            assert offer["repayment_structure"] in p["preferred_structures"], pid

    def test_deterministic(self, providers, invoice):
        from market.agents import generate_offers
        demo = ["PRV001", "PRV002", "PRV003", "PRV004"]
        a = _assessment(providers, demo, max_fundable={"PRV003": 6.00})
        args = ([providers[p] for p in demo], invoice, a)
        assert json.dumps(generate_offers(*args)) == json.dumps(generate_offers(*args))

    def test_arcline_posts_lowest_rate(self, demo_offers):
        """The demo's trap must survive any tuning."""
        cheapest = min(demo_offers.values(), key=lambda o: o["rate_annual"])
        assert cheapest["provider_id"] == "PRV002"



def _scored(offers, fit_scores):
    """Attach a fit_score by hand, for tests that need a specific ordering."""
    out = []
    for o in offers:
        scored = dict(o)
        scored["fit_score"] = fit_scores[o["offer_id"]]
        scored["feasible"] = True
        out.append(scored)
    return out


def _market_json():
    path = os.path.join(os.path.dirname(__file__), "..", "..",
                        "data", "mock", "market.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def demo_clearing():
    """Clear INV001 through the REAL pipeline — assess, bid, score, clear.

    This used to hand-feed fit scores copied from DEMO_SCENARIO.md §4. Those
    numbers were written before engine/scoring.py existed and are not what it
    produces, so the test passed while describing a market that never runs.
    Now that the engine is wired up (Phase 2), there is no reason to fake it.
    """
    import json
    import os

    from engine.assess import assess, score_offers
    from market.clearing import run_clearing
    from market.simulate import generate_offers, resolve_preferences

    path = os.path.join(os.path.dirname(__file__), "..", "..",
                        "data", "mock", "market.json")
    with open(path, encoding="utf-8") as f:
        market = json.load(f)

    invoice = next(i for i in market["invoices"] if i["invoice_id"] == "INV001")
    assessment = assess("INV001", market)
    raw = generate_offers("INV001", market, assessment)
    scored = score_offers(raw, assessment, resolve_preferences("INV001", market))

    return run_clearing(
        invoices=[invoice],
        offers_by_invoice={"INV001": scored["offers"]},
        providers=market["providers"],
        eligibility_by_invoice={
            "INV001": {e["provider_id"]: e for e in assessment["eligibility"]}},
        risk_by_invoice={"INV001": assessment["risk"]},
        exposure_by_invoice={"INV001": {"buyer_id": invoice["buyer_id"],
                                        "sector": "auto_components"}},
    )


class TestSyndication:
    """Demo step 7 — Kestrel caps at its sector limit and the deal is split."""

    def test_kestrel_capped_at_sector_limit(self, demo_clearing):
        """The syndication trigger: Kestrel wants 9.00, its book allows 6.00."""
        m = demo_clearing["matches"][0]
        kestrel = next(a for a in m["allocations"] if a["provider_id"] == "PRV003")
        assert kestrel["amount_lakh"] == 6.00

    def test_deal_is_split_to_the_full_advance(self, demo_clearing):
        m = demo_clearing["matches"][0]
        assert m["invoice_id"] == "INV001"
        assert m["syndicated"] is True
        assert m["total_advance_lakh"] == 9.00
        assert len(m["allocations"]) == 2

    @pytest.mark.xfail(
        strict=True,
        reason="Fixture drift, needs Person A and Person C. expected_match names "
               "PRV001 as the syndication partner, which was true under the "
               "hand-written fit scores. With the real scorer OFR004 ranks second, "
               "so PRV004 fills the remainder. The fixture now contradicts its own "
               "expected_ranking; one of the two has to move.",
    )
    def test_matches_committed_fixture(self, demo_clearing):
        import json
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "..",
                            "data", "fixtures", "demo_scenario.json")
        with open(path, encoding="utf-8") as f:
            expected = json.load(f)["expected_match"]
        m = demo_clearing["matches"][0]
        assert [(a["provider_id"], a["amount_lakh"]) for a in m["allocations"]] == [
            (a["provider_id"], a["amount_lakh"]) for a in expected["allocations"]]

    def test_blended_rate_sits_between_the_slices(self, demo_clearing):
        """A syndicate's blended rate is a weighted average, so it must lie
        between the cheapest and dearest slice — never outside them."""
        from engine.assess import assess, score_offers
        from market.simulate import generate_offers, resolve_preferences

        market = _market_json()
        assessment = assess("INV001", market)
        scored = score_offers(
            generate_offers("INV001", market, assessment),
            assessment,
            resolve_preferences("INV001", market),
        )
        rates = {o["offer_id"]: o["rate_annual"] for o in scored["offers"]}

        m = demo_clearing["matches"][0]
        used = [rates[a["offer_id"]] for a in m["allocations"]]
        assert min(used) <= m["blended_rate_annual"] <= max(used)

        expected = sum(a["amount_lakh"] * rates[a["offer_id"]]
                       for a in m["allocations"]) / m["total_advance_lakh"]
        assert m["blended_rate_annual"] == round(expected, 4)

    def test_allocations_sum_exactly(self, demo_clearing):
        """schema.json requires this, and float drift bites here."""
        for m in demo_clearing["matches"]:
            assert round(sum(a["amount_lakh"] for a in m["allocations"]), 2) ==                    m["total_advance_lakh"]

    def test_starts_matched_not_funded(self, demo_clearing):
        """Selecting an offer is not financing — SCHEMA.md §4.6."""
        assert demo_clearing["matches"][0]["state"] == "matched"

    def test_capacity_respected(self, demo_clearing):
        """No allocation may exceed the provider's max_fundable_lakh."""
        caps = {"PRV003": 6.00}
        for m in demo_clearing["matches"]:
            for a in m["allocations"]:
                assert a["amount_lakh"] <= caps.get(a["provider_id"], 999.0) + 1e-9

    def test_clearing_terminates_and_is_stable(self, demo_clearing):
        s = demo_clearing["summary"]
        assert s["stable"] is True and 0 < s["iterations"] <= 50
        assert s["matched_count"] == 1 and s["syndicated_count"] == 1

    def test_reason_names_the_capped_provider_and_number(self, demo_clearing):
        text = demo_clearing["matches"][0]["reason_text"]
        assert "Kestrel" in text and "6.00" in text

    def test_utilisation_reported(self, demo_clearing):
        util = {u["provider_id"]: u for u in demo_clearing["provider_utilisation"]}
        assert util["PRV003"]["committed_lakh"] == 6.00
        assert round(sum(u["committed_lakh"] for u in
                         demo_clearing["provider_utilisation"]), 2) == 9.00

    def test_determinism(self, demo_clearing):
        """Two identical clears must be byte-identical — AGENTS.md §3.1."""
        from market.simulate import clear
        market = _market_json()
        assert json.dumps(clear(["INV001"], market)) ==                json.dumps(clear(["INV001"], market))

    def test_shortfall_is_unmatched_with_reason(self, providers, invoice, demo_offers):
        """When nobody has capacity, say so rather than part-funding silently."""
        from market.clearing import run_clearing
        demo = ["PRV001", "PRV002", "PRV003", "PRV004"]
        fit = {"OFR001": 0.71, "OFR002": 0.64, "OFR003": 0.89, "OFR004": 0.68}
        result = run_clearing(
            invoices=[invoice],
            offers_by_invoice={"INV001": _scored(list(demo_offers.values()), fit)},
            providers=[providers[p] for p in demo],
            eligibility_by_invoice={"INV001": {
                p: {"provider_id": p, "eligible": True, "max_fundable_lakh": 0.50}
                for p in demo}},
            risk_by_invoice={"INV001": {"pd": 0.0210, "pd_upper": 0.0280}},
            exposure_by_invoice={"INV001": {"buyer_id": "BUY001",
                                            "sector": "auto_components"}},
        )
        assert result["matches"] == []
        assert result["unmatched"][0]["invoice_id"] == "INV001"
        assert "lakh" in result["unmatched"][0]["reason"]


class TestConcentrationLimits:
    """A limit that only holds for one invoice is not a limit (AGENTS.md §4.5)."""

    # All four are on BUY001, so they compete for the same buyer headroom.
    IDS = ["INV001", "INV014", "INV031", "INV033"]

    def test_buyer_limit_binds_across_invoices(self):
        """Kestrel must stop at its BUY001 headroom, not at its overall capacity.

        Built deliberately, because the obvious version proves nothing. The
        shared per-provider budget is the largest per-invoice max_fundable_lakh
        across the batch, so if every invoice were on one buyer that budget
        already equals the buyer cap and deleting the buyer check changes no
        number. It only bites when the batch spans several buyers: the budget
        is then set by some other buyer's invoice, and nothing stops the
        provider spending it all against this one.

        Sector limits are widened so they cannot be what binds, and Kestrel is
        given ₹45 lakh of prior BUY001 exposure against a ₹75 lakh cap. It wants
        ₹48.84 lakh. It may have ₹30.00.
        """
        from market.simulate import clear

        market = copy.deepcopy(_market_json())
        for provider in market["providers"]:
            provider["sector_limits"] = {
                sector: 0.99 for sector in (provider.get("sector_limits") or {})}
            provider["current_exposure"]["by_sector"] = {}
            if provider["provider_id"] == "PRV003":
                provider["current_exposure"]["by_buyer"]["BUY001"] = 45.0

        invoices = {i["invoice_id"]: i for i in market["invoices"]}
        on_buyer = [i for i, v in invoices.items() if v["buyer_id"] == "BUY001"]
        elsewhere = [i for i, v in invoices.items() if v["buyer_id"] != "BUY001"][:6]

        funded = {}
        for match in clear(sorted(on_buyer + elsewhere), market)["matches"]:
            if invoices[match["invoice_id"]]["buyer_id"] != "BUY001":
                continue
            for alloc in match["allocations"]:
                funded[alloc["provider_id"]] = (
                    funded.get(alloc["provider_id"], 0.0) + alloc["amount_lakh"])

        for provider in market["providers"]:
            pid = provider["provider_id"]
            if pid not in funded:
                continue
            cap = provider["buyer_limit"] * provider["total_portfolio_lakh"]
            held = provider["current_exposure"]["by_buyer"].get("BUY001", 0.0)
            assert held + funded[pid] <= cap + 1e-6, (
                f"{pid} holds {held + funded[pid]:.2f} lakh against BUY001, "
                f"cap {cap:.2f}")

        assert funded.get("PRV003") == pytest.approx(30.0, abs=0.01), (
            "the limit did not bind, so this test proves nothing")

    def test_sector_limit_binds_across_invoices(self):
        from market.simulate import clear

        market = _market_json()
        buyers = {b["buyer_id"]: b for b in market["buyers"]}
        invoices = {i["invoice_id"]: i for i in market["invoices"]}
        providers = {p["provider_id"]: p for p in market["providers"]}

        funded = {}
        for match in clear(self.IDS, market)["matches"]:
            sector = buyers[invoices[match["invoice_id"]]["buyer_id"]]["sector"]
            for alloc in match["allocations"]:
                key = (alloc["provider_id"], sector)
                funded[key] = funded.get(key, 0.0) + alloc["amount_lakh"]

        for (provider_id, sector), total in funded.items():
            provider = providers[provider_id]
            limit = (provider.get("sector_limits") or {}).get(sector)
            if limit is None:
                continue
            held = provider.get("current_exposure", {}).get("by_sector", {}).get(sector, 0.0)
            cap = limit * provider["total_portfolio_lakh"]
            assert held + total <= cap + 1e-6, f"{provider_id}/{sector}"


class TestPurity:
    """No side effects — clear() must not touch the caller's data."""

    def test_no_market_mutation(self):
        """The API is stateless; a mutated input would leak between requests."""
        import copy

        from market.simulate import clear
        market = _market_json()
        before = copy.deepcopy(market)
        clear(["INV001", "INV014"], market)
        assert market == before


class TestSettlement:
    """The state machine — `matched` is not `funded` (SCHEMA.md §4.6)."""

    def _match(self, state="matched"):
        return {
            "match_id": "MCH001", "invoice_id": "INV001",
            "allocations": [{"provider_id": "PRV003", "amount_lakh": 6.00,
                             "offer_id": "OFR003"}],
            "syndicated": False, "total_advance_lakh": 6.00,
            "blended_rate_annual": 0.086, "blended_cost_lakh": 0.08,
            "supplier_fit_score": 0.9, "state": state, "days_to_settle": 0,
            "reason_text": "Kestrel Credit Fund funds the full ₹6.00 lakh advance.",
        }

    def test_illegal_transition(self):
        """settled → funded raises — nothing transitions out of a terminal state."""
        from market.settlement import IllegalTransitionError, advance
        with pytest.raises(IllegalTransitionError) as exc:
            advance(self._match("settled"), {"outcome": "funded"}, _market_json())
        assert exc.value.current_state == "settled"
        assert exc.value.target_state == "funded"

    def test_cannot_settle_before_funding(self):
        """The refusal names the fix, not just the states (PERSON_B.md §5)."""
        from market.settlement import IllegalTransitionError, advance
        with pytest.raises(IllegalTransitionError, match="fund it first"):
            advance(self._match("matched"), {"outcome": "late"}, _market_json())

    @pytest.mark.parametrize("state", ["settled", "defaulted", "cancelled"])
    def test_terminal_states_are_terminal(self, state):
        from market.settlement import LEGAL_TRANSITIONS
        assert LEGAL_TRANSITIONS[state] == set()

    def test_legal_path_walks_all_the_way(self):
        from market.settlement import advance
        market = _market_json()
        match = self._match("matched")
        for target in ("funded", "late", "settled"):
            match = advance(match, {"outcome": target, "days_late": 5}, market)
            assert match["state"] == target
        assert match["days_late"] == 5

    def test_funding_checks_liquidity_again(self):
        """A provider drained after clearing cannot fund — cancel it, don't settle it.

        This is where the state machine earns its keep: without the re-check, a
        scenario that empties Kestrel between clearing and disbursement would
        still report ₹6 lakh as paid out.
        """
        from market.settlement import IllegalTransitionError, advance
        market = _market_json()
        for provider in market["providers"]:
            if provider["provider_id"] == "PRV003":
                provider["available_liquidity_lakh"] = 1.00
        with pytest.raises(IllegalTransitionError, match="short of"):
            advance(self._match("matched"), {"outcome": "funded"}, market)
        # ...and cancelling it is always available.
        assert advance(self._match("matched"), {"outcome": "cancelled"},
                       market)["state"] == "cancelled"

    def test_advance_does_not_mutate(self):
        from market.settlement import advance
        match = self._match("matched")
        before = copy.deepcopy(match)
        advance(match, {"outcome": "funded"}, _market_json())
        assert match == before

    def test_clearing_narration_survives_settlement(self):
        """Demo steps 7 and 8 are one screen; the syndication reason must persist."""
        from market.settlement import advance
        match = self._match("matched")
        funded = advance(match, {"outcome": "funded"}, _market_json())
        assert funded["reason_text"] == match["reason_text"]
        assert "disbursed" in funded["state_reason_text"]


class TestMatchIdIsAnAddress:
    """/api/settle addresses a match by id, and the API holds no state."""

    def test_match_id_follows_the_invoice(self):
        from market.clearing import match_id_for
        assert match_id_for("INV001") == "MCH001"
        assert match_id_for("INV014") == "MCH014"

    def test_id_does_not_depend_on_the_batch(self):
        """MCH014 means INV014 whether or not INV001 was in the same request.

        Numbering by position made MCH001 mean "whatever sorted first in this
        request", so settling MCH001 could resolve to a different invoice than
        the one the caller matched.
        """
        from market.simulate import clear
        market = _market_json()
        alone = clear(["INV014"], market)["matches"]
        batched = [m for m in clear(["INV001", "INV014"], market)["matches"]
                   if m["invoice_id"] == "INV014"]
        assert alone and batched
        assert alone[0]["match_id"] == batched[0]["match_id"] == "MCH014"


def _fixture():
    path = os.path.join(os.path.dirname(__file__), "..", "..",
                        "data", "fixtures", "demo_scenario.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def demo_settlement():
    """Settle INV001 five days late, through the real pipeline. Demo step 8."""
    from market.simulate import settle
    fixture = _fixture()
    event = fixture["settlement_event"]
    return settle("MCH001", event["outcome"], event["days_late"], _market_json())


class TestLearning:
    """Demo step 8 — the outcome feeds back into the market."""

    def test_learning_delta(self, demo_settlement):
        """Settling INV001 late reproduces the fixture's expected_after_learning."""
        expected = _fixture()["expected_after_learning"]
        update = demo_settlement["delta"]["buyer_updates"][0]
        assert update["buyer_id"] == "BUY001"
        assert update["avg_payment_delay_after"] == expected["BUY001_avg_delay"]

    def test_delay_moves_by_the_learning_rate(self, demo_settlement):
        """4 days moving 30% toward an observed 5 is 4.3 — reported as 5.

        Rounded up, not to nearest: engine/risk.py reads this field as an
        integer, and 4.3 reported as 4 would make a late payment a no-op.
        """
        update = demo_settlement["delta"]["buyer_updates"][0]
        assert update["avg_payment_delay_before"] == 4
        assert update["avg_payment_delay_after"] == 5
        assert update["payment_delay_trend_after"] == 1.0

    def test_secondary_invoice_repriced(self, demo_settlement):
        """The fixture's secondary invoice is among those repriced."""
        secondary = _fixture()["secondary_invoice_id"]
        repriced = {r["invoice_id"]: r
                    for r in demo_settlement["delta"]["repriced_invoices"]}
        assert secondary in repriced
        assert repriced[secondary]["pd_after"] > repriced[secondary]["pd_before"]

    @pytest.mark.xfail(strict=True, reason=(
        "DEMO_SCENARIO.md §5 says INV014 crosses prime to standard on a 5-day "
        "delay. With the committed risk calibration it does not: INV014's "
        "pd_upper moves 0.0221 to 0.0244 against a 0.030 prime threshold. The "
        "invoice that does cross is INV001 itself. The fixture's numbers "
        "(pd 0.0210 to 0.0265) are INV001's, copied onto INV014's row. Needs a "
        "deliberate fixture update with A and C named — DEMO_SCENARIO.md is "
        "shared (AGENTS.md 2.1)."))
    def test_secondary_invoice_crosses_a_band(self, demo_settlement):
        expected = _fixture()["expected_after_learning"]
        secondary = _fixture()["secondary_invoice_id"]
        repriced = {r["invoice_id"]: r
                    for r in demo_settlement["delta"]["repriced_invoices"]}
        assert repriced[secondary]["band_before"] == expected["INV014_band_before"]
        assert repriced[secondary]["band_after"] == expected["INV014_band_after"]

    def test_only_movers_are_reported(self, demo_settlement):
        """SCHEMA.md §4.7: repriced_invoices holds invoices whose pd moved."""
        repriced = demo_settlement["delta"]["repriced_invoices"]
        assert repriced, "a late payment must move something"
        assert all(r["pd_after"] != r["pd_before"] for r in repriced)
        # INV002 is on the same buyer but is a rejected duplicate, so it has no
        # pd to move and must not pad the list the judge reads.
        assert "INV002" not in {r["invoice_id"] for r in repriced}

    def test_only_this_buyer_is_touched(self, demo_settlement):
        """A late payment by one buyer must not reprice the rest of the market."""
        market = _market_json()
        buyers = {i["invoice_id"]: i["buyer_id"] for i in market["invoices"]}
        assert {buyers[r["invoice_id"]]
                for r in demo_settlement["delta"]["repriced_invoices"]} == {"BUY001"}

    def test_late_does_not_return_liquidity(self, demo_settlement):
        """PERSON_B.md §3.4: settled returns the capital, late returns nothing yet.

        DEMO_SCENARIO.md §5 and SCHEMA.md §4.7 both show capital coming back on
        a *late* outcome. That is the wrong way round — the buyer has not paid —
        so this follows PERSON_B.md §3.4 and the two shared docs need a fix.
        """
        for entry in demo_settlement["delta"]["liquidity_updates"]:
            assert entry["returned_lakh"] == 0.0
            assert entry["available_after_lakh"] == entry["available_before_lakh"]

    def test_settled_returns_liquidity(self):
        from market.simulate import settle
        result = settle("MCH001", "settled", 0, _market_json())
        updates = result["delta"]["liquidity_updates"]
        assert updates
        for entry in updates:
            assert entry["returned_lakh"] > 0

    def test_default_consumes_liquidity_and_costs_more(self):
        """A write-off must be visibly worse than a late payment, not just different."""
        from market.simulate import settle
        market = _market_json()
        late = settle("MCH001", "late", 5, market)["delta"]
        gone = settle("MCH001", "defaulted", 0, market)["delta"]
        assert all(e["returned_lakh"] == 0.0 for e in gone["liquidity_updates"])
        assert (gone["buyer_updates"][0]["avg_payment_delay_after"]
                > late["buyer_updates"][0]["avg_payment_delay_after"])
        assert (gone["provider_bid_adjustments"][0]["rate_adjustment"]
                > late["provider_bid_adjustments"][0]["rate_adjustment"])

    def test_bid_adjustment_is_a_real_repricing(self, demo_settlement):
        """The adjustment must be the change in the agent's own pricing function.

        Not a second, unexplained model bolted on for the demo — otherwise the
        number on screen is not the number the market would actually bid.
        """
        from engine.assess import assess
        from engine.config import DEFAULT_EXPECTED_COMPETITORS, SEGMENT_LEARNING_RATE
        from market.agents import bid_rate

        adjustment = demo_settlement["delta"]["provider_bid_adjustments"][0]
        provider = next(p for p in _market_json()["providers"]
                        if p["provider_id"] == adjustment["provider_id"])

        market = _market_json()
        after = copy.deepcopy(market)
        buyer = next(b for b in after["buyers"] if b["buyer_id"] == "BUY001")
        buyer["avg_payment_delay_days"] = 5
        buyer["payment_delay_trend"] = 1.0

        was = bid_rate(provider, assess("INV001", market)["risk"],
                       DEFAULT_EXPECTED_COMPETITORS)
        now = bid_rate(provider, assess("INV001", after)["risk"],
                       DEFAULT_EXPECTED_COMPETITORS)
        assert adjustment["rate_adjustment"] == pytest.approx(
            SEGMENT_LEARNING_RATE * (now - was), abs=1e-6)

    def test_the_loop_actually_closes(self):
        """Kestrel's next bid moving up must be true of the next bid, not a caption.

        The learned adjustment is carried in the returned market, so re-running
        the agents on it produces the higher rate. If it only lived in the delta
        the learning claim would be decorative.

        The buyer is put back exactly as it was before the comparison. Without
        that, the after-market prices higher anyway because its pd moved, and
        this test would pass with the adjustment deleted entirely — which is
        precisely what it exists to catch.
        """
        from engine.assess import assess
        from market.learning import apply_outcome
        from market.settlement import commit_liquidity
        from market.simulate import clear, generate_offers

        market = _market_json()
        match = clear(["INV001"], market)["matches"][0]
        funded = commit_liquidity(market, match)
        after, delta = apply_outcome({**match, "state": "late"},
                                     {"outcome": "late", "days_late": 5}, funded)
        assert delta["provider_bid_adjustments"]

        isolated = copy.deepcopy(after)
        original = next(b for b in market["buyers"] if b["buyer_id"] == "BUY001")
        for buyer in isolated["buyers"]:
            if buyer["buyer_id"] == "BUY001":
                buyer.update(copy.deepcopy(original))
        assert (assess("INV001", isolated)["risk"]
                == assess("INV001", market)["risk"]), "risk must be held constant"

        winner = match["allocations"][0]["provider_id"]
        before_rate = {o["provider_id"]: o["rate_annual"] for o in generate_offers(
            "INV001", market, assess("INV001", market))}
        after_rate = {o["provider_id"]: o["rate_annual"] for o in generate_offers(
            "INV001", isolated, assess("INV001", isolated))}
        assert after_rate[winner] > before_rate[winner]

    def test_summary_text_is_generated_from_the_numbers(self, demo_settlement):
        """Template-generated, and every number in it is one the delta reports."""
        delta = demo_settlement["delta"]
        summary = delta["summary_text"]
        assert "Vireon Motors India Ltd" in summary
        assert str(delta["trigger"]["days_late"]) in summary
        assert str(len(delta["repriced_invoices"])) in summary


class TestSettlementPurity:
    """The API is stateless — settling must not leave a trace."""

    def test_no_market_mutation(self):
        from market.simulate import settle
        market = _market_json()
        before = copy.deepcopy(market)
        settle("MCH001", "late", 5, market)
        assert market == before

    def test_determinism(self):
        from market.simulate import settle
        first = settle("MCH001", "late", 5, _market_json())
        second = settle("MCH001", "late", 5, _market_json())
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

    def test_before_and_after_line_up(self, demo_settlement):
        """Row for row, so the UI can diff them without matching on identity."""
        before = demo_settlement["before"]["affected_invoices"]
        after = demo_settlement["after"]["affected_invoices"]
        assert [r["invoice_id"] for r in before] == [r["invoice_id"] for r in after]
        assert before[0]["invoice_id"] == "INV001"

    def test_two_evaluations_not_one(self, demo_settlement):
        """SCHEMA.md §5.6: the before/after comparison is the product.

        Every affected invoice is assessed on both sides, and at least one must
        differ — an "after" that echoes "before" would pass a shape check while
        saying nothing.
        """
        before = demo_settlement["before"]["affected_invoices"]
        after = demo_settlement["after"]["affected_invoices"]
        assert any(b["pd"] != a["pd"] for b, a in zip(before, after, strict=True))
