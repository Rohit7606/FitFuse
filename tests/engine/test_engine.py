"""Tests for the valuation engine — Person A's test suite.

Test list from PERSON_A.md §5:
    test_determinism           — assess + score_offers give byte-identical JSON on same input
    test_schema_valid          — mockgen output validates; assess output validates
    test_demo_offers           — four demo offers produce exact total_cost_lakh and fit_score
    test_demo_ranking          — expected_ranking and expected_naive_ranking both reproduce
    test_preset_flip           — cheapest→OFR004 first; cash_fastest→OFR003 first
    test_hard_constraints      — offer below min_advance_rate is feasible:false, still returned
    test_duplicate_blocked     — INV002 rejected with duplicate_of: INV001
    test_irn_null_rejected     — null IRN rejects, no risk score
    test_uncertainty_widens    — adding unknown field increases pd_upper
    test_null_vs_zero          — prior_defaults:0 and null produce different pd
    test_eligibility_reasons   — every ineligible provider has exclusion_reason + binding_constraint
    test_max_fundable          — Kestrel's max_fundable_lakh is 6.00 on demo invoice
    test_zero_span             — offers identical on attribute all score 1.0
    test_scores_bounded        — no fit_score or pd outside [0, 1]
    test_no_input_mutation     — market dict unchanged after assess

Owner: Person A
"""

import pytest

# Placeholder tests — Person A implements these as the engine is built.

class TestDeterminism:
    """assess and score_offers run twice on the same input → byte-identical JSON."""

    def test_determinism(self):
        """Same input twice must give byte-identical JSON — AGENTS.md §3.1."""
        import json

        from engine.assess import assess
        market = _market()
        first = json.dumps(assess("INV001", market), sort_keys=True)
        second = json.dumps(assess("INV001", market), sort_keys=True)
        assert first == second


class TestSchemaValid:
    """mockgen output validates against MarketInput; assess output against Assessment."""

    def test_mockgen_validates(self):
        import os

        import jsonschema

        from engine.mockgen import generate_market, validate_market
        market = generate_market(42)
        schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "schema.json")
        # Validate should not raise any exceptions
        validate_market(market, schema_path)

        # The validator must actually reject bad input. schema.json is a
        # definitions-only document, so validating against its root would pass
        # anything at all — this guards against that regression.
        with pytest.raises(jsonschema.ValidationError):
            validate_market({"suppliers": "not-an-array"}, schema_path)

    def test_assess_validates(self):
        """assess() output validates against the Assessment definition."""
        import json
        import os

        import jsonschema

        from engine.assess import assess
        schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "schema.json")
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        for invoice_id in ("INV001", "INV002", "INV014"):
            jsonschema.validate(
                instance=assess(invoice_id, _market()),
                schema={**schema, "$ref": "#/definitions/Assessment"},
            )


def _market():
    import json
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "..",
                        "data", "mock", "market.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _demo_offers():
    return [
        {
            "offer_id": "OFR001", "invoice_id": "INV001", "provider_id": "PRV001", "rate_annual": 0.0900,
            "advance_rate": 0.80, "days_to_settle": 3, "fee_percent": 0.0050,
            "fee_flat_lakh": 0.0, "repayment_structure": "bullet", "tenor_days": 60,
            "amount_committed_lakh": 8.0, "advance_amount_lakh": 8.0,
        },
        {
            "offer_id": "OFR002", "invoice_id": "INV001", "provider_id": "PRV002", "rate_annual": 0.0820,
            "advance_rate": 0.70, "days_to_settle": 2, "fee_percent": 0.0080,
            "fee_flat_lakh": 0.0, "repayment_structure": "bullet", "tenor_days": 60,
            "amount_committed_lakh": 7.0, "advance_amount_lakh": 7.0,
        },
        {
            "offer_id": "OFR003", "invoice_id": "INV001", "provider_id": "PRV003", "rate_annual": 0.0860,
            "advance_rate": 0.90, "days_to_settle": 0, "fee_percent": 0.0040,
            "fee_flat_lakh": 0.0, "repayment_structure": "bullet", "tenor_days": 60,
            "amount_committed_lakh": 6.0, "advance_amount_lakh": 9.0,
        },
        {
            "offer_id": "OFR004", "invoice_id": "INV001", "provider_id": "PRV004", "rate_annual": 0.0940,
            "advance_rate": 0.75, "days_to_settle": 1, "fee_percent": 0.0030,
            "fee_flat_lakh": 0.0, "repayment_structure": "instalment", "tenor_days": 60,
            "amount_committed_lakh": 7.5, "advance_amount_lakh": 7.5,
        },
    ]


