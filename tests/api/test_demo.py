"""The eight-step demo, walked end to end against one API process.

Phase 3's exit criterion is "the eight-step demo runs without a restart"
(PERSON_B.md §9). The individual pieces are covered elsewhere; this is the
one test that fails if the *sequence* breaks — a step that only works after a
reload, or a step that quietly depends on a previous one having run.

Every id comes from data/fixtures/demo_scenario.json. Nothing here hardcodes
INV001 (DEMO_SCENARIO.md §9).

Owner: Person B
"""

import json
import os

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _fixture():
    path = os.path.join(os.path.dirname(__file__), "..", "..",
                        "data", "fixtures", "demo_scenario.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def demo():
    """Every step's response, collected from one client without restarting."""
    fx = _fixture()
    invoice_id = fx["invoice_id"]

    urgent = {"scenario": {"preference_overrides": [{
        "supplier_id": fx["supplier_id"], "urgent": True,
        "weights": {"cost": 0.10, "advance": 0.30, "speed": 0.45,
                    "tenor": 0.05, "fees": 0.05, "structure": 0.05}}]}}

    steps = {
        "fixture": fx,
        "market": client.get("/api/market").json(),
        "assess": client.post("/api/assess",
                              json={"invoice_id": invoice_id}).json(),
        "duplicate": client.post("/api/assess",
                                 json={"invoice_id": fx["duplicate_invoice_id"]}).json(),
        "offers": client.post("/api/offers",
                              json={"invoice_id": invoice_id}).json(),
        "slider": client.post("/api/offers",
                              json={"invoice_id": invoice_id, **urgent}).json(),
        "clear": client.post("/api/clear",
                             json={"invoice_ids": [invoice_id]}).json(),
    }
    match = steps["clear"]["matches"][0]
    steps["settle"] = client.post(
        "/api/settle",
        json={"match_id": match["match_id"], **fx["settlement_event"]}).json()
    # Run after settling, to prove step 8 left nothing behind.
    steps["assess_again"] = client.post("/api/assess",
                                        json={"invoice_id": invoice_id}).json()
    return steps


def test_step1_market_view(demo):
    market = demo["market"]
    assert market["invoices"] and len(market["providers"]) == 6


def test_step2_verify_and_block_the_duplicate(demo):
    """We verify before we finance, and catch the same invoice financed twice."""
    assert demo["assess"]["verification"]["status"] == "verified"
    duplicate = demo["duplicate"]["verification"]
    assert duplicate["status"] == "rejected"
    assert duplicate["duplicate_of"] == demo["fixture"]["invoice_id"]


def test_step3_risk_states_its_range(demo):
    """The range is the honest part — a point estimate would hide the unknown field."""
    expected = demo["fixture"]["expected_risk"]
    risk = demo["assess"]["risk"]
    assert risk["pd_lower"] < risk["pd"] < risk["pd_upper"]
    assert risk["risk_band"] == expected["risk_band"]
    assert [risk["pd_lower"], risk["pd_upper"]] == expected["pd_range"]


def test_step4_two_providers_grey_out_with_reasons(demo):
    fixture = demo["fixture"]
    eligibility = {e["provider_id"]: e for e in demo["assess"]["eligibility"]}
    assert sorted(p for p, e in eligibility.items()
                  if e["eligible"]) == fixture["expected_eligible"]
    for provider_id in fixture["expected_excluded"]:
        assert eligibility[provider_id]["exclusion_reason"]


def test_step5_four_offers_differ_on_more_than_rate(demo):
    """Four rates thirty basis points apart makes the whole product pointless."""
    offers = demo["offers"]["offers"]
    assert len(offers) == 4
    terms = {(o["advance_rate"], o["days_to_settle"], o["repayment_structure"])
             for o in offers}
    assert len(terms) == 4, "the offers differ only by rate"


def test_step6_fit_beats_rate(demo):
    """The assertion that the product still makes its point."""
    slider = demo["slider"]
    assert slider["summary"]["fit_beats_rate"]
    assert slider["ranking"][0] != slider["naive_ranking"][0]


def test_step6_the_slider_actually_reorders(demo):
    """Dragging the weights must move the ranking, not just the numbers.

    Speed-and-advance keeps OFR003 on top — it is already there at baseline, so
    that alone would pass with the sliders disconnected. Dragging toward cost
    instead promotes the fixture's expected_cheapest_preset_winner, which is a
    different offer and therefore a real reorder.
    """
    fixture = demo["fixture"]
    cheapest = {"scenario": {"preference_overrides": [{
        "supplier_id": fixture["supplier_id"], "urgent": False,
        "weights": {"cost": 0.60, "advance": 0.10, "speed": 0.10,
                    "tenor": 0.10, "fees": 0.05, "structure": 0.05}}]}}
    body = client.post("/api/offers",
                       json={"invoice_id": fixture["invoice_id"], **cheapest}).json()
    assert body["ranking"][0] == fixture["expected_cheapest_preset_winner"]
    assert body["ranking"][0] != demo["offers"]["ranking"][0]


def test_step7_clearing_syndicates_and_stops_at_matched(demo):
    """Kestrel wants all of it; its sector book won't allow it. matched, not funded."""
    match = demo["clear"]["matches"][0]
    assert match["syndicated"]
    assert len(match["allocations"]) > 1
    assert match["state"] == "matched"
    assert demo["clear"]["summary"]["stable"]
    assert match["total_advance_lakh"] == demo["fixture"]["expected_match"][
        "total_advance_lakh"]


def test_step8_settling_late_moves_the_market(demo):
    """The closing beat: the market notices, reprices, and reallocates."""
    settle = demo["settle"]
    assert settle["before"]["match"]["state"] == "funded"
    assert settle["after"]["match"]["state"] == "late"
    delta = settle["delta"]
    assert delta["repriced_invoices"], "a late payment must reprice something"
    assert delta["provider_bid_adjustments"], "and must move somebody's next bid"
    assert delta["summary_text"]


def test_step8_the_naive_counterfactual(demo):
    """The same four lenders, ranked by rate alone, hand over less cash."""
    offers = {o["offer_id"]: o for o in demo["offers"]["offers"]}
    cheapest = offers[demo["offers"]["naive_ranking"][0]]
    assert (demo["clear"]["matches"][0]["total_advance_lakh"]
            > cheapest["advance_amount_lakh"])


def test_the_sequence_leaves_no_residue(demo):
    """Step 8 must not change what step 2 would say if you ran it again.

    The failure mode that would hurt most on stage: rehearse the demo twice
    and get different numbers the second time.
    """
    assert demo["assess_again"] == demo["assess"]
