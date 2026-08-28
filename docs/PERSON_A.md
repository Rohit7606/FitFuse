# PERSON_A.md — Valuation Engine & Risk Logic

**Person A / Person 1 — "Build the brain that decides what an offer is worth."**

Read `AGENTS.md` and `SCHEMA.md` before starting. This file assumes both.

---

## 1. What you own

| Path | Yours |
|---|---|
| `engine/` | Everything |
| `data/` | Everything |
| `tests/engine/` | Everything |

Your reviewer for every PR is **Person B**.

You own the valuation layer:

- Invoice verification — IRN check, duplicate detection, field-confidence tagging
- Risk scoring — default probability with an honest uncertainty band
- Eligibility — which providers may see an opportunity, how much each can fund, and **why the others cannot**
- The whole-offer value score — the centrepiece of the product
- Reason generation — every score explains itself in plain English
- **The mock market generator** — everyone's day-one dependency

**What you do not own:** who wins. You produce valuations; Person B's `market/` decides allocations. If you find yourself writing code that picks a winner, stop — that belongs in `market/clearing.py`.

`engine/mockgen.py` was put on your track deliberately. The generator *is* the contract made concrete, and building it forces you to confront every field before anyone depends on it.

---

## 2. Your public surface

Person B calls exactly these. Keep the surface small.

```python
# engine/assess.py

def assess(
    invoice_id: str,
    market: dict,
    scenario: Scenario | None = None,
) -> dict:
    """Verify an invoice, score its risk, and determine provider eligibility.

    Args:
        invoice_id: must exist in market["invoices"]
        market:     MarketInput dict, validated against schema.json
        scenario:   preference and liquidity overrides; None means baseline

    Returns:
        Assessment dict, validated against schema.json

    Pure. Deterministic. No I/O, no globals, no mutation of the input.
    """


def score_offers(
    offers: list[dict],
    assessment: dict,
    preferences: dict,
) -> dict:
    """Score and rank competing offers for one supplier.

    Returns:
        { "offers": [ScoredOffer...], "ranking": [...], "naive_ranking": [...], "summary": {...} }

    Infeasible offers are returned with feasible=false, never dropped.
    """
```

**Contract you must honour:**

- Same input → byte-identical output, always
- Never mutate `market` or `offers`. Deep-copy first
- Never read files or the clock inside these calls
- Raise `UnknownEntityError` (defined in `engine/assess.py`) for a bad ID so B can map it to a 400
- Raise `InvalidWeightsError` when preference weights don't sum to 1.0

Also expose the scenario type:

```python
@dataclass(frozen=True)
class Scenario:
    preference_overrides: tuple[PreferenceOverride, ...] = ()
    liquidity_overrides: tuple[LiquidityOverride, ...] = ()
    naive_mode: bool = False
```

Frozen and tuple-based so it cannot be mutated mid-scoring.

---

## 3. The algorithm

All constants live in `engine/config.py` with a one-line comment each. No magic numbers in the modules.

### 3.1 Verification — `engine/verify.py`

Produces a `Verification` object (`SCHEMA.md` §4.2). Runs before anything else. **A rejected invoice produces no risk score and no offers.**

**Three checks, in order:**

**1. IRN validity.** In the mock, an IRN is valid if it is a non-null 64-character hex string. `null` fails.

```
if invoice["irn"] is None:        → rejected, "not registered under GST e-invoicing"
if not is_hex64(invoice["irn"]):  → rejected, "invoice reference number is malformed"
```

**2. Duplicate detection.** Compare `document_hash` against every other invoice in the market whose `status` is `"financed"` or `"settled"`, **and** against other `"open"` invoices from a different supplier.

```
matches = [i for i in sorted_invoices
           if i["document_hash"] == invoice["document_hash"]
           and i["invoice_id"] != invoice_id]
```

If any match exists → `duplicate_detected: true`, `duplicate_of` set to the **lexicographically smallest** matching ID (deterministic), status `rejected`.

This is the mechanism used by real trade-finance registries: fingerprint the document, check the fingerprint, never share the document. Say that if asked — it is a real technique, not something we invented.

**3. Field-confidence tagging.** Copy `field_confidence` from the invoice, then tag anything the invoice didn't:

| Field | Rule |
|---|---|
| `amount_lakh`, `tenor_days` | `verified` when IRN is valid — these are on the registered document |
| `buyer_gstin` | `verified` when the buyer exists in `market["buyers"]` |
| `delivery_confirmed` | `verified` if `true`/`false`; **`unknown` if `null`** |
| `supplier_prior_defaults` | `verified` if an integer; `unknown` if `null` |

