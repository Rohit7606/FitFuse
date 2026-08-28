"""Tests for the API — Person B's API test suite.

Test list from PERSON_B.md §7:
    test_market_shape       — /api/market validates against MarketResponse
    test_assess_shape       — /api/assess validates against Assessment
    test_offers_shape       — /api/offers validates, naive_ranking present
    test_clear_shape        — /api/clear validates against ClearingResponse
    test_settle_shape       — /api/settle validates against SettleResponse
    test_unknown_id_400     — bad ID returns 400, not 500, names the ID
    test_bad_weights_400    — weights summing to 0.87 return 400
    test_malformed_422      — garbage body returns 422
    test_stateless          — two identical requests → identical responses
    test_fit_beats_rate     — /api/offers on INV001 returns fit_beats_rate: true

Owner: Person B
"""

import json
import os

import jsonschema
import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "schema.json")
with open(_SCHEMA_PATH, encoding="utf-8") as _f:
    SCHEMA = json.load(_f)

BASELINE = {"scenario": {"preference_overrides": [], "liquidity_overrides": [],
                         "settlement_events": [], "naive_mode": False}}


def validates(instance, definition):
    """Validate against one definition in schema.json.

    The document is definitions-only, so a bare validate() against its root
    accepts anything — the $ref is what makes this a real check.
    """
    jsonschema.validate(
        instance=instance,
        schema={**SCHEMA, "$ref": f"#/definitions/{definition}"},
    )


class TestEndpointShapes:
    """All five endpoints return contract-valid shapes."""

    def test_market_shape(self):
        r = client.get("/api/market")
        assert r.status_code == 200
        body = r.json()
        for key in ("meta", "suppliers", "buyers", "invoices", "providers"):
            assert key in body, f"/api/market missing {key}"
        assert len(body["providers"]) == 6

    def test_assess_shape(self):
        r = client.post("/api/assess", json={"invoice_id": "INV001", **BASELINE})
        assert r.status_code == 200
        validates(r.json(), "Assessment")

    def test_offers_shape(self):
        r = client.post("/api/offers", json={"invoice_id": "INV001", **BASELINE})
        assert r.status_code == 200
        body = r.json()
        validates(body["assessment"], "Assessment")
        for offer in body["offers"]:
            validates(offer, "ScoredOffer")
        # Always returned, so the frontend can toggle the counterfactual with
        # no second request — PERSON_B.md §4.3.
        assert body["naive_ranking"], "naive_ranking must be present"

    def test_clear_shape(self):
        r = client.post("/api/clear", json={"invoice_ids": ["INV001"], **BASELINE})
        assert r.status_code == 200
        body = r.json()
        for match in body["matches"]:
            validates(match, "Match")
        assert body["summary"]["stable"] is True

    def test_settle_shape(self):
        r = client.post("/api/settle", json={"match_id": "MCH001", "outcome": "late",
                                             "days_late": 5, **BASELINE})
        assert r.status_code == 200
        body = r.json()
        validates(body["before"]["match"], "Match")
        validates(body["after"]["match"], "Match")
        validates(body["delta"], "LearningDelta")

    def test_syndicated_allocations_sum(self):
        """Match.allocations must sum to total_advance_lakh — SCHEMA.md §6."""
        body = client.post("/api/clear",
                           json={"invoice_ids": ["INV001"], **BASELINE}).json()
        for match in body["matches"]:
            total = round(sum(a["amount_lakh"] for a in match["allocations"]), 2)
            assert total == match["total_advance_lakh"]