class TestDemoScenario:
    """The four demo offers produce exactly the stated values under min-max normalization."""

    def test_demo_offers(self):
        """All 4 demo offers produce exact all-in costs and fit scores under PERSON_A.md §3.4 normalization."""
        from engine.scoring import score_offers

        prefs = {
            "preset": "cash_fastest",
            "weights": {"cost": 0.15, "advance": 0.30, "speed": 0.35, "tenor": 0.10, "fees": 0.05, "structure": 0.05},
            "min_advance_rate": 0.70,
            "max_days_to_cash": 5,
            "preferred_structure": "bullet",
            "urgent": True,
        }
        res = score_offers(_demo_offers(), {"invoice_id": "INV001"}, prefs)
        offers_by_id = {o["offer_id"]: o for o in res["offers"]}

        # OFR003: ₹16,723 all-in, fit 0.8980. Exact, not a tolerant range —
        # a range here would silently accept a return to mid-calculation
        # rounding, which AGENTS.md §3.1 forbids and which quantises the
        # cost to the nearest ₹10.
        o3 = offers_by_id["OFR003"]
        assert round(o3["total_cost_lakh"] * 100000) == 16723
        assert round(o3["fit_score"], 2) == 0.90

        # OFR002: ₹17,436 all-in, fit 0.2611
        o2 = offers_by_id["OFR002"]
        assert round(o2["total_cost_lakh"] * 100000) == 17436
        assert round(o2["fit_score"], 2) == 0.26

        # OFR004: ₹14,589 all-in, fit 0.6222
        o4 = offers_by_id["OFR004"]
        assert round(o4["total_cost_lakh"] * 100000) == 14589
        assert round(o4["fit_score"], 2) == 0.62

        # OFR001: ₹16,836 all-in, fit 0.3263
        o1 = offers_by_id["OFR001"]
        assert round(o1["total_cost_lakh"] * 100000) == 16836
        assert round(o1["fit_score"], 2) == 0.33

    def test_demo_ranking(self):
        """Full ordered rankings (both fit auction and naive auction) match expected relative ordering."""
        from engine.scoring import score_offers

        prefs = {
            "preset": "cash_fastest",
            "weights": {"cost": 0.15, "advance": 0.30, "speed": 0.35, "tenor": 0.10, "fees": 0.05, "structure": 0.05},
            "min_advance_rate": 0.70,
            "max_days_to_cash": 5,
            "preferred_structure": "bullet",
            "urgent": True,
        }
        res = score_offers(_demo_offers(), {"invoice_id": "INV001"}, prefs)

        # Read the expectations from the committed fixture rather than
        # restating them here. DEMO_SCENARIO.md §8 makes the fixture the
        # authority, and a hardcoded copy can drift from it silently — which
        # is exactly what happened before this test was rewritten.
        import json
        import os
        fixture_path = os.path.join(os.path.dirname(__file__), "..", "..",
                                    "data", "fixtures", "demo_scenario.json")
        with open(fixture_path, encoding="utf-8") as f:
            fixture = json.load(f)

        assert res["ranking"] == fixture["expected_ranking"]
        assert res["naive_ranking"] == fixture["expected_naive_ranking"]

        # Summary flags
        assert res["summary"]["best_fit_offer_id"] == "OFR003"
        assert res["summary"]["lowest_rate_offer_id"] == "OFR002"
        assert res["summary"]["fit_beats_rate"] is True

    def test_preset_flip(self):
        """Cheapest preset flips winner to OFR004; cash_fastest keeps OFR003."""
        from engine.scoring import score_offers

        # 1. Cheapest preset
        prefs_cheap = {
            "preset": "cheapest",
            "weights": {"cost": 0.55, "advance": 0.10, "speed": 0.05, "tenor": 0.10, "fees": 0.15, "structure": 0.05},
            "min_advance_rate": 0.70,
            "max_days_to_cash": 5,
            "preferred_structure": "bullet",
            "urgent": False,
        }
        res_cheap = score_offers(_demo_offers(), {"invoice_id": "INV001"}, prefs_cheap)
        assert res_cheap["summary"]["best_fit_offer_id"] == "OFR004"
        assert res_cheap["ranking"][0] == "OFR004"

        # 2. Cash fastest preset
        prefs_fast = {
            "preset": "cash_fastest",
            "weights": {"cost": 0.15, "advance": 0.30, "speed": 0.35, "tenor": 0.10, "fees": 0.05, "structure": 0.05},
            "min_advance_rate": 0.70,
            "max_days_to_cash": 5,
            "preferred_structure": "bullet",
            "urgent": True,
        }
        res_fast = score_offers(_demo_offers(), {"invoice_id": "INV001"}, prefs_fast)
        assert res_fast["summary"]["best_fit_offer_id"] == "OFR003"
        assert res_fast["ranking"][0] == "OFR003"


