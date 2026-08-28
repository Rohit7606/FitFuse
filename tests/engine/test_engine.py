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


class TestDemoScenario:
    """The four demo offers produce exactly the stated values."""

    @pytest.mark.skip(reason="Person A: implement after scoring")
    def test_demo_offers(self):
        pass

    @pytest.mark.skip(reason="Person A: implement after scoring")
    def test_demo_ranking(self):
        pass

    @pytest.mark.skip(reason="Person A: implement after scoring")
    def test_preset_flip(self):
        pass


class TestHardConstraints:
    """An offer below min_advance_rate is feasible:false and still returned."""

    @pytest.mark.skip(reason="Person A: implement after scoring")
    def test_hard_constraints(self):
        pass


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

    @pytest.mark.skip(reason="Person A: implement after eligibility")
    def test_eligibility_reasons(self):
        pass

    @pytest.mark.skip(reason="Person A: implement after eligibility")
    def test_max_fundable(self):
        pass


class TestScoring:
    """Scoring edge cases."""

    @pytest.mark.skip(reason="Person A: implement after scoring")
    def test_zero_span(self):
        pass


class TestPurity:
    """No side effects."""

    @pytest.mark.skip(reason="Person A: implement after assess")
    def test_no_input_mutation(self):
        pass
