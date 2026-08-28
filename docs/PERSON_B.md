# PERSON_B.md — Market Simulator, API & Integration

**Person B / Person 2 — "Build the market that decides who wins."**

Read `AGENTS.md` and `SCHEMA.md` before starting. This file assumes both.

---

## 1. What you own

| Path | Yours |
|---|---|
| `market/` | Everything |
| `api/` | Everything |
| `tests/market/`, `tests/api/` | Everything |

Your reviewer for every PR is **Person A**.

You also **review every PR touching `engine/` and `data/`** — even when Person C wrote it.

You own two things that are easy to conflate, so keep them separate in your head:

- **`market/`** is the simulator — provider agents that bid, clearing that allocates, settlement that closes, learning that reallocates. It is the intellectually deepest part of the project
- **`api/`** is a thin, boring, stateless HTTP shell over `engine/` and `market/`. It should contain almost no logic

You are also the bridge:

```
Person A's engine  ──▶  your market  ──▶  your API  ──▶  Person C's frontend
```

Which means two responsibilities beyond writing code:

1. **You own the seam.** When A's valuations don't fit what the market or C needs, it surfaces in your layer first. Raise it rather than papering over it in a transform
2. **You own integration timing.** Phase 2 happens because you make it happen, not because the other two are ready

---

## 2. Stateless — the rule that shapes everything

The server holds **no** session state. See `AGENTS.md` §3.4.

- No scenario storage, no session IDs, no mutation between requests
- The client sends the full `MarketScenario` with every call and gets a complete result
- Settlement events arrive in the request body, not from server memory
- A page refresh or a backend restart mid-demo loses nothing the client can't immediately re-send
- Caching only as a pure function of the request body

**Why it matters more here than usual:** the demo walks a market through offers → match → funding → settlement → learning. If that progression lived on the server, step 8 would depend on steps 1–7 having run cleanly in order. Stateless means any step can be re-entered directly, which is exactly what you want when a judge asks "can you show that again?"

---

## 3. The market simulator — `market/`

This is your deep work. Budget accordingly: it is larger than the API by a wide margin.

### 3.1 Provider agents — `market/agents.py`

Each provider is an autonomous agent that independently decides whether to bid and on what terms. Constants come from `engine/config.py` — there is exactly one config file (`AGENTS.md` §7).

```python
def generate_offer(
    provider: dict,
    invoice: dict,
    assessment: dict,
    eligibility: dict,
    expected_competitors: int,
) -> dict | None:
    """Return an Offer, or None if this provider declines to bid."""
```

**Return `None` only when `eligibility.eligible` is `False`.** An eligible-but-capacity-limited provider still bids — for `max_fundable_lakh`, not the full amount. That partial bid is what produces syndication.

**Base rate:**

```
expected_loss   = pd * (1 - RECOVERY_RATE)              # RECOVERY_RATE = 0.40
capital_charge  = CAPITAL_CHARGE_RATE * pd_upper        # 0.30
required_rate   = provider.cost_of_funds
                + expected_loss
                + capital_charge
                + provider.target_margin
```

**Winner's-curse shading — do not skip this.**

In an auction, the winner is disproportionately whoever most *underestimated* the risk. A market that ignores this quietly destroys its own lenders, which is a documented failure of naive lending auctions. Each agent therefore adds a shade proportional to uncertainty and to how many rivals it expects:

```
shade    = SHADE_K * assessment.risk.uncertainty * log(1 + expected_competitors)
bid_rate = max(required_rate + shade, provider.cost_of_funds)   # never below cost of funds
```

`SHADE_K = 8.0`. The `max()` floor is a hard invariant — an agent bidding below its own cost of funds is a bug, and `tests/market/` asserts it.

**Then differentiate on non-price terms by provider type.** This is what produces four genuinely different offers rather than four rates 30 basis points apart:

| Type | Advance | Settlement | Fees | Structure | Rate posture |
|---|---|---|---|---|---|
| `bank` | Modest (0.75–0.82) | Slow (2–4 d) | Moderate | bullet | Competitive |
| `nbfc` | Low (0.68–0.75) | Medium (1–2 d) | High | bullet | **Lowest headline** |
| `fund` | High (0.85–0.92) | Fast (0–1 d) | Low | bullet | Mid, priced for the advance |
| `fintech` | Modest (0.72–0.78) | Fast (0–1 d) | Lowest | instalment | Highest |

Each agent's offer must respect its own limits:

- `days_to_settle >= provider.speed_capability_days`
- `repayment_structure in provider.preferred_structures`
- `amount_committed_lakh <= eligibility.max_fundable_lakh`
- `rate_annual >= provider.cost_of_funds`

**The demo's four offers (`DEMO_SCENARIO.md` §4) are the acceptance test for this module.** Your agents must produce those exact terms on `INV001`. Getting there may need per-type constants tuned in `config.py` — that is expected and fine. Hardcoding the demo offers is not.

**Allocation policy across the invoice stream.** Each agent maintains a running estimate per segment (`sector/grade/tenor-band`) and prefers opportunities with the best risk-adjusted return per rupee of budget:

```
priority = (expected_return - expected_loss) / amount_committed_lakh
         + EXPLORATION_BONUS / sqrt(1 + times_segment_seen)
```

The visible consequence, which is excellent in a demo: **as a provider's liquidity drains, it bids more selectively and prices higher.** That is a live market responding to changing capital availability, which is an explicit problem-statement requirement rather than a nice-to-have.

### 3.2 Clearing — `market/clearing.py`

**Deferred acceptance, not greedy selection.**

Greedy "highest score wins" produces unstable outcomes when several invoices compete for the same provider's capital: a provider's budget gets committed to invoice A when it would have preferred invoice B, and B's supplier would have preferred that provider. Deferred acceptance produces a **stable** match — no supplier/provider pair would both rather defect.

```
1. Each invoice proposes to its highest-fit_score feasible offer not yet rejected
2. Each provider tentatively holds the proposals it most prefers by risk-adjusted
   return, subject to remaining capacity, and rejects the rest
3. Rejected invoices propose to their next-best offer
4. Repeat until no invoice has an unanswered proposal, or MAX_ROUNDS is hit
```

**Non-negotiable implementation details:**

- **Ties break by ID ascending**, both sides, always. Required for determinism (`AGENTS.md` §3.1)
- **Sorted iteration** over invoices and providers, always
- Deferred acceptance provably terminates; `MAX_ROUNDS` (50) is a safety net, not a design assumption. Hitting it is a bug — set `stable: false` and let the test catch it
- Never allocate a provider beyond `available_liquidity_lakh` or past a concentration limit. Re-check on every tentative hold, because holds accumulate within a round

**Syndication.** When the top offer's `amount_committed_lakh` is less than the supplier's requested advance, fill the remainder from the next-best feasible offers:

```
remaining = advance_needed
for offer in ranked_feasible_offers:
    take = min(offer.amount_committed_lakh, remaining)
    if take > 0: allocations.append((offer.provider_id, take, offer.offer_id))
    remaining -= take
    if remaining <= EPSILON: break

if remaining > EPSILON:
    → unmatched, with a reason naming the shortfall
```

Then compute the blended terms:

```
blended_rate_annual = Σ(alloc.amount × offer.rate_annual) / Σ(alloc.amount)
blended_cost_lakh   = Σ(each allocation's cost at its own terms)
```

**`Match.allocations[].amount_lakh` must sum to `total_advance_lakh` exactly** — `schema.json` enforces it, and floating-point drift will bite you here. Round each allocation at 2dp and give any residual paise to the largest allocation.

Syndication is not a nice-to-have. Thin liquidity is the historical killer of invoice marketplaces — single-invoice auction platforms have closed for exactly this reason. Being able to split a deal across providers is the answer, and it is also demo step 7.

### 3.3 Settlement — `market/settlement.py`