`unknown_field_count` is the count of `unknown` tags. It feeds the uncertainty band directly.

**Be honest about what an IRN proves.** It proves the invoice was reported to the GST system. It does **not** prove goods were delivered. That is why `delivery_confirmed` stays `unknown` and widens the band rather than being quietly assumed. If a judge asks how you verify invoices, this distinction is the answer that earns credibility.

### 3.2 Risk — `engine/risk.py`

Put this at the top of the file:

```python
# Credit risk sits primarily with the BUYER, not the supplier.
# The financier pays the supplier now and collects from the buyer later.
# See SCHEMA.md §2.6.
```

**A transparent scorecard, not a trained model** — see `AGENTS.md` §1.5.

```
logit = B0
      + B_GRADE      * grade_penalty(buyer.credit_grade)
      + B_DELAY      * min(buyer.avg_payment_delay_days / DELAY_REF_DAYS, 1.0)
      + B_TREND      * clamp(buyer.payment_delay_trend / TREND_REF_DAYS, 0.0, 1.0)
      + B_TENOR      * min(invoice.tenor_days / TENOR_REF_DAYS, 1.0)
      + B_SIZE       * size_anomaly(invoice.amount_lakh, supplier.annual_revenue_lakh)
      + B_THIN       * (1.0 - supplier.data_completeness)
      + B_HISTORY    * default_rate(supplier)
      + B_DISPUTE    * min(buyer.disputes_last_year / DISPUTE_REF, 1.0)

pd = clamp(1 / (1 + exp(-logit)), PD_FLOOR, PD_CEILING)
```

Reference constants (`config.py`): `DELAY_REF_DAYS = 30`, `TREND_REF_DAYS = 10`, `TENOR_REF_DAYS = 120`, `DISPUTE_REF = 3`, `PD_FLOOR = 0.002`, `PD_CEILING = 0.400`.

`grade_penalty` is a lookup, not a formula — `AAA: 0.0, AA: 0.15, A: 0.35, BBB: 0.60, BB: 0.85, B: 1.10, C: 1.50`.

`size_anomaly` flags an invoice that is unusually large for the supplier:

```
ratio = amount_lakh / max(annual_revenue_lakh / 12, EPSILON)   # vs one month of revenue
size_anomaly = clamp((ratio - 1.0) / 3.0, 0.0, 1.0)            # 1 month = 0, 4 months = 1
```

**`default_rate(supplier)` must respect null-vs-zero** (`AGENTS.md` §3.6):

| `prior_defaults` | `prior_financings` | Behaviour |
|---|---|---|
| `0` | `> 0` | `0.0` — a real clean record, and it should help |
| `null` | anything | `NO_HISTORY_PRIOR` (0.02) — absence is not a clean record |
| `n > 0` | `m > 0` | `n / m` |
| anything | `0` | `NO_HISTORY_PRIOR` — no track record either way |

**The uncertainty band — this is your differentiator:**

```
uncertainty = BASE_UNCERTAINTY                                    # 0.003
            + UNKNOWN_FIELD_PENALTY * verification.unknown_field_count   # 0.002 each
            + INFERRED_FIELD_PENALTY * inferred_field_count              # 0.001 each
            + THIN_FILE_PENALTY * (1.0 - supplier.data_completeness)     # 0.006
            + NEW_SUPPLIER_PENALTY if years_operating < 3 else 0.0       # 0.004

pd_lower = clamp(pd - uncertainty, PD_FLOOR, 1.0)
pd_upper = clamp(pd + uncertainty, 0.0, PD_CEILING)
```

**Band on `pd_upper`, never on `pd`** (`SCHEMA.md` §4.8). A provider with a tight risk appetite should be repelled by uncertainty itself, not only by the point estimate. This is how the model implements "account for incomplete information" rather than just mentioning it.

**Edge cases you must handle explicitly:**

| Case | Behaviour |
|---|---|
| Buyer not in `market["buyers"]` | Raise `UnknownEntityError`. Never guess a grade |
| `delivery_confirmed` is `null` | `unknown` tag, band widens. **Do not treat as `false`** |
| `payment_delay_trend` is negative | Buyer is improving. Allowed to reduce the logit |
| `data_completeness` is `1.0` | Band is still at least `BASE_UNCERTAINTY`. Never claim zero uncertainty |

