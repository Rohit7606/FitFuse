# DEMO_SCENARIO.md — FitFuse

**This file has no single owner.** Changes require both other team members named on the PR. See `AGENTS.md` §4.3.

This is the one scenario all three tracks build toward. Entity IDs and amounts here are **fixed and committed**. If Person C animates a ranking flip between offers Person A's engine scores in the opposite order, the demo breaks — and that only gets caught if everyone points at the same identifiers.

---

## 1. The story in one line

> Verified invoice → honest risk → some providers can't fund it and say why → four genuinely different offers → the supplier's priorities change the winner → syndicated match → the buyer pays late → the market learns.

---

## 2. The cast — fixed IDs

These IDs are guaranteed present in `data/mock/market.json` at seed `42`, and must survive any regeneration.

### 2.1 The invoice and the parties

| ID | Name | Role in the demo |
|---|---|---|
| `SUP001` | Sharda Auto Components Pvt Ltd | **The protagonist.** Pune MSME, 7 years operating, ₹480 lakh revenue. Payroll due Friday |
| `BUY001` | Vireon Motors India Ltd | The buyer. AA-rated OEM, 4-day average payment delay. **Pays late in step 7** |
| `INV001` | — | **The headline invoice.** ₹10.00 lakh, 60-day tenor, IRN valid, delivery unconfirmed |
| `INV002` | — | **The duplicate.** Same `document_hash` as `INV001`, submitted from a different supplier. Blocked in step 2 |
| `INV014` | — | A second live invoice on `BUY001`. Exists only so step 7's repricing has something to visibly affect |

### 2.2 The capital providers

Six providers. Four eligible, two excluded — and the exclusions are the point.

| ID | Name | Type | Character | Role |
|---|---|---|---|---|
| `PRV001` | Meridian Bank | bank | Conservative. Cheap-ish, modest advance, 3-day settlement | Offers. **Takes the syndication remainder** |
| `PRV002` | Arcline Capital | nbfc | **The lowest headline rate — 8.2%.** Low advance, high fees | The trap. What a naive market would pick |
| `PRV003` | Kestrel Credit Fund | fund | Opportunistic. Highest advance, same-day, low fees | **The fit winner — but capacity-limited** |
| `PRV004` | Nimbus Finserv | fintech | Fast and low-fee, but prices high and advances modestly | Offers. Shows cheapest-in-rupees ≠ best fit |
| `PRV005` | Coastal Cooperative Bank | bank | ₹8.00 lakh maximum ticket | **Excluded — ticket size** |
| `PRV006` | Sentinel Asset Managers | fund | Risk appetite `0.015`, below this invoice's `pd_upper` | **Excluded — risk appetite** |

**The chain that matters:**

```
SUP001 Sharda ──invoice INV001──▶ BUY001 Vireon
   (supplier)     ₹10.00 lakh        (buyer, pays in 60 days)
       ▲
       │ cash now
       │
  PRV003 Kestrel (₹6.00 lakh)  +  PRV001 Meridian (₹3.00 lakh)
```

Read the invoice arrow as "is owed by." Goods already flowed to Vireon; money flows back in 60 days. The financiers stand in for Vireon in the meantime — **which is why Vireon's credit grade, not Sharda's, drives the risk score.**

---

## 3. Why PRV003 beats PRV002 — the point of the whole product

Both are real offers. Only one is right for this supplier.

| | `PRV002` Arcline | `PRV003` Kestrel |
|---|---|---|
| Headline rate | **8.2% — the lowest** | 8.6% |
| Advance rate | 70% | **90%** |
| Days to settle | 2 | **0 — same day** |
| Fee | 0.8% | **0.4%** |
| Cash to Sharda | ₹7.00 lakh | **₹9.00 lakh** |
| All-in cost | ₹17,437 | **₹16,722 — actually cheaper** |
| `fit_score` | 0.64 | **0.89** |

A judge who asks *"why isn't the cheapest rate winning?"* gets the entire thesis in one answer:

> **The lowest rate is not the lowest cost, and cost is not the only thing that matters. Arcline advances less money, more slowly, and charges higher fees — so it costs ₹715 more in rupees while delivering ₹2 lakh less cash.**

Keep this contrast intact through any tuning. It is the most defensible thing in the demo.

---

## 4. The exact offer table

Person A owns these values. Person B's agents must produce them. Person C designs around them.

Invoice: **₹10.00 lakh, 60-day tenor.**

```
total_cost_lakh = amount × advance_rate × rate_annual × (tenor_days / 365)
                + amount × fee_percent
                + fee_flat_lakh
```