A state machine. Legal transitions are in `SCHEMA.md` §4.6 and **no others are permitted.**

```python
def advance(match: dict, event: dict, market: dict) -> dict:
    """Transition a match. Raises IllegalTransitionError on a bad path."""
```

- `matched → funded` requires funding conditions met; otherwise `matched → cancelled`
- `funded → settled | late | defaulted`
- `late → settled` (recovered) or `late → defaulted`
- **Nothing transitions out of `settled`, `defaulted` or `cancelled`**

Raise `IllegalTransitionError` for anything else so the API can map it to a 400 (`SCHEMA.md` §5.7).

**`matched` is not `funded`.** The problem statement is explicit that selecting an offer does not complete a financing. Enforce it in the state machine rather than trusting the caller — this is one of the few places where being strict is visibly part of the product.

### 3.4 Learning — `market/learning.py`

```python
def apply_outcome(match: dict, event: dict, market: dict) -> tuple[dict, dict]:
    """Returns (updated_market, LearningDelta). Never mutates the input market."""
```

Five things happen, in this order:

1. **Update the buyer.** `avg_payment_delay_days` moves toward the observed delay by `DELAY_LEARNING_RATE` (0.30); `payment_delay_trend` records the change
2. **Reprice affected invoices.** Every other open invoice on that buyer gets re-assessed through A's `assess()`. Record only invoices whose `pd` actually moved
3. **Return or consume liquidity.** `settled` returns the committed amount; `defaulted` consumes it; `late` returns nothing yet
4. **Adjust provider bid policy.** The segment estimate moves by `SEGMENT_LEARNING_RATE` (0.20), producing a `rate_adjustment` in decimal fractions
5. **Compose `summary_text`** — template-generated, no LLM

**Deep-copy the market first.** `apply_outcome` returning a new market rather than mutating one is what keeps the API stateless.

The `LearningDelta` (`SCHEMA.md` §4.7) is the entire payload for demo step 8. Make `repriced_invoices` and `provider_bid_adjustments` accurate — those two arrays are what the judge actually sees.

### 3.5 Your public surface

```python
# market/simulate.py

def generate_offers(invoice_id, market, assessment, scenario) -> list[dict]
def clear(invoice_ids, market, scenario) -> dict          # ClearingResult
def settle(match_id, outcome, days_late, market, scenario) -> dict   # before/after/delta
```

Pure and deterministic, same rules as A's engine. Never mutate `market`.

---

## 4. The five endpoints

Full request and response shapes are in `SCHEMA.md` §5. Validate everything against `schema.json`.

Keep `api/` thin. If an endpoint body is more than about fifteen lines, logic has leaked out of `market/` and should move back.

### 4.1 `GET /api/market`

Raw market for initial render. No scoring — it should be fast, because C blocks on it before anything appears.

```python
@app.get("/api/market", response_model=MarketResponse)
def get_market():
    m = load_market()          # cached at startup
    return {"meta": m["meta"], "suppliers": m["suppliers"],
            "buyers": m["buyers"], "invoices": m["invoices"], "providers": m["providers"]}
```

Loading `market.json` once at startup is fine — that is not session state.

### 4.2 `POST /api/assess`

Verification, risk and eligibility for one invoice. No offers.

```python
@app.post("/api/assess", response_model=Assessment)
def assess(req: AssessRequest):
    return engine.assess(req.invoice_id, load_market(), to_scenario(req.scenario))
```

Kept separate from `/api/offers` deliberately — the demo reveals verification and eligibility *before* offers appear, and separate calls let C stage that without artificially holding a response.

### 4.3 `POST /api/offers`

Generate and score competing offers.

```python
@app.post("/api/offers", response_model=OffersResponse)
def offers(req: OffersRequest):
    market = load_market()
    scenario = to_scenario(req.scenario)
    assessment = engine.assess(req.invoice_id, market, scenario)
    raw = market_sim.generate_offers(req.invoice_id, market, assessment, scenario)
    prefs = resolve_preferences(market, req.invoice_id, scenario)
    return {"invoice_id": req.invoice_id, "assessment": assessment,
            **engine.score_offers(raw, assessment, prefs)}
```