### 3.3 Eligibility — `engine/eligibility.py`

For **every** provider, produce a `ProviderEligibility` (`SCHEMA.md` §4.4) — including the ineligible ones, with reasons.

Checks run in this fixed order, and **the first failure is the `binding_constraint`:**

```
1. min_ticket      advance_needed >= provider.min_ticket_lakh
2. max_ticket      advance_needed <= provider.max_ticket_lakh
3. liquidity       provider.available_liquidity_lakh > 0
4. risk_appetite   risk.pd_upper <= provider.risk_appetite
5. sector_limit    headroom_sector > 0
6. buyer_limit     headroom_buyer > 0
7. target_return   max_feasible_return(pd, provider) >= provider.target_return
```

where

```
advance_needed  = invoice.amount_lakh * supplier.preferences.min_advance_rate
headroom_sector = sector_limits[sector] * total_portfolio_lakh - current_exposure.by_sector[sector]
headroom_buyer  = buyer_limit           * total_portfolio_lakh - current_exposure.by_buyer[buyer_id]
```

**`max_fundable_lakh` is the field that makes syndication possible:**

```
max_fundable_lakh = round(min(
    provider.available_liquidity_lakh,
    provider.max_ticket_lakh,
    headroom_sector,
    headroom_buyer,
), 2)
```

A provider can be **eligible but capacity-limited** — that is exactly Kestrel in the demo, and it is the most interesting state in the system. Do not collapse it into a binary.

**Exclusion reasons must name the provider and the number.** Not `"ticket size"` but:

> `"Invoice of ₹10.00 lakh exceeds Coastal Cooperative Bank's ₹8.00 lakh maximum ticket size."`

A judge reading a greyed-out provider row should need no further explanation. This text is a large part of why the product looks like a real market rather than a filter.

### 3.4 Whole-offer scoring — `engine/scoring.py`

**This is the centrepiece. Build it first, tune it last.**

**Step 1 — hard constraints, before any scoring.**

```
if offer.advance_rate  < prefs.min_advance_rate:  feasible = false
if offer.days_to_settle > prefs.max_days_to_cash: feasible = false
```

Infeasible offers get `fit_score = 0.0`, a `rejection_reason`, and are **returned, not dropped** (`SCHEMA.md` §4.5). They rank last.

**Hard constraints are not preferences.** An offer advancing 60% to a supplier who needs 70% is not "a bit worse" — it is unusable. Down-scoring instead of rejecting is the most likely scoring bug in this project.

**Step 2 — all-in cost, in rupees.**

```
financing_cost = amount_lakh * advance_rate * rate_annual * (tenor_days / 365)
fee_cost       = amount_lakh * fee_percent + fee_flat_lakh
total_cost_lakh = financing_cost + fee_cost
```

**The headline rate is not the cost.** A lower rate on a smaller advance can cost more in rupees than a higher rate on a larger one — that is `OFR002` vs `OFR003` in `DEMO_SCENARIO.md` §4, and reproducing it exactly is one of your tests.

**Step 3 — normalise each attribute to 0–1 across the feasible offer set**, where 1 is always best for the supplier.

```
cost_score      = 1 - (total_cost      - min_cost)      / span(cost)
advance_score   =     (advance_rate    - min_adv)       / span(advance)
speed_score     = 1 - (days_to_settle  - min_days)      / span(days)
tenor_score     =     (tenor_days      - min_tenor)     / span(tenor)
fee_score       = 1 - (fee_total       - min_fee)       / span(fee)
structure_score = 1.0 if structure == prefs.preferred_structure else STRUCTURE_MISMATCH  # 0.6
```

where `span(x) = max(x) - min(x)`.

**When `span` is zero** — every offer identical on that attribute — return `1.0` for all, not a divide-by-zero and not `0.0`. All offers being equally fast is not all offers being equally bad.

**Normalise across feasible offers only.** Including a rejected offer's terms stretches the scale and distorts everyone else's scores.

**Step 4 — urgency multiplier, applied to weights before combining.**

```
if prefs.urgent:
    w_speed   *= URGENCY_SPEED_BOOST     # 1.4
    w_advance *= URGENCY_ADVANCE_BOOST   # 1.2
    renormalise all six weights to sum to 1.0
```

This is what makes the score *contextual* rather than a generic weighted average. A supplier with payroll on Friday genuinely values speed more than the same supplier next month.

**Step 5 — combine.**

