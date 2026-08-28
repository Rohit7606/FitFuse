"""Phase 4 — error paths, edge cases and response budgets.

The rule these tests hold (SCHEMA.md §5.7, PERSON_B.md §5):

    Never a 500 for a bad request. Never a 200 with an error inside.
    Never a 200 that is confidently wrong.

That third one is the interesting case and it is why this file exists. A
scenario whose weights sum to 1.0 over the *wrong* keys used to return a
ranking — correct-looking, authoritative, and meaningless. An error would have
been strictly better, and that bug was live in the frontend.

Owner: Person B
"""

import json
import math
import time

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.models import WEIGHT_KEYS

client = TestClient(app)

JSON = {"Content-Type": "application/json"}
W_OK = {"cost": 0.15, "advance": 0.30, "speed": 0.35,
        "tenor": 0.10, "fees": 0.05, "structure": 0.05}

# Every endpoint that takes a body, with a valid payload to perturb.
ENDPOINTS = {
    "/api/assess": {"invoice_id": "INV001"},
    "/api/offers": {"invoice_id": "INV001"},
    "/api/clear": {"invoice_ids": ["INV001"]},
    "/api/settle": {"match_id": "MCH001", "outcome": "late", "days_late": 5},
}


def _scenario(**kw):
    base = {"preference_overrides": [], "liquidity_overrides": [],
            "settlement_events": [], "naive_mode": False}
    base.update(kw)
    return {"scenario": base}


def _assert_clean(response):
    """Whatever else it is, it must be a well-formed, honest response."""
    assert response.status_code < 500, response.text[:300]
    body = response.json()
    if response.status_code == 200:
        assert "error" not in body, f"200 with an error inside: {body.get('error')}"
        json.dumps(body, allow_nan=False)  # raises if a NaN reached the wire
    else:
        assert body.get("error"), f"error body without an error key: {body}"
        assert isinstance(body.get("detail"), str) and body["detail"], body
    return body


# ---------------------------------------------------------------------------
# Bad identifiers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "", " ", "INV999", "inv001", "INV001 ", "SUP001", "!!!", "../etc/passwd",
    "INV0001", "0", "-1", "null", "None", "A" * 500, "🙂",
])
@pytest.mark.parametrize("path", list(ENDPOINTS))
def test_bad_identifier_is_never_a_500(path, bad):
    payload = dict(ENDPOINTS[path])
    key = next(k for k in ("invoice_id", "invoice_ids", "match_id") if k in payload)
    payload[key] = [bad] if key == "invoice_ids" else bad
    _assert_clean(client.post(path, json=payload))


def test_unknown_id_names_the_id():
    """A human under time pressure needs the offending value, not a code."""
    for path, key in (("/api/assess", "invoice_id"), ("/api/offers", "invoice_id")):
        body = client.post(path, json={key: "INV999"}).json()
        assert body["error"] == "unknown_entity"
        assert "INV999" in body["detail"]
        assert body["entity_id"] == "INV999"


# ---------------------------------------------------------------------------
# Weights — the case where a 200 was worse than an error
# ---------------------------------------------------------------------------

def test_the_six_dimensions_come_from_the_schema():
    """Retyping them here is how the API and the contract drift apart."""
    assert set(WEIGHT_KEYS) == set(W_OK)


@pytest.mark.parametrize("weights,why", [
    ({}, "empty"),
    ({"cost": 1.0}, "one dimension only"),
    ({"unknown_key": 1.0}, "no real dimension at all"),
    (dict(W_OK, extra=0.0), "an extra dimension"),
    ({k: v for k, v in W_OK.items() if k != "advance"}, "one dimension missing"),
])
def test_a_weight_vector_that_is_not_the_contract_is_rejected(weights, why):
    body = _assert_clean(client.post(
        "/api/offers",
        json={"invoice_id": "INV001",
              **_scenario(preference_overrides=[
                  {"supplier_id": "SUP001", "weights": weights}])}))
    assert "error" in body, f"{why} was accepted"


