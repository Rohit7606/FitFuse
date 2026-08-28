# PERSON_C.md — Frontend, Visualisation & Product UX

**Person C / Person 3 — "Build what the judge experiences."**

Read `AGENTS.md`, `SCHEMA.md` and `DEMO_SCENARIO.md` before starting. This file assumes all three.

---

## 1. What you own

| Path | Yours |
|---|---|
| `web/` | Everything |
| `tests/web/` | Everything |

Your reviewer for every PR is **Person B**.

You own everything the judge sees, and — importantly — **the demo flow itself**. A and B provide technical input on the sequence; you own it.

That is deliberate. The person who builds the visuals understands the visual story best. Splitting "who builds the demo" from "who explains the demo" reliably produces a beautiful UI and a rambling pitch.

---

## 2. The one thing that matters most

Your entire product argument is:

> **The cheapest offer is not the best offer — and you can see it happen.**

A judge who *watches* the ranking reorder when a supplier says "I need cash fast, not a discount" has understood the thesis without anyone explaining it. A judge who reads a table of four rates has not.

**So spend your effort on the offer comparison and the slider, not on having many screens.** One great interaction beats four mediocre ones. If you run short of time, cut the stakeholder views before you cut the slider.

---

## 3. Stack

| Layer | Choice |
|---|---|
| Framework | React + Vite |
| Styling | Whatever you're fastest in. Tailwind is fine |
| State | React state. No Redux, no state library |
| Charts | Only where a bar genuinely beats a number. Most of this UI is comparison, not charting |
| Animation | CSS transitions. A layout animation helper is fine for the reorder; a physics engine is not |

**Forbidden:** `localStorage`, `sessionStorage`, any browser storage. Keep everything in React state.

Do not add a component library for five screens.

---

## 4. Never block on the backend

`web/src/mocks/` holds hand-written responses for all five endpoints, matching `SCHEMA.md` exactly.

```
npm run dev        # committed mocks
npm run dev:live   # http://localhost:8000
```

One flag, one API client module. Every component consumes the client, never `fetch` directly.

**Your mocks must validate against `schema.json`.** A mock that doesn't validate is not a mock — it is a future integration bug you have hidden from yourself. Test this.

B will stub all five endpoints in Phase 0, so you can switch to live early. Do it as soon as the stubs exist — that's what makes Phase 2 cheap.

---

## 5. Components

### 5.1 Offer comparison — the centrepiece

Four offer cards, side by side, all six dimensions visible at once. This is where the product lives.

**Per card:**

| Element | Notes |
|---|---|
| Provider name and type badge | `bank` / `nbfc` / `fund` / `fintech` |
| `fit_score` | Large, prominent, 2dp — the thing being ranked |
| Rate | Flag the lowest with a subtle marker, **not** a winner's badge |
| Cash now | `₹9.00 lakh` — arguably the number a supplier cares about most |
| Days to settle | `Same day` for `0`, not `0 days` |
| All-in cost | In rupees, so it can be compared against the rate |
| Fees, tenor, structure | Smaller, but present |
| `reason_text` | **Display in full.** This is the most defensible thing on screen |
| Rank position | Visible, and it must animate when the order changes |

**The lowest rate must be visually marked but not visually winning.** The whole point is that the cheapest headline rate loses. If your design makes it look like the winner, the demo argues against itself.

**Infeasible offers** (`feasible: false`) render greyed out, at the bottom, with `rejection_reason` shown. Do not hide them — a supplier seeing "advances only 60%, below your 70% minimum" learns more about the market than one who sees three cards and no explanation.

### 5.2 Preference sliders — the moment that sells it

Six sliders: cost, advance, speed, tenor, fees, structure. Plus three preset buttons.

**Behaviour:**

- Weights **must** always sum to 1.0. When one slider moves, redistribute the remainder proportionally across the other five. Send weights that sum to 1.0 or the API returns a 400 (`SCHEMA.md` §5.7)
- Debounce at **~250 ms**. Do not fire a request per pixel
- **Cards reorder with a layout animation, not a re-render jump.** The eye must be able to follow a card travelling from position four to position one. A card that teleports communicates nothing
- Presets snap the sliders to the values in `DEMO_SCENARIO.md` §4.1 and re-rank immediately

