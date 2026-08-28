# SCHEMA.md — FitFuse Data Contract

**Schema version: 1.1**

This file is the boundary between all three tracks. It has **no single owner** — changes require both other team members to be named on the PR. See `AGENTS.md` §4.3.

---

## 1. The three layers

Data exists in three distinct shapes. Confusing them is the most likely way this project goes wrong, so they are named explicitly.

| Layer | Shape | Produced by | Consumed by | Lives in |
|---|---|---|---|---|
| **Runtime input** | `market.json` | `engine/mockgen.py` | `engine/assess.py`, `market/simulate.py` | `data/mock/` |
| **Assessment** | `Assessment` | `engine/assess.py` | `market/`, then `api/`, then `web/` | in memory, over HTTP |
| **Market result** | `ClearingResult`, `SettlementResult` | `market/simulate.py` | `api/`, then `web/` | in memory, over HTTP |

```
   market.json  ──engine/assess.py──▶  Assessment  ──market/simulate.py──▶  ClearingResult  ──API──▶  UI
   (runtime in)                        (valuation)                          (market outcome)
        ▲
        │
   mockgen.py
  (the day-one path)
```

**The seam that matters:** `engine/` produces valuations and never decides who wins. `market/` decides who wins and never invents a valuation. If a module starts doing both, the split has broken down.

---

## 2. Conventions that apply everywhere

### 2.1 Currency

**All monetary values are ₹ lakh, expressed as floats.** Field names carry a `_lakh` suffix. There are no exceptions and no other units anywhere in the runtime layer.

- A ₹10,00,000 invoice is `10.00`
- A provider holding ₹50 crore is `5000.00`
- A ₹16,836 financing cost is `0.17` (rounded at serialisation)

**Display conversion to crore is a frontend concern only.** Nothing in `engine/`, `market/` or `api/` converts units. See `AGENTS.md` §3.5.

### 2.2 Rates, percentages and time

- **Rates and percentages are decimal fractions.** 8.8% per annum is `0.088`. An 85% advance rate is `0.85`. Never store `8.8` or `85`
- **All annual rates are per annum**, converted to the invoice period at calculation time using `tenor_days / 365`
- **Tenor and settlement speed are integer days.** `days_to_settle: 0` means same-day. Never fractional, never hours

### 2.3 Missing versus zero versus unverified

Three distinct states — see `AGENTS.md` §3.6.

- `null` — the field was not provided
- `0` / `0.0` — the value is explicitly zero
- `field_confidence` — a separate map recording whether a **present** value is `verified`, `inferred`, or `unknown`

```json
"amount_lakh": 10.00,
"field_confidence": {
  "amount_lakh": "verified",
  "buyer_gstin": "verified",
  "delivery_confirmed": "unknown",
  "supplier_prior_defaults": "inferred"
}
```

**Every field named in `field_confidence` must exist on the object.** A confidence tag for a field that isn't there is a bug, and `schema.json` enforces it.

### 2.4 Rounding

Applied at serialisation only, never mid-calculation:

- Monetary fields: 2 decimal places
- Score, rate and probability fields (0–1 range): 4 decimal places
- Percentage fields stored as fractions (`0.85`), not as `85`

### 2.5 Identifiers

| Prefix | Entity | Example |
|---|---|---|
| `INV` | Invoice | `INV001` |
| `SUP` | Supplier | `SUP001` |
| `BUY` | Buyer | `BUY001` |
| `PRV` | Capital provider | `PRV001` |
| `OFR` | Offer | `OFR001` |
| `MCH` | Match | `MCH001` |

- Zero-padded to three digits
- Stable across regenerations of the mock data given the same seed
- Sorted lexicographically wherever iteration order could affect output

### 2.6 Direction — read this carefully

An invoice is money the **buyer owes the supplier**.

```json
{ "supplier_id": "SUP001", "buyer_id": "BUY001" }
```

- **Goods** flowed supplier → buyer, already
- **Money** will flow buyer → supplier, at `due_date`
- **The financier stands in for the buyer temporarily** — it pays the supplier now and collects from the buyer later

**Therefore: credit risk sits primarily with the buyer, not the supplier.** This is the single most counter-intuitive fact in the domain, and getting it backwards makes the risk model score the wrong party. Write it in a comment at the top of `engine/risk.py`.