def test_the_frontends_old_key_would_have_been_caught():
    """web/ sent `advance_rate`, which is not a dimension.

    It summed to 1.0, so it passed the sum check, and the engine read
    weights['advance'] as absent — the advance slider drove the ranking with a
    weight of zero and every fit score collapsed. This is the regression guard.
    """
    stale = {"cost": 0.10, "advance_rate": 0.05, "speed": 0.60,
             "tenor": 0.15, "fees": 0.05, "structure": 0.05}
    assert abs(sum(stale.values()) - 1.0) < 1e-9, "it really did sum to 1.0"
    r = client.post("/api/offers",
                    json={"invoice_id": "INV001",
                          **_scenario(preference_overrides=[
                              {"supplier_id": "SUP001", "weights": stale}])})
    assert r.status_code == 422
    assert "advance" in r.json()["detail"]


def test_weights_that_do_not_sum_to_one_are_a_400():
    """SCHEMA.md §5.7 puts the sum specifically at 400 invalid_weights."""
    body = client.post("/api/offers",
                       json={"invoice_id": "INV001",
                             **_scenario(preference_overrides=[
                                 {"supplier_id": "SUP001",
                                  "weights": dict(W_OK, cost=0.9)}])}).json()
    assert body["error"] == "invalid_weights"
    assert "1.75" in body["detail"]


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("path", list(ENDPOINTS))
def test_non_finite_weights_on_the_wire(path, literal):
    """json.loads accepts these literals, so any HTTP client can send them.

    NaN defeats every comparison it touches, so `abs(total - 1.0) > tolerance`
    was False for a NaN total: the weights sailed through the sum check and
    every offer scored 1.0. The ranking that came back was alphabetical and
    presented as a result.
    """
    payload = json.dumps({**ENDPOINTS[path],
                          **_scenario(preference_overrides=[
                              {"supplier_id": "SUP001",
                               "weights": dict(W_OK, cost=0.0)}])})
    raw = payload.replace('"cost": 0.0', f'"cost": {literal}')
    _assert_clean(client.post(path, content=raw, headers=JSON))


def test_a_non_finite_value_does_not_break_the_error_response_itself():
    """The 422 body echoes the input, so NaN once made the *error* unserialisable.

    starlette renders JSON with allow_nan=False, so the exception escaped the
    app and the client got a 500 with no body — the one outcome §5.7 forbids.
    """
    raw = ('{"invoice_id":"INV001","scenario":{"preference_overrides":'
           '[{"supplier_id":"SUP001","weights":{"cost":NaN,"advance":0.3,'
           '"speed":0.35,"tenor":0.1,"fees":0.05,"structure":0.05}}]}}')
    r = client.post("/api/offers", content=raw, headers=JSON)
    assert r.status_code == 422
    assert "finite" in r.json()["detail"]
    assert isinstance(r.json()["detail"], str), "web/ does throw new Error(detail)"
    json.dumps(r.json(), allow_nan=False)


# ---------------------------------------------------------------------------
# Scenario overrides that used to be ignored in silence
# ---------------------------------------------------------------------------

def test_an_override_for_an_unknown_supplier_is_a_400():
    """Silently ignored, this looks on stage like a slider that does nothing."""
    body = client.post("/api/offers",
                       json={"invoice_id": "INV001",
                             **_scenario(preference_overrides=[
                                 {"supplier_id": "SUP999",
                                  "weights": W_OK}])}).json()
    assert body["error"] == "unknown_entity"
    assert body["entity_id"] == "SUP999"


def test_an_override_for_an_unknown_provider_is_a_400():
    body = client.post("/api/clear",
                       json={"invoice_ids": ["INV001"],
                             **_scenario(liquidity_overrides=[
                                 {"provider_id": "PRV999",
                                  "available_liquidity_lakh": 10.0}])}).json()
    assert body["error"] == "unknown_entity"
    assert body["entity_id"] == "PRV999"