**Always return `naive_ranking`, even when `naive_mode` is false.** C toggles the counterfactual with zero latency because both rankings are already in hand. This is the single highest-value line in your API.

### 4.4 `POST /api/clear`

Stable matching across invoices, including syndication.

Returns `provider_utilisation` so C can animate liquidity bars draining. Set `summary.stable` honestly — if deferred acceptance hit `MAX_ROUNDS`, say so rather than pretending.

### 4.5 `POST /api/settle`

Before, after, and delta. This drives the closing demo beat, so it is the endpoint most worth getting right.

```python
@app.post("/api/settle", response_model=SettleResponse)
def settle(req: SettleRequest):
    market = load_market()
    before = snapshot(market, req.match_id)
    after_market, delta = market_sim.settle(req.match_id, req.outcome, req.days_late,
                                            market, to_scenario(req.scenario))
    return {"before": before, "after": snapshot(after_market, req.match_id), "delta": delta}
```

**Two full evaluations per request is correct.** Do not optimise it into one. The comparison is the product.

---

## 5. Errors

| Status | When | Body |
|---|---|---|
| 400 | Unknown ID | `{"error": "unknown_entity", "detail": "INV999 not in market", "entity_id": "INV999"}` |
| 400 | Weights don't sum to 1.0 | `{"error": "invalid_weights", "detail": "Weights sum to 0.87, expected 1.0"}` |
| 400 | Illegal settlement transition | `{"error": "illegal_transition", "detail": "Cannot settle a match in state 'matched'; fund it first"}` |
| 422 | Malformed body | pydantic output |
| 500 | Engine or market raised unexpectedly | `{"error": "engine_failure", "detail": "<message>"}` |

**Rules:**

- Never 500 for a bad request. A typo'd ID is a 400
- Never 200 with an error inside
- Catch `UnknownEntityError`, `InvalidWeightsError` and `IllegalTransitionError` and map each to a 400 naming the offending value
- The `detail` field is read by a human under time pressure. `"Cannot settle a match in state 'matched'; fund it first"` is useful; `"KeyError"` is not

---

## 6. Config

```python
# api/config.py
MARKET_PATH  = os.getenv("FITFUSE_MARKET", "data/mock/market.json")
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]
```

**One environment variable is the entire dataset switch.** If a richer generated market lands later, you change a path. Nothing else in `api/` or `web/` moves.

If that turns out to be false, the contract was wrong — fix the contract, not the endpoint.

---

## 7. Tests

### `tests/market/`

| Test | Asserts |
|---|---|
| `test_agents_differentiate` | The four demo providers produce four offers differing on more than rate |
| `test_never_below_cost` | No agent ever bids below its `cost_of_funds`, at any uncertainty |
| `test_shading_increases` | Higher `uncertainty` produces a higher bid rate, all else equal |
| `test_capacity_respected` | No allocation exceeds `max_fundable_lakh`, liquidity, or any concentration limit |
| `test_clearing_terminates` | Deferred acceptance converges under `MAX_ROUNDS` on the demo market |
| `test_clearing_stable` | No supplier/provider pair would both prefer to defect from the result |
| `test_syndication_sums` | `allocations` sum exactly to `total_advance_lakh` |
| `test_demo_match` | Clearing on `INV001` reproduces the fixture's `expected_match` |
| `test_illegal_transition` | `settled → funded` raises `IllegalTransitionError` |
| `test_learning_delta` | Settling `INV001` late reproduces `expected_after_learning` |
| `test_no_market_mutation` | The input market dict is unchanged after `clear` and `settle` |
| `test_determinism` | Two identical `clear` calls return byte-identical results |

### `tests/api/`