class TestHardConstraints:
    """An offer below min_advance_rate is feasible:false and still returned."""

    def test_hard_constraints(self):
        """Hard constraints mark feasible=false and exclude from normalization."""
        from engine.scoring import score_offers

        offers = _demo_offers()
        # Set a hard constraint that OFR002 violates (advance_rate: 0.70 < 0.75)
        prefs = {
            "preset": "custom",
            "weights": {"cost": 0.15, "advance": 0.30, "speed": 0.35, "tenor": 0.10, "fees": 0.05, "structure": 0.05},
            "min_advance_rate": 0.75,
            "max_days_to_cash": 5,
            "preferred_structure": "bullet",
            "urgent": False,
        }
        res = score_offers(offers, {"invoice_id": "INV001"}, prefs)
        offers_by_id = {o["offer_id"]: o for o in res["offers"]}

        o2 = offers_by_id["OFR002"]
        assert o2["feasible"] is False
        assert o2["fit_score"] == 0.0
        assert o2["rejection_reason"] is not None
        assert "70%" in o2["rejection_reason"]
        assert "75%" in o2["rejection_reason"]

        # Infeasible offer ranks last
        assert res["ranking"][-1] == "OFR002"


class TestVerification:
    """Verification edge cases."""

    def test_duplicate_blocked(self):
        """INV002 is rejected with duplicate_of: INV001."""
        from engine.mockgen import generate_market
        from engine.verify import verify

        market = generate_market(42)
        v = verify("INV002", market)
        assert v["status"] == "rejected"
        assert v["duplicate_detected"] is True
        assert v["duplicate_of"] == "INV001"
        # No risk score should be computed — rejected invoices stop here.
        assert v["field_confidence"] == {}
        assert v["unknown_field_count"] == 0

    def test_irn_null_rejected(self):
        """A null IRN rejects the invoice; no risk score is produced."""
        import copy

        from engine.mockgen import generate_market
        from engine.verify import verify

        market = generate_market(42)
        # Patch INV001 to have a null IRN.
        market = copy.deepcopy(market)
        for inv in market["invoices"]:
            if inv["invoice_id"] == "INV001":
                inv["irn"] = None
                break
        v = verify("INV001", market)
        assert v["status"] == "rejected"
        assert v["irn_valid"] is False
        assert v["duplicate_detected"] is False
        assert "not registered" in v["reason_text"].lower()