def test_negative_liquidity_is_rejected():
    """A provider cannot have less than nothing, and clearing would still match."""
    r = client.post("/api/clear",
                    json={"invoice_ids": ["INV001"],
                          **_scenario(liquidity_overrides=[
                              {"provider_id": "PRV003",
                               "available_liquidity_lakh": -5.0}])})
    assert r.status_code == 422


def test_draining_every_provider_leaves_the_invoice_unmatched_with_a_reason():
    """The honest empty result, not an exception and not a silent empty list."""
    body = client.post("/api/clear",
                       json={"invoice_ids": ["INV001"],
                             **_scenario(liquidity_overrides=[
                                 {"provider_id": f"PRV00{n}",
                                  "available_liquidity_lakh": 0.0}
                                 for n in range(1, 7)])}).json()
    assert body["matches"] == []
    assert body["unmatched"][0]["invoice_id"] == "INV001"
    assert body["unmatched"][0]["reason"]


# ---------------------------------------------------------------------------
# Edge cases in the market itself
# ---------------------------------------------------------------------------

def test_clearing_a_rejected_invoice_answers_rather_than_dropping_it():
    """Ten invoices in, ten answers out — INV002 is a duplicate, not a silence."""
    body = client.post("/api/clear", json={"invoice_ids": ["INV002"]}).json()
    assert body["matches"] == []
    assert [u["invoice_id"] for u in body["unmatched"]] == ["INV002"]
    assert "uplicate" in body["unmatched"][0]["reason"]


def test_clearing_the_same_invoice_twice_does_not_double_allocate():
    once = client.post("/api/clear", json={"invoice_ids": ["INV001"]}).json()
    twice = client.post("/api/clear",
                        json={"invoice_ids": ["INV001", "INV001"]}).json()
    assert len(twice["matches"]) == len(once["matches"]) == 1
    assert twice["matches"][0]["total_advance_lakh"] == \
        once["matches"][0]["total_advance_lakh"]


def test_clearing_every_invoice_stays_within_every_providers_liquidity():
    """The whole book at once — the case that would over-allocate if capacity
    were only re-checked at the start of a round."""
    market = client.get("/api/market").json()
    ids = [i["invoice_id"] for i in market["invoices"]]
    body = client.post("/api/clear", json={"invoice_ids": ids}).json()
    liquidity = {p["provider_id"]: p["available_liquidity_lakh"]
                 for p in market["providers"]}
    committed = {}
    for match in body["matches"]:
        for alloc in match["allocations"]:
            committed[alloc["provider_id"]] = (
                committed.get(alloc["provider_id"], 0.0) + alloc["amount_lakh"])
    for provider_id, used in committed.items():
        assert used <= liquidity[provider_id] + 1e-6, provider_id
    assert len(body["matches"]) + len(body["unmatched"]) == len(ids)