```
fit_score = w_cost      * cost_score
          + w_advance   * advance_score
          + w_speed     * speed_score
          + w_tenor     * tenor_score
          + w_fees      * fee_score
          + w_structure * structure_score
```

**Weighted sum, deliberately** — unlike a risk model, there is no offer attribute that should zero out the whole offer. Anything that *should* zero it out is a hard constraint and was already handled in step 1. Keep these two mechanisms separate; merging them is how the scoring becomes unexplainable.

**Step 6 — naive ranking, always computed.**

```
naive_ranking = sorted(feasible_offers, key=lambda o: (o.rate_annual, o.offer_id))
```

Returned on every response so C can toggle the counterfactual with no second request (`SCHEMA.md` §5.4).

Set `summary.fit_beats_rate = (ranking[0] != naive_ranking[0])`. That one boolean is the product thesis.

**Ranking ties break by `offer_id` ascending.** Required for determinism.

### 3.5 Reasons — `engine/reasons.py`

Every score carries a non-empty `reason_text`. Template-generated, deterministic, **no LLM** (`AGENTS.md` §1.2).

Build `reason_factors` first, then compose the sentence from the top two or three by weight.

| `kind` | Template |
|---|---|
| `cost_premium` | `"Costs ₹{delta} more than the cheapest rate"` |
| `cost_saving` | `"Costs ₹{delta} less than the lowest-rate offer"` |
| `more_cash` | `"delivers ₹{delta} lakh more cash"` |
| `faster` | `"settles {n} days sooner"` \| `"settles same day"` |
| `advance_floor` | `"Advances only {pct}%, below your {floor}% minimum"` |
| `slow_settle` | `"Settles in {n} days, past your {max}-day requirement"` |
| `structure_mismatch` | `"Repays in instalments rather than a single payment"` |
| `buyer_grade` | `"Buyer rated {grade}"` |
| `unverified` | `"{field} unavailable, so the range is wider"` |

Target outputs:

> "Costs ₹3,100 more than the cheapest rate but delivers ₹2.00 lakh more cash, same day."

> "Advances only 60%, below your 70% minimum."

> "Buyer rated AA with a 4-day average payment delay. Range is widened because delivery confirmation is unavailable."

Factor `weight` values are each contributor's share and **must sum to 1.0** — `schema.json` enforces it.

**Format money for humans.** `₹3,100` and `₹2.00 lakh`, never `0.031` or `3100.0`. A judge should understand why an offer won without asking. Interpretability is what makes this a credible market rather than a number generator.

---

## 4. Mock market generator — `engine/mockgen.py`

**Build this first.** Everyone is blocked until it exists.

```bash
python -m engine.mockgen --seed 42 --out data/mock/market.json
```

**Requirements:**

- ~60 suppliers, ~12 buyers, ~180 invoices, exactly 6 providers
- **The `DEMO_SCENARIO.md` §2 entities placed explicitly first**, with their specified names, terms and relationships, before generating filler
- Deterministic: same seed → byte-identical file. Seed a local `random.Random(seed)`, never the global module
- Output validates against `MarketInput` before writing
- Randomness is permitted **here and nowhere else**

**Plausibility bar — this is not cosmetic.** Fake-looking data is the most likely thing to make judges dismiss the project.

| Property | Requirement |
|---|---|
| Supplier names | Realistic Indian MSME names. **Never `Supplier_12`** |
| Buyer names | Plausible, clearly fictional. **Never a real company** (`DEMO_SCENARIO.md` §10) |
| Revenue distribution | Heavily skewed — a few large suppliers, many tiny |
| Invoice sizes | ₹0.5–₹80 lakh, log-distributed, non-round. `10.00` for `INV001`, `7.35` elsewhere |
| Tenors | 30, 45, 60, 90 days — clustered, as real payment terms are |
| Buyer grades | Skewed to `A`/`AA`. A market of all-`AAA` buyers has no risk to model |
| Provider liquidity | Spread across two orders of magnitude — a cooperative bank and a fund are not the same size |
| Concentration | **Pre-load `current_exposure` so at least two providers are genuinely near a limit.** Otherwise the eligibility filter never bites and the demo has nothing to show |
| Duplicates | Exactly one planted pair — `INV001` / `INV002` |

**`PRV003` Kestrel must be pre-loaded to 94% of its auto-components sector limit.** That single line in the generator is what produces the demo's syndication beat. Getting it wrong makes step 7 vanish.