class TestRisk:
    """Risk model edge cases."""

    def test_uncertainty_widens(self):
        """Adding an unknown field increases pd_upper."""
        import copy

        from engine.mockgen import generate_market
        from engine.risk import score_risk
        from engine.verify import verify

        market = generate_market(42)
        inv = next(i for i in market["invoices"] if i["invoice_id"] == "INV001")
        sup = next(s for s in market["suppliers"] if s["supplier_id"] == inv["supplier_id"])
        buy = next(b for b in market["buyers"] if b["buyer_id"] == inv["buyer_id"])

        # Baseline: INV001 has 1 unknown (delivery_confirmed)
        v_base = verify("INV001", market)
        r_base = score_risk(inv, sup, buy, v_base)

        # Widened: patch delivery_confirmed AND null out prior_defaults
        market2 = copy.deepcopy(market)
        for s in market2["suppliers"]:
            if s["supplier_id"] == "SUP001":
                s["prior_defaults"] = None
                break
        v_wide = verify("INV001", market2)
        assert v_wide["unknown_field_count"] > v_base["unknown_field_count"]

        inv2 = next(i for i in market2["invoices"] if i["invoice_id"] == "INV001")
        sup2 = next(s for s in market2["suppliers"] if s["supplier_id"] == inv2["supplier_id"])
        buy2 = next(b for b in market2["buyers"] if b["buyer_id"] == inv2["buyer_id"])
        r_wide = score_risk(inv2, sup2, buy2, v_wide)
        assert r_wide["pd_upper"] > r_base["pd_upper"]
        assert r_wide["uncertainty"] > r_base["uncertainty"]

    def test_null_vs_zero(self):
        """prior_defaults=0 and null produce different pd."""
        import copy

        from engine.mockgen import generate_market
        from engine.risk import score_risk
        from engine.verify import verify

        market = generate_market(42)
        inv = next(i for i in market["invoices"] if i["invoice_id"] == "INV001")
        sup_zero = next(s for s in market["suppliers"] if s["supplier_id"] == "SUP001")
        buy = next(b for b in market["buyers"] if b["buyer_id"] == inv["buyer_id"])
        assert sup_zero["prior_defaults"] == 0  # explicitly zero

        v = verify("INV001", market)
        r_zero = score_risk(inv, sup_zero, buy, v)

        # Patch to null — absence is not a clean record
        market2 = copy.deepcopy(market)
        for s in market2["suppliers"]:
            if s["supplier_id"] == "SUP001":
                s["prior_defaults"] = None
                break
        v2 = verify("INV001", market2)
        sup_null = next(s for s in market2["suppliers"] if s["supplier_id"] == "SUP001")
        r_null = score_risk(inv, sup_null, buy, v2)

        # null should produce a higher pd than explicit zero
        assert r_null["pd"] > r_zero["pd"]

    def test_scores_bounded(self):
        """No pd or fit_score outside [0, 1] anywhere in the market.

        Swept across every invoice rather than the demo one, because a bound
        violation would most likely show up on an edge-case supplier or buyer
        that the demo path never touches.
        """
        from engine.assess import assess, score_offers
        market = _market()
        prefs = {
            "preset": "cash_fastest",
            "weights": {"cost": 0.15, "advance": 0.30, "speed": 0.35,
                        "tenor": 0.10, "fees": 0.05, "structure": 0.05},
            "min_advance_rate": 0.70, "max_days_to_cash": 5,
            "preferred_structure": "bullet", "urgent": True,
        }
        for invoice in market["invoices"]:
            result = assess(invoice["invoice_id"], market)
            risk = result["risk"]
            for field in ("pd", "pd_lower", "pd_upper"):
                assert 0.0 <= risk[field] <= 1.0, (
                    f"{invoice['invoice_id']} {field} = {risk[field]}"
                )
            assert risk["pd_lower"] <= risk["pd"] <= risk["pd_upper"]
            for entry in result["eligibility"]:
                assert entry["max_fundable_lakh"] >= 0.0

        scored = score_offers(_demo_offers(), {"invoice_id": "INV001"}, prefs)
        for offer in scored["offers"]:
            assert 0.0 <= offer["fit_score"] <= 1.0
            for name, value in offer["component_scores"].items():
                assert 0.0 <= value <= 1.0, f"{offer['offer_id']} {name} = {value}"