| Test | Asserts |
|---|---|
| `test_market_shape` | `/api/market` validates against `MarketResponse` |
| `test_assess_shape` | `/api/assess` validates against `Assessment` |
| `test_offers_shape` | `/api/offers` validates, and `naive_ranking` is present even when `naive_mode` is false |
| `test_clear_shape` | `/api/clear` validates against `ClearingResponse` |
| `test_settle_shape` | `/api/settle` validates against `SettleResponse` |
| `test_unknown_id_400` | Bad ID returns 400, not 500, and names the ID |
| `test_bad_weights_400` | Weights summing to 0.87 return 400 |
| `test_malformed_422` | Garbage body returns 422 |
| `test_stateless` | Two identical requests return identical responses; a settle call does not affect a later assess call |
| `test_fit_beats_rate` | `/api/offers` on `INV001` returns `fit_beats_rate: true` |

`test_stateless` catches the failure mode that would hurt most on stage. `test_fit_beats_rate` is the one-line assertion that the product still makes its point.

---

## 8. Deployment

Local is enough. Do not build a pipeline.

```bash
uvicorn api.main:app --reload --port 8000
```

For the demo, run **without** `--reload` — the file watcher can restart mid-presentation.

Two things worth having:

- **`GET /health`** returning `{"status": "ok", "market": "<path>", "invoices": <count>, "providers": <count>}`. Ten seconds to write, tells you instantly whether the backend is up and which dataset it loaded
- **A `make demo` target** (or a shell script) that starts the API and the frontend together. Removes one class of stage error

---

## 9. Phases

**Phase 0 — Contract freeze**
- Agree `SCHEMA.md` and `schema.json` with A and C
- Write `api/models.py` — pydantic models mirroring the schema
- **Stub all five endpoints returning static valid responses**
- **Exit:** C can develop against your running API before A's engine exists

Stubbing early is the single most useful thing you do. It unblocks C immediately, and it costs an hour.

**Phase 1 — Independent build**
- `agents.py` producing differentiated offers; `clearing.py` with deferred acceptance
- Real endpoint logic against A's engine, or a stub scorer if the engine is mid-change
- Error handling
- **Exit:** all five endpoints return contract-valid responses; agents produce four visibly different offers

**Phase 2 — Integration**
- **You drive this.** Wire A's real engine and C's real frontend together
- Fix contract mismatches at the source, not with adapters
- **Exit:** one invoice flows end to end, slider included

**Phase 3 — Demo path**
- `settlement.py`, `learning.py`
- `test_demo_match` and `test_learning_delta` pass
- `/health`, `make demo`
- **Exit:** the eight-step demo runs without a restart

**Phase 4 — Hardening**
- Error paths, response times, rehearsal

---

## 10. Traps specific to your track

- **Accidental state.** A module-level dict caching scenario results is state. Cache only pure functions of the request body
- **Greedy allocation instead of deferred acceptance.** Greedy is easier and produces unstable, indefensible matches. The stability argument is one of your strongest answers in Q&A — don't give it up for twenty lines of code
- **Forgetting to re-check capacity within a clearing round.** Tentative holds accumulate; checking only at round start over-allocates a provider
- **Agents that differ only by rate.** Four offers at 8.2/8.4/8.6/8.8 with identical terms makes the entire product pointless. Differentiation across advance, speed, fees and structure is the whole thesis
- **Skipping winner's-curse shading.** It is four lines, and it is one of the few genuinely defensible pieces of mechanism design in the project
- **Letting an agent bid below its cost of funds.** Instantly spotted by anyone with finance background
- **Floating-point drift in syndication.** Allocations must sum exactly. Round at 2dp, give the residual to the largest allocation
- **Adapting around a contract mismatch.** If A's output doesn't fit C's need, fixing it in your layer hides the problem and leaves two people with different mental models. Change the contract instead
- **Optimising `/api/settle` into one evaluation.** The before/after comparison is the product
- **Letting `--reload` run during the demo.** Restarts mid-presentation
- **Adding a database.** Explicitly out of scope — `AGENTS.md` §1.2
- **Waiting for A's engine before stubbing.** C is blocked on you, not on A
