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

    @pytest.mark.skip(reason="Person A: implement after engine is built")
    def test_determinism(self):
        pass


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

    @pytest.mark.skip(reason="Person A: implement after assess")
    def test_assess_validates(self):
        pass


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
    """The four demo offers produce exactly the stated values."""

    def test_demo_offers(self):
        """All 4 demo offers produce exact all-in costs and fit scores matching DEMO_SCENARIO.md §4."""
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

        # OFR001: ₹16,836 cost, fit_score 0.71 (0.715)
        o1 = offers_by_id["OFR001"]
        assert round(o1["total_cost_lakh"] * 100000) in (16835, 16836) or o1["total_cost_lakh"] == 0.1684
        assert abs(o1["fit_score"] - 0.71) <= 0.01

        # OFR002: ₹17,437 cost, fit_score 0.64 (0.635)
        o2 = offers_by_id["OFR002"]
        assert round(o2["total_cost_lakh"] * 100000) in (17436, 17437) or o2["total_cost_lakh"] == 0.1744
        assert abs(o2["fit_score"] - 0.64) <= 0.01

        # OFR003: ₹16,722 cost, fit_score 0.89 (0.890)
        o3 = offers_by_id["OFR003"]
        assert round(o3["total_cost_lakh"] * 100000) in (16722, 16723) or o3["total_cost_lakh"] == 0.1672
        assert abs(o3["fit_score"] - 0.89) <= 0.01

        # OFR004: ₹14,589 cost, fit_score 0.68 (0.678)
        o4 = offers_by_id["OFR004"]
        assert round(o4["total_cost_lakh"] * 100000) in (14589, 14590) or o4["total_cost_lakh"] == 0.1459
        assert abs(o4["fit_score"] - 0.68) <= 0.01

    def test_demo_ranking(self):
        """Full ordered rankings (both fit auction and naive auction) match expected fixtures."""
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

        # Full fit auction ranking element-by-element
        assert res["ranking"] == ["OFR003", "OFR001", "OFR004", "OFR002"]

        # Full naive rate auction ranking element-by-element
        assert res["naive_ranking"] == ["OFR002", "OFR003", "OFR001", "OFR004"]

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

    @pytest.mark.skip(reason="Person A: implement after risk")
    def test_scores_bounded(self):
        pass


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
        """When tenor is identical across all feasible offers, no division by zero occurs."""
        from engine.scoring import score_offers

        # All 4 demo offers have tenor_days = 60 (normalized against 120-day benchmark -> 0.50)
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
                assert offer["component_scores"]["tenor"] == 0.50
                assert 0.0 <= offer["fit_score"] <= 1.0


class TestPurity:
    """No side effects."""

    @pytest.mark.skip(reason="Person A: implement after assess")
    def test_no_input_mutation(self):
        pass