def test_clearing_the_whole_book_respects_every_concentration_limit():
    """AGENTS.md §4.5 — no provider past a sector or buyer limit, in aggregate.

    Per-invoice headroom is not a limit. eligibility.max_fundable_lakh answers
    "how much of THIS invoice may you fund", and clearing used the largest such
    answer as a budget for the entire run without subtracting as it spent. One
    invoice looked correct; the full book put Meridian ₹31 lakh past its
    textiles limit and Kestrel past its auto-components limit.
    """
    market = client.get("/api/market").json()
    invoices = {i["invoice_id"]: i for i in market["invoices"]}
    buyers = {b["buyer_id"]: b for b in market["buyers"]}
    providers = {p["provider_id"]: p for p in market["providers"]}

    body = client.post("/api/clear",
                       json={"invoice_ids": list(invoices)}).json()

    by_sector, by_buyer = {}, {}
    for match in body["matches"]:
        invoice = invoices[match["invoice_id"]]
        sector = buyers[invoice["buyer_id"]]["sector"]
        for alloc in match["allocations"]:
            pid = alloc["provider_id"]
            by_sector.setdefault(pid, {}).setdefault(sector, 0.0)
            by_sector[pid][sector] += alloc["amount_lakh"]
            by_buyer.setdefault(pid, {}).setdefault(invoice["buyer_id"], 0.0)
            by_buyer[pid][invoice["buyer_id"]] += alloc["amount_lakh"]

    assert by_sector, "nothing cleared, so nothing was actually checked"

    for pid, sectors in by_sector.items():
        provider = providers[pid]
        portfolio = provider["total_portfolio_lakh"]
        held = provider.get("current_exposure", {}).get("by_sector", {})
        for sector, funded in sectors.items():
            limit = (provider.get("sector_limits") or {}).get(sector)
            if limit is None:
                continue
            cap = limit * portfolio
            total = held.get(sector, 0.0) + funded
            assert total <= cap + 1e-6, (
                f"{pid} holds {total:.2f} lakh in {sector}, cap {cap:.2f}")

    for pid, buyer_totals in by_buyer.items():
        provider = providers[pid]
        limit = provider.get("buyer_limit")
        if limit is None:
            continue
        cap = limit * provider["total_portfolio_lakh"]
        held = provider.get("current_exposure", {}).get("by_buyer", {})
        for buyer_id, funded in buyer_totals.items():
            total = held.get(buyer_id, 0.0) + funded
            assert total <= cap + 1e-6, (
                f"{pid} holds {total:.2f} lakh against {buyer_id}, cap {cap:.2f}")


def test_the_demo_match_is_unchanged_by_book_wide_clearing():
    """Clearing INV001 alone must still be the demo's answer."""
    match = client.post("/api/clear", json={"invoice_ids": ["INV001"]}).json()["matches"][0]
    assert match["match_id"] == "MCH001"
    assert match["total_advance_lakh"] == 9.00
    assert match["allocations"][0]["provider_id"] == "PRV003"
    assert match["allocations"][0]["amount_lakh"] == 6.00


def test_every_match_allocates_exactly_what_it_claims():
    market = client.get("/api/market").json()
    ids = [i["invoice_id"] for i in market["invoices"]]
    for match in client.post("/api/clear", json={"invoice_ids": ids}).json()["matches"]:
        total = round(sum(a["amount_lakh"] for a in match["allocations"]), 2)
        assert total == match["total_advance_lakh"], match["match_id"]


def test_every_score_stays_in_range_and_carries_a_reason():
    body = client.post("/api/offers", json={"invoice_id": "INV001"}).json()
    for offer in body["offers"]:
        assert 0.0 <= offer["fit_score"] <= 1.0
        assert math.isfinite(offer["rate_annual"])
        assert offer["reason_text"]
        if not offer["feasible"]:
            assert offer["rejection_reason"]


# ---------------------------------------------------------------------------
# Response budgets — catastrophic regressions only, so this never flakes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,payload,budget_ms", [
    ("/api/assess", {"invoice_id": "INV001"}, 1000),
    ("/api/offers", {"invoice_id": "INV001"}, 1000),
    ("/api/clear", {"invoice_ids": ["INV001"]}, 1000),
    ("/api/settle", {"match_id": "MCH001", "outcome": "late", "days_late": 5}, 3000),
])
def test_the_demo_path_stays_responsive(path, payload, budget_ms):
    """Generous on purpose — this catches an accidental O(n^2), not a slow laptop.

    Measured on this machine: assess 9ms, offers 10ms, clear 14ms, settle 249ms.
    /api/settle is the outlier because before/after is two full evaluations of
    every invoice on the buyer, which SCHEMA.md §5.6 requires and forbids
    optimising away.
    """
    client.post(path, json=payload)  # warm
    start = time.perf_counter()
    response = client.post(path, json=payload)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert response.status_code == 200
    assert elapsed_ms < budget_ms, f"{path} took {elapsed_ms:.0f}ms"


def test_health_reports_what_it_actually_loaded():
    """Ten seconds to write; tells you instantly which dataset is live."""
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["invoices"] > 0 and body["providers"] > 0
    assert body["market"]