| Offer | Provider | Rate | Advance | Settles | Fee | Structure | Cash now | All-in cost | `fit_score` |
|---|---|---|---|---|---|---|---|---|---|
| `OFR001` | Meridian Bank | 0.0900 | 0.80 | 3 d | 0.0050 | bullet | ₹8.00 L | ₹16,836 | 0.71 |
| `OFR002` | Arcline Capital | **0.0820** | 0.70 | 2 d | 0.0080 | bullet | ₹7.00 L | ₹17,437 | 0.64 |
| `OFR003` | Kestrel Credit Fund | 0.0860 | **0.90** | **0 d** | 0.0040 | bullet | ₹9.00 L | ₹16,722 | **0.89** |
| `OFR004` | Nimbus Finserv | 0.0940 | 0.75 | 1 d | 0.0030 | instalment | ₹7.50 L | **₹14,589** | 0.68 |

**Worked check for `OFR003`** — Person A should reproduce this exactly:

```
10.00 × 0.90 × 0.0860 × (60/365) = 0.12722
10.00 × 0.0040                   = 0.04000
                          total  = 0.16722 lakh  →  ₹16,722
```

**Two deliberate traps in this table**, both of which make the demo stronger:

1. **`OFR002` has the lowest rate but is not the cheapest in rupees.** Its lower advance and higher fee make it cost more than `OFR003`. Say this out loud — it lands
2. **`OFR004` is the cheapest in rupees but still loses.** Because it advances only 75% and repays in instalments, which Sharda did not ask for. This pre-empts the judge who says "so you just want the cheapest total cost"

### 4.1 The slider flip

Sharda's committed preset is `cash_fastest`. The demo also uses a second weight set to show the ranking is genuinely preference-driven:

| Preset | cost | advance | speed | tenor | fees | structure | Winner |
|---|---|---|---|---|---|---|---|
| `cheapest` | 0.55 | 0.10 | 0.05 | 0.10 | 0.15 | 0.05 | **`OFR004`** |
| `cash_fastest` (committed) | 0.15 | 0.30 | 0.35 | 0.10 | 0.05 | 0.05 | **`OFR003`** |

**Three different winners across three views of the same four offers** — `OFR002` under naive mode, `OFR004` under `cheapest`, `OFR003` under `cash_fastest`. That is the strongest single fact in the demo.

---

## 5. The numbers on screen

Indicative, from the mock market at seed `42`. Person A owns the exact values; these are what the other two design around.

**Assessment of `INV001`:**

| Metric | Value |
|---|---|
| Verification | `verified` — IRN valid, no duplicate |
| Unknown fields | 1 — `delivery_confirmed` |
| `pd` | 0.0210 |
| `pd` range | 0.0140 – 0.0280 |
| `risk_band` | `prime` |
| Providers eligible | 4 of 6 |
| Excluded | `PRV005` (ticket size), `PRV006` (risk appetite) |

**Clearing:**

| Metric | Value |
|---|---|
| Winning offer by fit | `OFR003` (Kestrel) |
| Kestrel's `max_fundable_lakh` | **₹6.00 lakh** — sector limit binds at 94% of a 20% cap |
| Syndication partner | `PRV001` Meridian, ₹3.00 lakh |
| Total advance | **₹9.00 lakh** |
| Blended rate | 0.0873 |
| Match state | `matched` → `funded` |

**The naive counterfactual:** `OFR002` alone. ₹7.00 lakh, 2 days, ₹17,437.

> **₹2.00 lakh more cash, two days sooner, for ₹715 less.** Same invoice, same four lenders, different market.

**After settlement (`late`, 5 days):**

| Metric | Value |
|---|---|
| `BUY001` average delay | 4 d → 5 d |
| `INV014` `pd` | 0.0210 → 0.0265 |
| `INV014` band | `prime` → `standard` |
| Kestrel's rate on this segment | +15 bps |
| Liquidity returned to Kestrel | ₹6.00 lakh |

---

## 6. The eight steps

| # | On screen | Said aloud | Owner |
|---|---|---|---|
| 1 | Market view. Live invoices, six providers with liquidity bars | "Sharda has a ₹10 lakh invoice and payroll on Friday. Six lenders have money. Today she'd call one of them." | C |
| 2 | `INV001` submitted. IRN validates. Field badges appear — one reads **delivery unconfirmed**. Then `INV002` submitted → **duplicate blocked** | "We verify before we finance. And we catch the same invoice being financed twice." | C |
| 3 | Risk panel. `pd` 2.1%, **range 1.4–2.8%**, with the range explained | "Two-point-one percent — but honestly, somewhere between 1.4 and 2.8, because we can't confirm delivery. We show the range rather than hiding it." | C |
| 4 | Six providers. Four light up. **Two grey out with reasons on screen** | "Coastal can't write a ticket this size. Sentinel's risk appetite is below this invoice. A real market knows that before it asks anyone to bid." | C |
| 5 | Four offers appear, visibly different. Lowest rate flagged on `OFR002` | "Four offers. The cheapest rate is 8.2%. Watch what happens." | C |
| 6 | **The slider moment.** Drag speed and advance up → ranking reorders, `OFR003` to the top. Reason text reads out | "Sharda needs cash, not a discount. Now the 8.6% offer wins — and it actually costs less in rupees than the 8.2% one." | C |
| 7 | Clearing runs. Kestrel caps at ₹6 lakh, Meridian takes ₹3 lakh. **`matched` → `funded`** | "Kestrel wants all of it. Its auto-components book won't allow it. So the market splits the deal — and Sharda still gets ₹9 lakh." | C |
| 8 | **Settle late.** `BUY001` delay rises, `INV014` reprices, Kestrel's next bid moves up. Then **toggle naive mode** — the market collapses to `OFR002`, ₹7 lakh | "Vireon pays five days late. The market notices, reprices, and reallocates. And this — this is what she'd have got from a lowest-rate marketplace." | C |