---

## 3. Runtime input — `market.json`

The complete file:

```json
{
  "meta": { ... },
  "suppliers": [ ... ],
  "buyers": [ ... ],
  "invoices": [ ... ],
  "providers": [ ... ],
  "financing_history": [ ... ]
}
```

### 3.1 `meta`

```json
{
  "schema_version": "1.1",
  "generated_at": "2026-08-28T00:00:00Z",
  "generator": "mockgen",
  "seed": 42,
  "currency_unit": "INR_lakh",
  "supplier_count": 60,
  "buyer_count": 12,
  "invoice_count": 180,
  "provider_count": 6
}
```

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | Must match the version this file declares |
| `generated_at` | ISO 8601 string | Set once at build time. **Never** at score time |
| `generator` | `"mockgen"` | Which path produced this file |
| `seed` | integer | Fixed at `42` for the committed file |
| `currency_unit` | string | Always `"INR_lakh"` |

### 3.2 `suppliers`

```json
{
  "supplier_id": "SUP001",
  "name": "Sharda Auto Components Pvt Ltd",
  "sector": "auto_components",
  "city": "Pune",
  "years_operating": 7,
  "annual_revenue_lakh": 480.00,
  "gstin": "27AABCS1429B1ZQ",
  "prior_financings": 4,
  "prior_defaults": 0,
  "data_completeness": 0.72,
  "preferences": { ...SupplierPreferences... },
  "data_source": "synthetic",
  "field_confidence": { ... }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `supplier_id` | string | yes | `SUP###` |
| `name` | string | yes | Plausible Indian MSME name. **Never `Supplier_12`** |
| `sector` | string | yes | snake_case |
| `years_operating` | integer | yes | Drives the thin-file penalty |
| `annual_revenue_lakh` | float | yes | Used to detect an unusually large invoice |
| `prior_defaults` | integer \| null | yes | **`0` and `null` are different.** See §2.3 |
| `data_completeness` | float | yes | `0.0`–`1.0`. Fraction of risk inputs available. Widens the uncertainty band |
| `preferences` | object | yes | See §3.3 |
| `data_source` | `"synthetic"` | yes | Always synthetic in this project. **Never blur this** |

### 3.3 `SupplierPreferences`

The heart of the product. This is what makes the market a fit auction rather than a price auction.

```json
{
  "preset": "cash_fastest",
  "weights": {
    "cost":      0.15,
    "advance":   0.30,
    "speed":     0.35,
    "tenor":     0.10,
    "fees":      0.05,
    "structure": 0.05
  },
  "min_advance_rate": 0.70,
  "max_days_to_cash": 5,
  "preferred_structure": "bullet",
  "urgent": true
}
```

| Field | Type | Notes |
|---|---|---|
| `preset` | enum \| null | `"cheapest"` \| `"cash_fastest"` \| `"max_cash_now"` \| `"custom"` |
| `weights` | object | Six named floats. **Must sum to `1.0`** (tolerance `0.001`) — `schema.json` enforces it |
| `min_advance_rate` | float \| null | **Hard constraint.** An offer below this is rejected, not down-scored |
| `max_days_to_cash` | integer \| null | **Hard constraint.** Same |
| `preferred_structure` | enum \| null | `"bullet"` \| `"instalment"`. A *soft* preference, unlike the two above |
| `urgent` | boolean | Applies the urgency multiplier — see `docs/PERSON_A.md` §3.4 |

**Hard constraints are not preferences.** An offer violating `min_advance_rate` never appears in the ranking, however good its score would have been. Conflating the two is the most likely scoring bug in this project.

### 3.4 `buyers`

```json
{
  "buyer_id": "BUY001",
  "name": "Vireon Motors India Ltd",
  "sector": "automotive_oem",
  "credit_grade": "AA",
  "avg_payment_delay_days": 4,
  "payment_delay_trend": 0.0,
  "disputes_last_year": 0,
  "annual_procurement_lakh": 42000.00,
  "data_source": "synthetic",
  "field_confidence": { ... }
}
```