class TestEligibility:
    """Eligibility edge cases."""

    def test_eligibility_reasons(self):
        """Every ineligible provider has an exclusion_reason and binding_constraint."""
        from engine.eligibility import check_eligibility
        from engine.mockgen import generate_market
        from engine.risk import score_risk
        from engine.verify import verify

        market = generate_market(42)
        inv = next(i for i in market["invoices"] if i["invoice_id"] == "INV001")
        sup = next(s for s in market["suppliers"] if s["supplier_id"] == inv["supplier_id"])
        buy = next(b for b in market["buyers"] if b["buyer_id"] == inv["buyer_id"])
        v = verify("INV001", market)
        r = score_risk(inv, sup, buy, v)

        elig = check_eligibility(inv, sup, r, market["providers"])
        elig_by_id = {e["provider_id"]: e for e in elig}

        # 4 eligible, 2 excluded
        assert elig_by_id["PRV001"]["eligible"] is True
        assert elig_by_id["PRV002"]["eligible"] is True
        assert elig_by_id["PRV003"]["eligible"] is True
        assert elig_by_id["PRV004"]["eligible"] is True

        # PRV005 excluded due to max_ticket
        prv5 = elig_by_id["PRV005"]
        assert prv5["eligible"] is False
        assert prv5["binding_constraint"] == "max_ticket"
        assert prv5["max_fundable_lakh"] == 0.00
        assert "Coastal Cooperative Bank's" in prv5["exclusion_reason"]
        assert "exceeds" in prv5["exclusion_reason"]

        # PRV006 excluded due to risk_appetite (2.80% vs 1.50%, Sentinel Asset Managers')
        prv6 = elig_by_id["PRV006"]
        assert prv6["eligible"] is False
        assert prv6["binding_constraint"] == "risk_appetite"
        assert prv6["max_fundable_lakh"] == 0.00
        assert "Sentinel Asset Managers'" in prv6["exclusion_reason"]
        assert "Sentinel Asset Managers's" not in prv6["exclusion_reason"]
        assert "2.80%" in prv6["exclusion_reason"]
        assert "1.50%" in prv6["exclusion_reason"]

    def test_max_fundable(self):
        """Kestrel's max_fundable_lakh is 6.00 on demo invoice INV001."""
        from engine.eligibility import check_eligibility
        from engine.mockgen import generate_market
        from engine.risk import score_risk
        from engine.verify import verify

        market = generate_market(42)
        inv = next(i for i in market["invoices"] if i["invoice_id"] == "INV001")
        sup = next(s for s in market["suppliers"] if s["supplier_id"] == inv["supplier_id"])
        buy = next(b for b in market["buyers"] if b["buyer_id"] == inv["buyer_id"])
        v = verify("INV001", market)
        r = score_risk(inv, sup, buy, v)

        elig = check_eligibility(inv, sup, r, market["providers"])
        elig_by_id = {e["provider_id"]: e for e in elig}

        assert elig_by_id["PRV003"]["max_fundable_lakh"] == 6.00


class TestScoring:
    """Scoring edge cases."""

    def test_zero_span(self):
        """When an attribute is identical across all feasible offers, score is 1.0."""
        from engine.scoring import score_offers

        # All 4 demo offers have tenor_days = 60 (zero span -> 1.0 for all)
        prefs = {
            "preset": "cash_fastest",
            "weights": {"cost": 0.15, "advance": 0.30, "speed": 0.35, "tenor": 0.10, "fees": 0.05, "structure": 0.05},
            "min_advance_rate": 0.70,
            "max_days_to_cash": 5,
            "preferred_structure": "bullet",
            "urgent": False,
        }
        res = score_offers(_demo_offers(), {"invoice_id": "INV001"}, prefs)

        for offer in res["offers"]:
            if offer["feasible"]:
                assert offer["component_scores"]["tenor"] == 1.0