class TestErrorHandling:
    """Error responses follow SCHEMA.md §5.7."""

    @pytest.mark.parametrize("endpoint,payload", [
        ("/api/assess", {"invoice_id": "INV999"}),
        ("/api/offers", {"invoice_id": "INV999"}),
        ("/api/clear", {"invoice_ids": ["INV999"]}),
    ])
    def test_unknown_id_400(self, endpoint, payload):
        r = client.post(endpoint, json={**payload, **BASELINE})
        assert r.status_code == 400, "a typo'd ID is a bad request, not a 500"
        body = r.json()
        assert body["error"] == "unknown_entity"
        assert "INV999" in body["detail"], "the error must name the offending ID"

    def test_bad_weights_400(self):
        bad = {"preference_overrides": [{"supplier_id": "SUP001", "urgent": False,
                                         "weights": {"cost": 0.15, "advance": 0.30,
                                                     "speed": 0.20, "tenor": 0.10,
                                                     "fees": 0.07, "structure": 0.05}}],
               "liquidity_overrides": [], "settlement_events": [], "naive_mode": False}
        r = client.post("/api/offers", json={"invoice_id": "INV001", "scenario": bad})
        assert r.status_code == 400
        body = r.json()
        assert body["error"] == "invalid_weights"
        assert "0.87" in body["detail"]

    def test_malformed_422(self):
        r = client.post("/api/assess", json={"not_a_field": "garbage"})
        assert r.status_code == 422

    def test_illegal_transition_400(self):
        r = client.post("/api/settle", json={"match_id": "MCH001",
                                             "outcome": "funded", **BASELINE})
        assert r.status_code == 400
        assert r.json()["error"] == "illegal_transition"

    def test_no_500s_on_bad_input(self):
        """Never a 500 for a bad request — SCHEMA.md §5.7."""
        for payload in ({"invoice_id": ""}, {"invoice_id": "!!!"},
                        {"invoice_id": "SUP001"}):
            r = client.post("/api/assess", json={**payload, **BASELINE})
            assert r.status_code < 500, f"{payload} produced a {r.status_code}"


class TestScoringSeam:
    """One invoice must never be scored two different ways.

    Person A raised this in review: agents produce unscored Offers, clearing
    needs ScoredOffers, and for a while both /api/offers and simulate.clear()
    called engine.score_offers() independently. Two call sites is two chances
    to drift, so scoring now goes through market.simulate.scored_offers() and
    this test holds it there.
    """

    def test_endpoint_and_seam_agree(self):
        from api.main import load_market, to_scenario
        from engine.assess import assess
        from market import simulate

        market = load_market()
        assessment = assess("INV001", market)
        seam = simulate.scored_offers("INV001", market, assessment,
                                      to_scenario(None))
        endpoint = client.post("/api/offers",
                               json={"invoice_id": "INV001", **BASELINE}).json()
        for key in ("offers", "ranking", "naive_ranking", "summary"):
            assert endpoint[key] == seam[key], f"{key} diverges from the seam"

    def test_clearing_uses_the_same_scoring(self):
        """Clearing must rank on the same fit scores the offers endpoint shows."""
        from api.main import load_market
        from market import simulate

        market = load_market()
        endpoint = client.post("/api/offers",
                               json={"invoice_id": "INV001", **BASELINE}).json()
        winner = endpoint["ranking"][0]
        match = simulate.clear(["INV001"], market)["matches"][0]
        assert match["allocations"][0]["offer_id"] == winner


class TestStateless:
    """No server-side state — AGENTS.md §3.4."""

    def test_stateless(self):
        req = {"invoice_id": "INV001", **BASELINE}
        first = client.post("/api/offers", json=req).json()
        # A settle call in between must not affect a later assess/offers call.
        client.post("/api/settle", json={"match_id": "MCH001", "outcome": "late",
                                         "days_late": 5, **BASELINE})
        second = client.post("/api/offers", json=req).json()
        assert first == second, "a settle call leaked state into a later request"


class TestProductThesis:
    """The one assertion that the product still makes its point."""

    def test_fit_beats_rate(self):
        body = client.post("/api/offers",
                           json={"invoice_id": "INV001", **BASELINE}).json()
        assert body["summary"]["fit_beats_rate"] is True
        assert body["ranking"][0] == "OFR003", "the fit winner is Kestrel"
        assert body["naive_ranking"][0] == "OFR002", "the lowest rate is Arcline"