| Field | Type | Notes |
|---|---|---|
| `credit_grade` | enum | `"AAA"` \| `"AA"` \| `"A"` \| `"BBB"` \| `"BB"` \| `"B"` \| `"C"`. **The primary risk driver** (§2.6) |
| `avg_payment_delay_days` | integer | Historical mean days past due |
| `payment_delay_trend` | float | Change in delay over the last period, in days. **Mutated by the learning loop** — see §4.7 |
| `disputes_last_year` | integer \| null | `0` and `null` differ |

### 3.5 `invoices`

```json
{
  "invoice_id": "INV001",
  "supplier_id": "SUP001",
  "buyer_id": "BUY001",
  "amount_lakh": 10.00,
  "issue_date": "2026-08-20",
  "due_date": "2026-10-19",
  "tenor_days": 60,
  "irn": "a1b2c3d4e5f6...",
  "document_hash": "sha256:9f86d081884c7d65...",
  "goods_description": "hydraulic_seal_kits",
  "delivery_confirmed": null,
  "status": "open",
  "data_source": "synthetic",
  "field_confidence": {
    "amount_lakh": "verified",
    "irn": "verified",
    "delivery_confirmed": "unknown"
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `irn` | string \| null | yes | GST Invoice Reference Number. `null` means unregistered — **fails verification** |
| `document_hash` | string | yes | `sha256:` prefix. Two invoices sharing a hash are a duplicate-financing attempt |
| `tenor_days` | integer | yes | `due_date - issue_date`. Must agree with the dates |
| `delivery_confirmed` | boolean \| null | yes | `null` is expected and common. **Do not default it to `false`** — that would treat unknown as bad news |
| `status` | enum | yes | `"open"` \| `"financed"` \| `"settled"` \| `"rejected"` |

### 3.6 `providers`

```json
{
  "provider_id": "PRV003",
  "name": "Kestrel Credit Fund",
  "type": "fund",
  "available_liquidity_lakh": 600.00,
  "total_portfolio_lakh": 3000.00,
  "risk_appetite": 0.75,
  "min_ticket_lakh": 5.00,
  "max_ticket_lakh": 250.00,
  "cost_of_funds": 0.062,
  "target_margin": 0.0121,
  "target_return": 0.105,
  "sector_limits": { "auto_components": 0.20, "textiles": 0.30 },
  "buyer_limit": 0.15,
  "current_exposure": {
    "by_sector": { "auto_components": 564.00 },
    "by_buyer":  { "BUY001": 210.00 }
  },
  "speed_capability_days": 0,
  "preferred_structures": ["bullet"],
  "data_source": "synthetic"
}
```

| Field | Type | Notes |
|---|---|---|
| `type` | enum | `"bank"` \| `"nbfc"` \| `"fund"` \| `"fintech"` |
| `available_liquidity_lakh` | float | The budget. Depletes on funding, replenishes on settlement |
| `risk_appetite` | float | `0.0`–`1.0`. Maximum `pd_upper` this provider will accept |
| `cost_of_funds` | float | Annual fraction. **The floor** — an agent may never bid below it |
| `target_margin` | float | Annual fraction. The spread this provider adds when **pricing** a bid — the last term of `required_rate` in `PERSON_B.md` §3.4 |
| `target_return` | float | Annual fraction. Required risk-adjusted return, used as an **eligibility screen** (`PERSON_A.md` §3.3 rule 7) |

**`target_margin` and `target_return` are not the same thing and must not be conflated.** `target_return` is a hurdle that decides *whether* a provider looks at a deal at all; `target_margin` is the profit spread it builds into the rate once it has decided to bid. A provider can clear its hurdle and still price thinly, which is exactly what Arcline does in the demo — it takes almost no spread on the rate and earns on fees and a low advance instead.
| `sector_limits` | object | Fraction of `total_portfolio_lakh` allowed per sector |
| `buyer_limit` | float | Fraction of `total_portfolio_lakh` allowed against any single buyer |
| `current_exposure` | object | Absolute ₹ lakh already committed, by sector and by buyer |
| `speed_capability_days` | integer | Fastest this provider can settle. Caps what its agent may offer |

**Concentration check:** a provider may fund `amount` against sector `s` only if
`current_exposure.by_sector[s] + amount <= sector_limits[s] * total_portfolio_lakh`.
The same form applies for buyers. This check is the source of the demo's syndication beat.

### 3.7 `financing_history`

Past outcomes, used by the learning loop as its starting memory.

```json
{
  "invoice_id": "INV044",
  "provider_id": "PRV001",
  "buyer_id": "BUY003",
  "sector": "auto_components",
  "amount_lakh": 7.50,
  "outcome": "settled",
  "days_late": 0
}
```

`outcome` is `"settled"` \| `"late"` \| `"defaulted"`.

---

## 4. Runtime output

### 4.1 `Assessment` — produced by `engine/assess.py`

```json
{
  "invoice_id": "INV001",
  "verification": { ...Verification... },
  "risk": { ...RiskProfile... },
  "eligibility": [ ...ProviderEligibility... ],
  "meta": { "schema_version": "1.1", "engine_version": "1.0" }
}
```

### 4.2 `Verification`

```json
{
  "status": "verified",
  "irn_valid": true,
  "duplicate_detected": false,
  "duplicate_of": null,
  "field_confidence": {
    "amount_lakh": "verified",
    "buyer_gstin": "verified",
    "tenor_days": "verified",
    "delivery_confirmed": "unknown"
  },
  "unknown_field_count": 1,
  "reason_text": "Invoice registered under a valid IRN and not previously financed. Delivery confirmation is unavailable."
}
```

| Field | Type | Notes |
|---|---|---|
| `status` | enum | `"verified"` \| `"rejected"` |
| `duplicate_of` | string \| null | The `invoice_id` this duplicates, when detected |
| `unknown_field_count` | integer | Feeds the uncertainty band directly |
| `reason_text` | string | **Mandatory, never empty.** Template-generated |

**A rejected invoice never proceeds.** No risk score, no eligibility, no offers. `AGENTS.md` §1.1 — opportunities must be based on verified invoices.

### 4.3 `RiskProfile`

```json
{
  "pd": 0.0210,
  "pd_lower": 0.0140,
  "pd_upper": 0.0280,
  "uncertainty": 0.0070,
  "risk_band": "prime",
  "expected_loss_lakh": 0.15,
  "reason_text": "Buyer rated AA with a 4-day average payment delay. Range is widened because delivery confirmation is unavailable.",
  "reason_factors": [
    { "kind": "buyer_grade",       "detail": "Buyer rated AA",                    "weight": 0.45 },
    { "kind": "payment_history",   "detail": "4-day average delay",               "weight": 0.25 },
    { "kind": "tenor",             "detail": "60-day tenor",                      "weight": 0.15 },
    { "kind": "unverified_fields", "detail": "Delivery confirmation unavailable", "weight": 0.15 }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `pd` | float 0–1 | Probability the invoice is not repaid in full |
| `pd_lower`, `pd_upper` | float 0–1 | The honest range. `pd_upper` is what providers screen against |
| `uncertainty` | float | Half-width of the band. Driven by unknown fields and thin files |
| `risk_band` | enum | `"prime"` \| `"standard"` \| `"watch"` \| `"decline"`. Thresholds in §4.8 |
| `reason_factors` | array | `weight` values **must sum to `1.0`** |

**`pd_upper`, not `pd`, is what eligibility screens on.** A provider with a low risk appetite should be repelled by uncertainty, not just by the point estimate. This is how the contract implements "account for incomplete information."

### 4.4 `ProviderEligibility`

One entry per provider — **including the excluded ones.**

```json
{
  "provider_id": "PRV005",
  "eligible": false,
  "max_fundable_lakh": 0.00,
  "exclusion_reason": "Invoice of ₹10.00 lakh exceeds Coastal Cooperative Bank's ₹8.00 lakh maximum ticket size.",
  "binding_constraint": "max_ticket"
}
```

| Field | Type | Notes |
|---|---|---|
| `eligible` | boolean | Passed every check in `docs/PERSON_A.md` §3.3 |
| `max_fundable_lakh` | float | **How much this provider can fund, which may be less than the full advance.** `0.00` when ineligible. This field is what makes syndication possible |
| `exclusion_reason` | string \| null | **Mandatory when `eligible` is `false`.** Plain English, names the provider and the number |
| `binding_constraint` | enum \| null | `"max_ticket"` \| `"min_ticket"` \| `"liquidity"` \| `"risk_appetite"` \| `"sector_limit"` \| `"buyer_limit"` \| `"target_return"` |

**Excluded providers are returned, not filtered out.** The UI shows why a provider is absent — that visible reasoning is a large part of the product's credibility.

### 4.5 `Offer` and `ScoredOffer`

An `Offer` is produced by `market/agents.py`. A `ScoredOffer` is an `Offer` plus the fields `engine/scoring.py` adds.

```json
{
  "offer_id": "OFR003",
  "invoice_id": "INV001",
  "provider_id": "PRV003",
  "rate_annual": 0.0860,
  "advance_rate": 0.90,
  "tenor_days": 60,
  "fee_percent": 0.0040,
  "fee_flat_lakh": 0.00,
  "days_to_settle": 0,
  "repayment_structure": "bullet",
  "amount_committed_lakh": 6.00,
  "advance_amount_lakh": 9.00,

  "total_cost_lakh": 0.17,
  "cash_now_lakh": 9.00,
  "fit_score": 0.8900,
  "component_scores": {
    "cost": 0.72, "advance": 1.00, "speed": 1.00,
    "tenor": 0.50, "fees": 1.00, "structure": 1.00
  },
  "feasible": true,
  "rejection_reason": null,
  "reason_text": "Costs ₹3,100 more than the cheapest rate but delivers ₹2.00 lakh more cash, same day."
}
```

| Field | Type | Notes |
|---|---|---|
| `rate_annual` | float | Decimal fraction, per annum. **Never below the provider's `cost_of_funds`** |
| `advance_rate` | float | Fraction of `amount_lakh` advanced |
| `advance_amount_lakh` | float | `amount_lakh × advance_rate`. Denormalised for the UI |
| `amount_committed_lakh` | float | **What this provider can actually fund.** Less than `advance_amount_lakh` triggers syndication |
| `days_to_settle` | integer | `0` = same day. Must be ≥ the provider's `speed_capability_days` |
| `total_cost_lakh` | float | All-in rupee cost. Formula in `docs/PERSON_A.md` §3.4 |
| `fit_score` | float 0–1 | The whole-offer value score |
| `component_scores` | object | Six normalised sub-scores. Drives the UI breakdown |
| `feasible` | boolean | `false` when a **hard constraint** is violated |
| `rejection_reason` | string \| null | Mandatory when `feasible` is `false` |
| `reason_text` | string | **Mandatory, never empty** |

**Infeasible offers are returned with `feasible: false`, not dropped.** The UI greys them out and shows why — a supplier seeing "this offer was excluded because it only advances 60%, below your 70% floor" understands the market far better than one who sees three offers and no explanation.

### 4.6 `Match` and settlement states

```json
{
  "match_id": "MCH001",
  "invoice_id": "INV001",
  "allocations": [
    { "provider_id": "PRV003", "amount_lakh": 6.00, "offer_id": "OFR003" },
    { "provider_id": "PRV001", "amount_lakh": 3.00, "offer_id": "OFR001" }
  ],
  "syndicated": true,
  "total_advance_lakh": 9.00,
  "blended_rate_annual": 0.0873,
  "blended_cost_lakh": 0.17,
  "supplier_fit_score": 0.8600,
  "state": "matched",
  "days_to_settle": 0,
  "reason_text": "Kestrel Credit Fund funds ₹6.00 lakh at its sector limit; Meridian Bank funds the remaining ₹3.00 lakh."
}
```

**Legal state transitions — no others are permitted:**

```
   matched ──▶ funded ──▶ settled
      │           │
      │           ├──▶ late ──▶ settled
      │           │
      │           └──▶ defaulted
      │
      └──▶ cancelled          (funding conditions not met)
```

| State | Meaning |
|---|---|
| `matched` | An offer combination was selected. **No money has moved** |
| `funded` | Funding conditions satisfied, cash disbursed to the supplier |
| `settled` | The buyer paid. The financing is closed |
| `late` | Past due, not yet written off. Still recoverable |
| `defaulted` | Written off |
| `cancelled` | Match failed before funding |

**`matched` is not `funded`.** The problem statement is explicit that selecting an offer does not complete a financing. The UI must show these as visibly distinct states — see `docs/PERSON_C.md` §5.5.

### 4.7 `LearningDelta`

What changed after an outcome was recorded.

```json
{
  "trigger": { "match_id": "MCH001", "outcome": "late", "days_late": 5 },
  "buyer_updates": [
    { "buyer_id": "BUY001", "avg_payment_delay_before": 4, "avg_payment_delay_after": 5,
      "payment_delay_trend_before": 0.0, "payment_delay_trend_after": 1.0 }
  ],
  "repriced_invoices": [
    { "invoice_id": "INV014", "pd_before": 0.0210, "pd_after": 0.0265,
      "band_before": "prime", "band_after": "standard" }
  ],
  "liquidity_updates": [
    { "provider_id": "PRV003", "available_before_lakh": 594.00, "available_after_lakh": 600.00 }
  ],
  "provider_bid_adjustments": [
    { "provider_id": "PRV003", "segment": "auto_components/AA/60d",
      "rate_adjustment": 0.0015, "reason": "Observed 5-day delay on BUY001" }
  ],
  "summary_text": "Vireon Motors paid 5 days late. Three other invoices on this buyer were repriced and Kestrel Credit Fund raised its rate on this segment by 15 basis points."
}
```

`repriced_invoices` includes only invoices whose `pd` actually moved. `provider_bid_adjustments` is expressed in decimal fractions — `0.0015` is 15 basis points.

### 4.8 Risk band thresholds

Defined once, in `engine/config.py`:

| Band | `pd_upper` |
|---|---|
| `prime` | < 0.025 |
| `standard` | 0.025 – 0.060 |
| `watch` | 0.060 – 0.120 |
| `decline` | ≥ 0.120 |

**Banding is on `pd_upper`, not `pd`.** See §4.3.

---

## 5. API contract

Base URL: `http://localhost:8000`. All responses `application/json`. The API is **stateless** — see `AGENTS.md` §3.4.

### 5.1 The `MarketScenario` object

Sent by the client on every mutating request. The server holds nothing between calls.

```json
{
  "preference_overrides": [
    { "supplier_id": "SUP001", "weights": { "cost": 0.15, "advance": 0.30, "speed": 0.35,
                                            "tenor": 0.10, "fees": 0.05, "structure": 0.05 },
      "urgent": true }
  ],
  "liquidity_overrides": [
    { "provider_id": "PRV003", "available_liquidity_lakh": 600.00 }
  ],
  "settlement_events": [
    { "match_id": "MCH001", "outcome": "late", "days_late": 5 }
  ],
  "naive_mode": false
}
```

All arrays default to empty. An empty scenario means "score the baseline."

| Field | Notes |
|---|---|
| `preference_overrides` | What the sliders send. Weights must still sum to `1.0` |
| `liquidity_overrides` | Lets the demo drain a provider's budget live |
| `settlement_events` | Drives the learning loop without server state |
| `naive_mode` | **The counterfactual switch.** When `true`, offers rank by `rate_annual` ascending and all other terms are ignored. This is what a conventional marketplace would do |

`naive_mode` is not a debug flag. It is the demo's closing argument, and it must be a first-class part of the contract.

### 5.2 `GET /api/market`

Returns the raw market for the initial render. No scoring — it must be fast, because C blocks on it before anything appears.

**Response:** `{ "meta": {...}, "suppliers": [...], "buyers": [...], "invoices": [...], "providers": [...] }`

### 5.3 `POST /api/assess`

Verification, risk and eligibility for one invoice. **No offers.**

**Request:** `{ "invoice_id": "INV001", "scenario": { ...MarketScenario... } }`

**Response:** full `Assessment` (§4.1), including ineligible providers with their reasons.

Kept separate from `/api/offers` deliberately: the demo reveals verification and eligibility *before* offers appear, and separating the calls lets C stage that reveal without holding a response back artificially.

### 5.4 `POST /api/offers`

Generate and score competing offers for one invoice.

**Request:** `{ "invoice_id": "INV001", "scenario": { ...MarketScenario... } }`

**Response:**

```json
{
  "invoice_id": "INV001",
  "assessment": { ...Assessment... },
  "offers": [ ...ScoredOffer... ],
  "ranking": ["OFR003", "OFR001", "OFR004", "OFR002"],
  "naive_ranking": ["OFR002", "OFR003", "OFR001", "OFR004"],
  "summary": {
    "offer_count": 4,
    "feasible_count": 4,
    "best_fit_offer_id": "OFR003",
    "lowest_rate_offer_id": "OFR002",
    "fit_beats_rate": true
  }
}
```

`ranking` is by `fit_score` descending, ties by `offer_id` ascending. `naive_ranking` is by `rate_annual` ascending — **always returned**, so C can toggle the counterfactual instantly without a second request.

`fit_beats_rate` is `true` when the two rankings disagree at position one. That boolean is the entire product thesis, reduced to one field.

### 5.5 `POST /api/clear`

Run clearing across the market and return stable matches, including syndication.

**Request:** `{ "invoice_ids": ["INV001", "INV014"], "scenario": { ...MarketScenario... } }`

**Response:**

```json
{
  "matches": [ ...Match... ],
  "unmatched": [ { "invoice_id": "INV022", "reason": "No provider had capacity within the supplier's advance floor." } ],
  "provider_utilisation": [
    { "provider_id": "PRV003", "committed_lakh": 6.00, "remaining_lakh": 594.00, "utilisation": 0.0100 }
  ],
  "summary": { "matched_count": 2, "syndicated_count": 1, "iterations": 3, "stable": true }
}
```

`stable` asserts deferred acceptance converged. If it is ever `false`, that is a bug, not a market condition.

### 5.6 `POST /api/settle`

Advance a match through settlement and return before, after, and the learning delta. **This drives the closing demo beat.**

**Request:**

```json
{
  "match_id": "MCH001",
  "outcome": "late",
  "days_late": 5,
  "scenario": { ...MarketScenario... }
}
```

**Response:**

```json
{
  "before": { "match": { ...Match... }, "affected_invoices": [ ...RiskProfile... ] },
  "after":  { "match": { ...Match... }, "affected_invoices": [ ...RiskProfile... ] },
  "delta":  { ...LearningDelta... }
}
```

**Two full evaluations per request is correct.** Do not optimise it into one. The before/after comparison is the product.

### 5.7 Errors

| Status | When | Body |
|---|---|---|
| 400 | Unknown ID in a request | `{ "error": "unknown_entity", "detail": "INV999 not in market", "entity_id": "INV999" }` |
| 400 | Preference weights do not sum to 1.0 | `{ "error": "invalid_weights", "detail": "Weights sum to 0.87, expected 1.0" }` |
| 400 | Illegal settlement transition | `{ "error": "illegal_transition", "detail": "Cannot settle a match in state 'matched'; fund it first" }` |
| 422 | Malformed body | pydantic validation output |
| 500 | Engine or market raised | `{ "error": "engine_failure", "detail": "<message>" }` |

Never return 500 for a bad request. Never return 200 with an error inside.

---

## 6. Validation

`schema.json` holds JSON Schema definitions for every object above.

```python
import json, jsonschema

schema = json.load(open("schema.json"))
jsonschema.validate(instance=market, schema=schema["definitions"]["MarketInput"])
```

**Required in tests:**

- A: `mockgen` output validates against `MarketInput`; `assess` output against `Assessment`
- B: every endpoint response validates against its definition; `Match` and `LearningDelta` validate
- C: committed mocks in `web/src/mocks/` validate against the same definitions

**Schema-enforced invariants** — these are checked by `schema.json`, not left to code review:

- `SupplierPreferences.weights` sums to `1.0` ± `0.001`
- `RiskProfile.reason_factors[].weight` sums to `1.0` ± `0.001`
- Every key in `field_confidence` names a field present on the same object
- `ProviderEligibility.exclusion_reason` is non-null whenever `eligible` is `false`
- `ScoredOffer.rejection_reason` is non-null whenever `feasible` is `false`
- `Match.allocations[].amount_lakh` sums to `Match.total_advance_lakh`

If a mock does not validate, it is not a mock — it is a future integration bug.

---

## 7. Changelog

| Version | Change |
|---|---|
| 1.0 | Initial contract. Monetary unit fixed as ₹ lakh. `pd_upper` designated the eligibility screen rather than `pd`. `naive_ranking` and `naive_mode` added as first-class contract fields to support the counterfactual. `max_fundable_lakh` added to `ProviderEligibility` to enable syndication |
| 1.1 | Added optional `Provider.target_margin` — the pricing spread `PERSON_B.md` §3.4 requires, which had no field in the contract. Documented it as distinct from `target_return`, which is an eligibility hurdle rather than a pricing term. Additive only; no field renamed or removed. |