class TestPurity:
    """No side effects."""

    def test_no_input_mutation(self):
        """The market dict must be unchanged after assess — the API is stateless."""
        import copy

        from engine.assess import assess
        market = _market()
        before = copy.deepcopy(market)
        assess("INV001", market)
        assert market == before

    def test_unknown_invoice_raises(self):
        """A typo'd id is a bad request, so B can map it to a 400 not a 500."""
        from engine.assess import UnknownEntityError, assess
        with pytest.raises(UnknownEntityError) as exc:
            assess("INV999", _market())
        assert exc.value.entity_id == "INV999"

    def test_rejected_invoice_has_no_offers(self):
        """A rejected invoice produces no risk score and no offers — §3.1."""
        from engine.assess import assess
        result = assess("INV002", _market())
        assert result["verification"]["status"] == "rejected"
        assert result["eligibility"] == []
        assert result["meta"]["assessed"] is False


class TestHardeningEdgeCases:
    """Edge cases identified during Phase 4 hardening."""

    def test_irn_malformed_hex_rejected(self):
        """64-char string with non-hex characters is rejected as malformed IRN."""
        import copy

        from engine.verify import verify

        market = copy.deepcopy(_market())
        market["invoices"][0]["irn"] = "g" * 64
        v = verify(market["invoices"][0]["invoice_id"], market)
        assert v["status"] == "rejected"
        assert v["irn_valid"] is False
        assert "malformed" in v["reason_text"]

    def test_unknown_buyer_handling(self):
        """Invoice with unknown buyer_id fails verification tag and raises in assess."""
        import copy

        from engine.assess import UnknownEntityError, assess
        from engine.verify import verify

        market = copy.deepcopy(_market())
        market["invoices"][0]["buyer_id"] = "BUY999"
        v = verify(market["invoices"][0]["invoice_id"], market)
        assert v["field_confidence"].get("buyer_gstin") != "verified"

        with pytest.raises(UnknownEntityError):
            assess(market["invoices"][0]["invoice_id"], market)

    def test_brand_new_buyer_no_delay_data(self):
        """Buyer with no prior payment delay history evaluates gracefully."""
        from engine.risk import score_risk
        from engine.verify import verify

        market = _market()
        inv = market["invoices"][0]
        sup = market["suppliers"][0]
        v = verify("INV001", market)

        buyer_new = {"buyer_id": "BUY_NEW", "credit_grade": "A"}
        r = score_risk(inv, sup, buyer_new, v)
        assert 0.0 <= r["pd"] <= 1.0
        assert r["risk_band"] in ("prime", "standard", "watch", "decline")

    def test_zero_prior_financings_and_defaults(self):
        """prior_financings=0 with prior_defaults=0 produces NO_HISTORY_PRIOR."""
        from engine.config import NO_HISTORY_PRIOR
        from engine.risk import _default_rate

        sup_no_hist = {"supplier_id": "SUP_TEST", "prior_financings": 0, "prior_defaults": 0}
        assert _default_rate(sup_no_hist) == NO_HISTORY_PRIOR

        sup_clean = {"supplier_id": "SUP_TEST", "prior_financings": 5, "prior_defaults": 0}
        assert _default_rate(sup_clean) == 0.0

    def test_risk_band_boundaries(self):
        """Banding on exact threshold values strictly matches config.py convention."""
        from engine.risk import _risk_band

        assert _risk_band(0.0299) == "prime"
        assert _risk_band(0.0300) == "standard"
        assert _risk_band(0.0599) == "standard"
        assert _risk_band(0.0600) == "watch"
        assert _risk_band(0.1199) == "watch"
        assert _risk_band(0.1200) == "decline"

    def test_zero_available_liquidity_ineligible(self):
        """Provider with available_liquidity_lakh=0 is marked ineligible for liquidity."""
        import copy

        from engine.eligibility import check_eligibility
        from engine.risk import score_risk
        from engine.verify import verify

        market = copy.deepcopy(_market())
        inv = market["invoices"][0]
        sup = market["suppliers"][0]
        buy = market["buyers"][0]
        r = score_risk(inv, sup, buy, verify("INV001", market))

        market["providers"][0]["available_liquidity_lakh"] = 0.0
        elig = check_eligibility(inv, sup, r, market["providers"])
        p0 = next(e for e in elig if e["provider_id"] == market["providers"][0]["provider_id"])
        assert p0["eligible"] is False
        assert p0["binding_constraint"] == "liquidity"
        assert p0["max_fundable_lakh"] == 0.00

    def test_exact_max_ticket_boundary_eligible(self):
        """Invoice amount exactly equal to max_ticket_lakh is eligible."""
        import copy

        from engine.eligibility import check_eligibility
        from engine.risk import score_risk
        from engine.verify import verify

        market = copy.deepcopy(_market())
        inv = dict(market["invoices"][0], amount_lakh=10.0)
        sup = market["suppliers"][0]
        buy = market["buyers"][0]
        r = score_risk(inv, sup, buy, verify("INV001", market))

        market["providers"][0]["max_ticket_lakh"] = 10.0
        market["providers"][0]["min_ticket_lakh"] = 1.0
        market["providers"][0]["available_liquidity_lakh"] = 100.0
        elig = check_eligibility(inv, sup, r, market["providers"])
        p0 = next(e for e in elig if e["provider_id"] == market["providers"][0]["provider_id"])
        assert p0["eligible"] is True

    def test_all_offers_infeasible(self):
        """When all offers are infeasible, ranking handles empty feasible set gracefully."""
        from engine.assess import assess, score_offers
        from market.simulate import generate_offers

        market = _market()
        a = assess("INV001", market)
        offers = generate_offers("INV001", market, a)

        prefs = dict(market["suppliers"][0]["preferences"], min_advance_rate=0.99)
        scored = score_offers(offers, a, prefs)

        assert scored["summary"]["offer_count"] == len(offers)
        assert scored["summary"]["feasible_count"] == 0
        assert all(o["feasible"] is False for o in scored["offers"])
        assert all(o["fit_score"] == 0.0 for o in scored["offers"])
        assert all(bool(o["reason_text"]) for o in scored["offers"])
        assert len(scored["ranking"]) == len(offers)
        assert len(scored["naive_ranking"]) == len(offers)

    def test_floating_point_weight_tolerance(self):
        """Weight drift within WEIGHT_SUM_TOLERANCE succeeds; large drift raises InvalidWeightsError."""
        import copy

        from engine.assess import InvalidWeightsError, assess, score_offers
        from market.simulate import generate_offers

        market = _market()
        a = assess("INV001", market)
        offers = generate_offers("INV001", market, a)

        # Drift within tolerance (sum = 0.9999999998)
        prefs_drift = copy.deepcopy(market["suppliers"][0]["preferences"])
        prefs_drift["weights"] = {
            "cost": 0.1499999999, "advance": 0.30, "speed": 0.35,
            "tenor": 0.10, "fees": 0.05, "structure": 0.0499999999,
        }
        res = score_offers(offers, a, prefs_drift)
        assert res["summary"]["best_fit_offer_id"] is not None

        # Exceeding tolerance (sum = 0.90)
        prefs_bad = copy.deepcopy(market["suppliers"][0]["preferences"])
        prefs_bad["weights"] = {
            "cost": 0.10, "advance": 0.30, "speed": 0.30,
            "tenor": 0.10, "fees": 0.05, "structure": 0.05,
        }
        with pytest.raises(InvalidWeightsError):
            score_offers(offers, a, prefs_bad)

    def test_component_scores_tie_reason(self):
        """When all offers have identical terms, reason_text is non-empty and well-formed."""
        from engine.assess import assess, score_offers

        market = _market()
        a = assess("INV001", market)
        offers_identical = [
            {
                "offer_id": f"OFR00{i}", "provider_id": f"PRV00{i}",
                "rate_annual": 0.088, "advance_rate": 0.85, "days_to_settle": 1,
                "tenor_days": 60, "fee_percent": 0.001, "fee_flat_lakh": 0.0,
                "repayment_structure": "bullet", "feasible": True,
            }
            for i in range(1, 5)
        ]
        res = score_offers(offers_identical, a, market["suppliers"][0]["preferences"])
        assert len(res["offers"]) == 4
        for o in res["offers"]:
            assert bool(o["reason_text"])
            assert isinstance(o["reason_text"], str)
            assert len(o["reason_text"]) > 10