**Step 6 sells the project. Step 8 closes it.** Everything else is setup.

---

## 7. The counterfactual

Step 8's second half. Toggle `naive_mode: true` and let the market rank by rate alone.

- `OFR002` rises to the top on 8.2%
- Advance drops to 70% — **₹7.00 lakh instead of ₹9.00 lakh**
- Settlement slows to 2 days
- All-in cost *rises* to ₹17,437

The supplier who needed cash by Friday gets ₹2 lakh less, two days later, for more money — from the same four lenders, on the same invoice.

**Do not over-narrate this.** Put the two numbers side by side and let them do it.

---

## 8. The fixture file

`data/fixtures/demo_scenario.json`:

```json
{
  "scenario_id": "canonical_v1",
  "description": "Sharda's invoice: fit beats rate, capacity forces syndication, late payment triggers learning",
  "invoice_id": "INV001",
  "duplicate_invoice_id": "INV002",
  "supplier_id": "SUP001",
  "buyer_id": "BUY001",
  "secondary_invoice_id": "INV014",

  "expected_verification": {
    "status": "verified",
    "irn_valid": true,
    "duplicate_detected": false,
    "unknown_field_count": 1
  },
  "expected_duplicate_verification": {
    "status": "rejected",
    "duplicate_detected": true,
    "duplicate_of": "INV001"
  },

  "expected_risk": {
    "risk_band": "prime",
    "pd_range": [0.0140, 0.0280]
  },

  "expected_eligible": ["PRV001", "PRV002", "PRV003", "PRV004"],
  "expected_excluded": {
    "PRV005": "max_ticket",
    "PRV006": "risk_appetite"
  },

  "expected_ranking":       ["OFR003", "OFR001", "OFR004", "OFR002"],
  "expected_naive_ranking": ["OFR002", "OFR003", "OFR001", "OFR004"],
  "expected_cheapest_preset_winner": "OFR004",

  "expected_match": {
    "syndicated": true,
    "total_advance_lakh": 9.00,
    "allocations": [
      { "provider_id": "PRV003", "amount_lakh": 6.00 },
      { "provider_id": "PRV001", "amount_lakh": 3.00 }
    ]
  },

  "settlement_event": { "outcome": "late", "days_late": 5 },
  "expected_after_learning": {
    "BUY001_avg_delay": 5,
    "INV014_band_before": "prime",
    "INV014_band_after": "standard"
  }
}
```

**This file is a test fixture, not just documentation.**

- **Person A** asserts in `tests/engine/` that assessment reproduces `expected_verification`, `expected_risk`, `expected_eligible`, `expected_excluded` and `expected_ranking`
- **Person B** asserts in `tests/market/` that clearing reproduces `expected_match`, and that settling reproduces `expected_after_learning`
- **Person C** reads `invoice_id`, `duplicate_invoice_id` and `settlement_event` rather than hardcoding them in components

If a tuning change breaks these assertions, that is the system working. Either retune, or update the fixture deliberately with both others named on the PR.

---

## 9. Rules

- **Never hardcode these IDs in application logic.** Read them from the fixture. Demo data must not leak into the engine, the market simulator, the API, or component internals
- **Regenerating the mock market must preserve every ID in §2.** `mockgen.py` places them explicitly before generating filler
- **The demo must run without a refresh or a manual fix.** If any step needs a human to intervene, it isn't done
- **No new names.** Everything on screen comes from this file or the mock market
- **`OFR003` must beat `OFR002` under `cash_fastest`, and `OFR004` must beat both under `cheapest`.** If tuning breaks either, the demo's argument breaks with it

---

## 10. Naming note

All company names here are **fictional**, constructed for the mock market. They are deliberately plausible rather than obviously fake — placeholders like `Supplier_12` or `Bank A` make the whole demo read as a toy.

**No real company is named anywhere in this project.** "Vireon Motors India Ltd" is invented; it is not a stand-in for any actual manufacturer, and nobody should describe it as one on stage. Every entity carries `data_source: "synthetic"` and the UI must show it — see `AGENTS.md` §3.7.

The financing terms are shaped to be plausible for Indian MSME invoice discounting, but they are illustrative, not quoted from any lender.

---

## 11. Changelog

| Version | Change |
|---|---|
| 1.0 | Initial. Six providers, four offers, eight-step flow. `OFR003`-vs-`OFR002` established as the core argument; `OFR004` added as the cheapest-in-rupees decoy to pre-empt the "you just want lowest total cost" objection |