**This is your highest-value interaction.** Budget more polish time for it than for anything else. Target: 300–500 ms for the reorder — fast enough to feel responsive, slow enough to follow.

### 5.3 Verification panel

Demo step 2. Small, but it establishes trust early.

- IRN status — valid or rejected, with the reason
- **Field badges** — `verified` / `inferred` / `unknown`, each with an icon *and* a label
- **Duplicate detection.** When `INV002` is submitted, this must read unmistakably as blocked. Red, explicit, naming `INV001`

The `unknown` badge on `delivery_confirmed` is doing real work — it is what makes the risk range honest two steps later. Don't let it be visually minor.

### 5.4 Risk panel

- `pd` as a percentage, one decimal — `2.1%`
- **The range as a visible band, not two numbers in brackets.** A horizontal bar with the point estimate marked and the range shaded communicates uncertainty in a way `2.1% (1.4–2.8%)` does not
- `risk_band` chip
- `reason_factors` as a small weighted breakdown

**Showing uncertainty rather than hiding it is a feature.** Make it look deliberate and designed, not like an error bar someone forgot to remove.

### 5.5 Provider panel

Six rows. Four eligible, two greyed.

Per row: name, type, liquidity bar, risk appetite, and — for the excluded — **`exclusion_reason` in full.**

**Do not truncate exclusion reasons.** "Invoice of ₹10.00 lakh exceeds Coastal Cooperative Bank's ₹8.00 lakh maximum ticket size" is a complete argument that the market understands real constraints. Truncated to "ticket size limit", it's a filter.

**The liquidity bar is not decoration.** When Kestrel funds ₹6 lakh in step 7, that bar must visibly move, and it must show the sector-limit cap as a distinct marker from total liquidity. That marker is the visual explanation for why syndication happened.

### 5.6 Match and settlement view

Demo step 7. **Three visibly distinct states** — `matched`, `funded`, `settled`.

- `matched` — offer selected, **no money moved**. Say this in the UI, not just in the narration
- `funded` — cash disbursed, with the day count
- `settled` / `late` / `defaulted` — outcome

For a syndicated match, show the split explicitly: which provider funded how much, at what terms, and the blended rate. A stacked bar works well here.

**Making `matched` and `funded` look different is a requirement, not polish.** The problem statement is explicit that selecting an offer does not complete a financing, and a UI that collapses them into "done" throws away a requirement you satisfied.

### 5.7 Learning view

Demo step 8. Driven entirely by `LearningDelta` (`SCHEMA.md` §4.7).

- The trigger — "Vireon Motors paid 5 days late"
- `repriced_invoices` as before/after chips, showing the band change
- `provider_bid_adjustments` — "+15 bps on auto components / AA / 60-day"
- Liquidity returning to the provider

**Animate the repricing.** Other invoices on that buyer changing colour, one after another, is the visible proof that the market learns. Static before/after tables do not land the same way.

### 5.8 Naive-mode toggle — the closer

One switch. Flips the ranking to `naive_ranking`.

**Both rankings are already in the `/api/offers` response** (`SCHEMA.md` §5.4). Switching must be **instant** — no refetch, no spinner. You are toggling between two known states.

When on, show the outcome side by side:

```
Lowest-rate market:  ₹7.00 lakh   ·   2 days   ·   ₹17,437
FitFuse:             ₹9.00 lakh   ·   same day ·   ₹16,722
```

Let the two rows sit next to each other and do the work. Do not add commentary on screen.

### 5.9 Stakeholder views

A filter on the same data, not three separate apps.

| View | Shows |
|---|---|
| **Supplier** | Own invoice, preferences, offers, match state |
| **Provider** | Own liquidity, limits, opportunities surfaced, current exposure |
| **Market** | All live invoices, all providers, utilisation |

**Cut these first if time runs short.** They satisfy a requirement; the offer comparison and slider win the room.

---

## 6. Presentation rules