**Also generate `financing_history`** — 40–60 past outcomes, mostly `settled`, some `late`, a couple `defaulted`. The learning loop needs a starting memory, and a market with no history looks like it was born five minutes ago.

---

## 5. Tests — `tests/engine/`

| Test | Asserts |
|---|---|
| `test_determinism` | `assess` and `score_offers` run twice on the same input give byte-identical JSON |
| `test_schema_valid` | `mockgen` output validates against `MarketInput`; `assess` output against `Assessment` |
| `test_demo_offers` | The four offers in `DEMO_SCENARIO.md` §4 produce exactly the stated `total_cost_lakh` and `fit_score` values |
| `test_demo_ranking` | `expected_ranking` and `expected_naive_ranking` from the fixture both reproduce |
| `test_preset_flip` | `cheapest` preset ranks `OFR004` first; `cash_fastest` ranks `OFR003` first |
| `test_hard_constraints` | An offer below `min_advance_rate` is `feasible: false` with a reason, **and is still returned** |
| `test_duplicate_blocked` | `INV002` verification is `rejected` with `duplicate_of: "INV001"` |
| `test_irn_null_rejected` | A null IRN rejects and produces no risk score |
| `test_uncertainty_widens` | Adding an `unknown` field increases `pd_upper` and never narrows the band |
| `test_null_vs_zero` | `prior_defaults: 0` and `prior_defaults: null` produce different `pd` |
| `test_eligibility_reasons` | Every ineligible provider has a non-empty `exclusion_reason` and a `binding_constraint` |
| `test_max_fundable` | Kestrel's `max_fundable_lakh` is 6.00 on the demo invoice |
| `test_zero_span` | Offers identical on an attribute all score `1.0` on it, no divide-by-zero |
| `test_scores_bounded` | No `fit_score` or `pd` outside [0, 1] on any input |
| `test_no_input_mutation` | The `market` dict is unchanged after `assess` |

`test_demo_offers` and `test_preset_flip` are your safety net. If a tuning change breaks either, that is the system working — retune, or update the fixture deliberately with both others named on the PR.

---

## 6. Phases

**Phase 0 — Contract freeze**
- Agree `SCHEMA.md` and `schema.json` with B and C
- Ship `mockgen.py` and commit `data/mock/market.json`
- Commit `data/fixtures/demo_scenario.json`
- **Exit:** B and C can both work without you

**Phase 1 — Independent build**
- `verify.py`, `risk.py`, `eligibility.py`, `scoring.py`, `reasons.py`
- `assess.py` producing a valid `Assessment`
- **Exit:** `python -m engine.assess data/mock/market.json --invoice INV001` prints a sensible assessment and ranked offers

**Phase 2 — Integration**
- Wire to B's API and market simulator, fix contract mismatches at the source
- **Exit:** one invoice flows end to end, even if numbers are rough

**Phase 3 — Demo path**
- Tune until `test_demo_offers`, `test_demo_ranking` and `test_preset_flip` all pass
- Determinism check green
- **Exit:** the eight-step demo scores correctly every run

**Phase 4 — Hardening**
- Edge cases, error messages, `config.py` comments
- **Be able to explain the fit score in one sentence, out loud, without notes**

---

## 7. Traps specific to your track

- **Scoring the supplier's credit instead of the buyer's.** The buyer pays. Get this backwards and every risk number is wrong in a way that looks plausible (`SCHEMA.md` §2.6)
- **Treating a hard constraint as a heavy weight.** An offer below the advance floor must be infeasible, not merely low-scoring. This is the most likely scoring bug in the project
- **Normalising across infeasible offers.** Stretches the scale and distorts every real offer's score
- **Dropping infeasible offers instead of returning them.** C needs to show why an offer failed
- **Defaulting `delivery_confirmed: null` to `false`.** Unknown is not bad news. It widens the band; it does not condemn the invoice
- **Conflating `prior_defaults: 0` with `null`.** A clean record should help. Silence should not
- **Banding on `pd` instead of `pd_upper`.** Removes the entire point of computing an uncertainty band
- **Divide-by-zero when all offers share an attribute value.** Return 1.0, not a crash and not 0.0
- **Letting `mockgen` produce round numbers.** `25.00` everywhere reads as fake. `24.70` reads as real
- **Forgetting to pre-load `current_exposure`.** Without it no provider is ever capacity-limited, the eligibility filter never bites, and demo step 7 has nothing to show
- **Adding a trained model "because the weights could be learned."** Explicitly out of scope — `AGENTS.md` §1.5