- **Every number carries its unit.** `₹9.00 lakh`, `8.6%`, `60 days`, `same day`. Never a bare float
- **Round for humans.** `₹16,722` not `0.16722`. `2.1%` not `0.0210`
- **Display conversion is yours alone.** The API sends ₹ lakh (`AGENTS.md` §3.5). Rendering `5000.00` as `₹50 cr` is a frontend concern — do it in one formatting helper, not scattered through components
- **Colour is not the only signal.** Add shape or a label — some judges have colour vision deficiency, and projectors distort hues
- **Every entity shows `data_source: synthetic`.** A judge must never think this is real market data (`AGENTS.md` §3.7). Legend it once, visibly, and never remove it
- **Legend always visible** for risk bands and field-confidence badges
- **No loading spinners longer than a beat.** Pre-fetch the market at mount
- **Design for a projector:** larger fonts than feel right, high contrast, test at 1280×720

---

## 7. Tests — `tests/web/`

Keep it light. You are not shipping to production.

| Test | Asserts |
|---|---|
| `test_mocks_valid` | Every file in `src/mocks/` validates against `schema.json` |
| `test_renders_offers` | Offer cards render from mock data without errors |
| `test_weights_sum` | Slider interaction always produces weights summing to 1.0 |
| `test_reorder` | Changing preferences reorders the cards |
| `test_reasons_untruncated` | `reason_text` and `exclusion_reason` render in full |
| `test_infeasible_shown` | An offer with `feasible: false` renders greyed, with its reason, not hidden |
| `test_naive_toggle` | Toggle switches ranking without a network call |
| `test_no_browser_storage` | Grep the bundle for `localStorage` / `sessionStorage` |

`test_mocks_valid` is the one that pays for itself — it catches contract drift before Phase 2. `test_weights_sum` catches the 400 you would otherwise discover live on stage.

---

## 8. Phases

**Phase 0 — Contract freeze**
- Agree `SCHEMA.md` and `schema.json` with A and B
- Write `web/src/mocks/` for all five endpoints
- Vite app shell, API client with the mock/live flag
- **Exit:** you can build with the backend switched off

**Phase 1 — Independent build**
- Offer cards, preference sliders, reorder animation — all from mocks
- Verification and risk panels
- **Exit:** dragging a slider visibly reorders four mock offers

**Phase 2 — Integration**
- Switch to B's live API, fix mismatches at the contract
- Provider panel with real eligibility and exclusion reasons
- **Exit:** live data renders end to end, slider included

**Phase 3 — Demo path**
- Match and settlement view, learning view, naive toggle
- Stakeholder views
- **Rehearse the eight steps end to end, repeatedly**
- **Exit:** the demo runs clean without a refresh

**Phase 4 — Hardening**
- Empty and error states, projector testing, final rehearsal

---

## 9. You own the demo flow

`DEMO_SCENARIO.md` §6 has the eight steps. Beyond building them:

- **Read IDs from `data/fixtures/demo_scenario.json`.** Never hardcode `INV001` in a component
- **Rehearse on the actual machine and projector**, not just your laptop
- **Time it.** Target four minutes. Steps 6 and 8 get the most air
- **Have a fallback.** A recorded video or screenshots, in case something fails on the day
- **Open with the supplier, not the mechanism.** A business with payroll on Friday and four lenders willing to help. The auction theory only lands after the stakes do
- **Say "simulated" once, early, plainly.** Naming it yourself is a strength. Being caught not having named it is not

---

## 10. Traps specific to your track

- **Building screens instead of depth.** Five polished views beat nine rough ones. The offer comparison and the slider are the product
- **Making the lowest rate look like the winner.** Your design would then argue against your own thesis
- **Cards that teleport instead of animating.** The reorder is the moment. If the eye can't follow it, the moment is gone
- **Truncating reason text or exclusion reasons.** Removes the most defensible thing on screen
- **Hiding infeasible offers.** The rejection reason teaches the judge how the market thinks
- **Refetching on the naive toggle.** Both rankings are already in the response; switching must be instant
- **Sending weights that don't sum to 1.0.** The API returns a 400 and your slider appears broken on stage
- **Converting units in components.** One formatting helper, or you will ship a `₹50 cr` next to a `₹5000 lakh`
- **Dropping the synthetic badge to make screenshots look cleaner.** Non-negotiable — `AGENTS.md` §3.7
- **Browser storage.** Forbidden — `AGENTS.md` §1.2
- **Leaving the demo until Phase 3 to rehearse.** Rehearse from Phase 2, roughly, and keep rehearsing
