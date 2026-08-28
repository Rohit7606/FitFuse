# CONTEXT FILE — "FitFuse"
### An Agentic Multi-Dimensional Clearinghouse for Supply-Chain Working Capital

**Hackathon:** CSI ORIGIN 2026
**Problem Statement:** #5 — Building a Competitive Capital Market for Supply-Chain Working Capital
**Status of this file:** Single source of truth for the build. If something is not in here, it is not in scope.

---

## 0. How to use this file

This document is written so that any teammate — or an AI coding assistant — can read it once and start building without needing the original research.

It is organised as:

1. What we are building (in one page)
2. Why this wins
3. The plain-English concepts (glossary first, so nothing later is confusing)
4. The system architecture
5. The data model
6. The algorithms, with actual formulas
7. The end-to-end flow, step by step
8. What to build vs. what not to build
9. Build plan and timeline
10. The demo script
11. Objection handling for judges
12. Appendix: worked example with real numbers

---

## 1. What we are building — the one-page version

**In one sentence:**
A marketplace where verified invoices are auctioned to competing capital providers, but providers compete on the **whole offer** — rate, how much cash you get, how fast, fees, tenor, repayment structure — scored against **each supplier's own priorities**, with every provider represented by an autonomous agent that respects its own real money limits.

**The three things that make it different from everything that exists:**

| # | What we do | What existing platforms do |
|---|---|---|
| 1 | Offers compete on a **whole-offer value score** built from the supplier's stated priorities | TReDS, OCEN, C2FO compete on **one number** — the rate |
| 2 | Each provider is an **agent with a budget, risk appetite and concentration limits**, and it bids carefully to avoid overpaying | Providers bid manually, or funding is allocated by static rules (Taulia, PrimeRevenue) |
| 3 | The market **re-clears continuously** and **learns from what actually got repaid**, reallocating capital | Auctions are one-shot; nothing feeds back |

**The name:** FitFuse — because it optimises *fit*, not price.

**The tagline:**
> "The cheapest offer is not the best offer. We built the market that knows the difference."

---

## 2. Why this wins

### 2.1 It hits the exact sentence the organisers built the problem around

The problem statement says, in its own words:

> "The most attractive financing option for a supplier may not be the offer with the lowest interest rate. Advance rate, fees, tenor, settlement speed, repayment structure, and supplier requirements may materially affect the overall value of an offer."

And:

> "The system must therefore solve a dynamic matching and allocation problem rather than a simple offer-comparison problem."

Most teams will read this, nod, and then build a lowest-rate auction anyway. Our entire system is built around that one sentence.

### 2.2 It sits in a real gap, not an invented one

- **India's TReDS platforms** (RXIL, M1xchange, Invoicemart) already run anonymous reverse auctions where multiple banks bid on an accepted invoice. RXIL alone has crossed ₹2,00,000 crore in cumulative MSME invoice financing. So "multiple lenders bidding" is **table stakes, not novelty**. We must not claim it as our innovation.
- **OCEN 4.0** already shares a loan application with multiple lenders using Account Aggregator data. Again — table stakes.
- **C2FO** runs a "name your rate" market, but it optimises a single discount rate and is typically funded by the buyer's own cash, not competing third-party lenders.
- **Taulia and PrimeRevenue** have multi-funder networks, but funders are allocated by pre-configured rules — when one funder hits a limit, the invoice is redirected to a *prescribed* next funder. That is routing, not competition.
- **The Receivables Exchange**, which pioneered single-invoice auctions, is permanently closed — it could never line up enough committed liquidity.

**Nobody deployed does multi-attribute suitability + portfolio-aware bidding + continuous re-clearing + a learning loop.** That is our space.

### 2.3 It is backed by citable theory, which is hard to replicate in a weekend

- **Multi-attribute auctions** (Che, 1993): bids ranked by a buyer-designed scoring rule across price and non-price attributes.
- **Stable matching** (Gale–Shapley; Roth & Shapley, Nobel 2012): produces matches where no supplier–provider pair would both rather defect.
- **Bandits with knapsacks** (Badanidiyuru, Kleinberg & Slivkins; Agrawal & Devanur): allocating limited capital across a stream of opportunities under budget constraints while learning.
- **The winner's curse and adverse selection**: Prosper's documented shift from borrower auctions to posted prices showed that naive auctions cause lenders to systematically overpay and underperform.

A competing team can copy "an auction with bids." They cannot easily copy this stack in the same time.

---

## 3. Plain-English glossary (read this before anything else)

These terms appear throughout. Each is explained in everyday language, because half the team will be non-finance people.

**Invoice** — a bill. Supplier delivered goods to a buyer, and the buyer will pay in, say, 60 days. The supplier wants that money now.

**Invoice financing / factoring** — a financier gives the supplier most of that money today, and collects from the buyer later, keeping a fee.

**Supplier** — the small business that is owed money and wants cash now. Usually an MSME.

**Buyer** — the (usually larger) company that owes the money. **The buyer's creditworthiness matters more than the supplier's**, because the buyer is the one who will actually pay.

**Capital provider** — bank, NBFC, fund, or fintech with money to deploy. In our system each one is an autonomous agent.

**NBFC** — Non-Banking Financial Company. An Indian lender that isn't a bank. Think of it as a lender without a savings-account business.

**Advance rate** — what percentage of the invoice you get up front. An 80% advance on a ₹10 lakh invoice means ₹8 lakh now, the rest (minus fees) when the buyer pays. **A higher advance rate can be worth more to a cash-starved supplier than a lower interest rate.**

**Tenor** — how long the financing lasts. Usually matched to when the buyer pays.

**Settlement speed** — how many days until the money actually lands in the supplier's bank account. Same-day versus five days is a huge difference to a business making payroll.

**Repayment structure** — how it gets paid back. "Bullet" means one lump sum at the end. Others might be instalments.

**Discount rate / financing rate** — the interest, effectively. The cost of the money.

**Risk appetite** — how much danger a provider is willing to accept. A conservative bank wants safe, boring invoices. An opportunistic fund will take risk if the return is high enough.

**Liquidity** — how much money a provider actually has available right now to deploy.

**Portfolio concentration limit** — a rule like "no more than 20% of my money in auto components." Even if an invoice looks great, a provider may refuse because it is already too exposed to that sector. **This is one of our key differentiators — most demos ignore it.**

**Risk-adjusted return** — return after accounting for how likely you are to lose. Earning 12% on something that defaults 5% of the time is worse than 9% on something safe.

**Information asymmetry** — the supplier knows more about their own business than the lender does. The lender has to price that uncertainty.

**Winner's curse** — in an auction, the winner is often whoever was *most wrong* about the value. If five lenders bid and one badly underestimates the risk, that one wins and loses money. A market that ignores this quietly destroys its own lenders.

**Adverse selection** — the worst borrowers are the keenest to borrow. If you price naively, you attract exactly the customers you don't want.

**Stable match** — a pairing where no supplier and provider would *both* prefer to break their current match and pair with each other instead. Stable markets don't fall apart.

**Continuous double auction** — a market that clears constantly as new orders arrive, rather than in one big round. A stock exchange works this way.

**IRN (Invoice Reference Number)** — under India's GST e-invoicing system, an invoice registered with the government gets a unique number and a QR code. **It proves the invoice was officially reported.** It does *not* prove the goods were delivered — an important honesty point for us.

**Duplicate financing fraud** — the same invoice financed twice with two different lenders. A real, common fraud. Solved in industry by hash registries (e.g. MonetaGo's approach, which fingerprints documents and checks for reuse).

**Hash / fingerprint** — a short unique code generated from a document. Two identical documents produce the same code, so you can detect reuse **without revealing the document contents**.

**Escrow** — money held by a neutral party, released only when conditions are met.

**Utility function** — a formula that turns "how good is this for me" into a single number, so options can be ranked. Ours turns a whole offer into one score.

**Conjoint analysis** — a technique from market research: instead of asking "how much do you value speed?", you show people a few choices and *infer* their priorities from what they pick. We use a simplified version.

**Contextual bandit** — a learning method that decides which option to pick when you only find out the result of the option you chose. "Bandit with knapsack" adds a budget you cannot exceed.

**SHAP** — a way to explain a model's decision by showing how much each input pushed the answer up or down. We use the idea, not necessarily the library.

---

## 4. System architecture

### 4.1 The seven components

```
                         ┌──────────────────────┐
   Supplier submits ───► │ 1. VERIFICATION GATE │
   invoice               │  IRN check           │
                         │  Duplicate hash      │
                         │  Field tagging       │
                         └──────────┬───────────┘
                                    │  verified opportunity
                                    ▼
                         ┌──────────────────────┐
                         │ 2. RISK ENGINE       │
                         │  Default probability │
                         │  + uncertainty band  │
                         └──────────┬───────────┘
                                    │  risk profile
                                    ▼
                         ┌──────────────────────┐
                         │ 3. DISCOVERY /       │
                         │    SUITABILITY FILTER│ ◄──── provider profiles
                         │  who should see this?│
                         └──────────┬───────────┘
                                    │  shortlist of eligible providers
                                    ▼
       ┌────────────────────────────────────────────────┐
       │ 4. PROVIDER AGENTS (4–6 of them, autonomous)    │
       │    each: liquidity, risk appetite, limits,      │
       │    target return, bidding policy                │
       └──────────┬─────────────────────────────────────┘
                  │  competing multi-term offers
                  ▼
   supplier ────► ┌──────────────────────┐
   priorities     │ 5. SCORING ENGINE    │
   (sliders) ───► │  whole-offer value   │
                  └──────────┬───────────┘
                             │  ranked offers + explanations
                             ▼
                  ┌──────────────────────┐
                  │ 6. CLEARING ENGINE   │
                  │  stable matching     │
                  │  continuous re-clear │
                  └──────────┬───────────┘
                             │  match
                             ▼
                  ┌──────────────────────┐
                  │ 7. SETTLEMENT + LEARN│
                  │  state machine       │
                  │  outcome feedback ───┼──► back into 2 and 4
                  └──────────────────────┘
```

### 4.2 What each component is responsible for

**1. Verification gate.** Nothing enters the market unverified. Checks the IRN, computes a hash to detect the same invoice being financed twice, and tags every data field as `verified`, `inferred`, or `unknown`. This directly answers the problem statement's requirement to "distinguish verified information from uncertain or incomplete information."

**2. Risk engine.** Produces a default probability *and* a confidence band. Critically, the band widens when fields are `unknown` — so uncertainty is visible, not hidden. Uses buyer creditworthiness as the primary signal, plus a small buyer–supplier network graph so thin-file suppliers can be scored via their buyer and peers.

**3. Discovery / suitability filter.** Decides which providers even *see* an opportunity. This is the problem statement's "determine which opportunities should be surfaced to which providers." Filters on risk appetite, available liquidity, sector and buyer concentration limits, and ticket-size range.

**4. Provider agents.** The autonomous part. Each agent independently decides whether to bid and what to offer across all terms. It shades its bid based on uncertainty (winner's-curse protection) and refuses deals that breach its own limits, even profitable ones.

**5. Scoring engine.** Converts every offer into one number representing value *to this supplier*. Fully transparent — we show the arithmetic.

**6. Clearing engine.** Runs deferred acceptance so matches are stable, and re-clears when conditions change (new liquidity, changed priorities, a withdrawn offer).

**7. Settlement and learning.** A match is not "done" when an offer is accepted. It becomes `funded` only when conditions are met and `settled` when the buyer actually pays. Outcomes then update risk scores and agent policies.

### 4.3 Tech stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + Tailwind | Fast, everyone knows it, good for live sliders |
| Charts | Recharts | Simple, reliable |
| Backend | Python + FastAPI | The scoring, matching and bandit logic is all Python-friendly |
| Data | SQLite or in-memory | No infra time wasted. Persistence is not the point. |
| Simulation | Python scripts generating synthetic invoices, buyers, providers | Real SCF data is unavailable |
| Real-time | WebSocket or 2-second polling | Needed for the "continuous market" feel |
| ML | scikit-learn (logistic regression or gradient boosting) | Explainable, trains in seconds |

**Deliberate non-choices:** no blockchain, no microservices, no Kubernetes, no auth system, no cloud deployment beyond a single box.

---

## 5. Data model

```python
Invoice
  id
  supplier_id
  buyer_id
  amount                 # e.g. 1_000_000
  issue_date
  due_date
  tenor_days             # due_date - today
  irn                    # GST invoice reference number (mocked)
  document_hash          # SHA-256, for duplicate detection
  verification_status    # verified | pending | rejected
  field_confidence       # {"amount": "verified", "buyer_gst": "verified",
                         #  "delivery_confirmed": "unknown", ...}

Supplier
  id, name, sector, years_operating, gst_id
  data_completeness      # 0-1, drives uncertainty
  preferences            # see below

SupplierPreferences
  w_cost                 # weight on cheapness
  w_advance              # weight on getting more cash now
  w_speed                # weight on fast settlement
  w_tenor                # weight on longer repayment time
  w_fees                 # weight on low fees
  w_structure            # weight on flexible repayment
  # weights normalised to sum to 1
  min_advance_rate       # hard constraint, e.g. "I need at least 70%"
  max_days_to_cash       # hard constraint, e.g. "must be within 5 days"

Buyer
  id, name, sector
  credit_grade           # AAA..C
  historical_payment_delay_days
  known_disputes

CapitalProvider
  id, name, type         # bank | nbfc | fund | fintech
  available_liquidity    # the knapsack budget
  risk_appetite          # 0-1; 0 = ultra conservative
  min_ticket, max_ticket
  target_return          # required risk-adjusted return, e.g. 0.09
  sector_limits          # {"auto": 0.20, "textile": 0.30} as % of portfolio
  buyer_limits           # per-buyer concentration cap
  current_exposure       # {sector: amount, buyer: amount}
  cost_of_funds          # floor below which it cannot bid

Offer
  id, invoice_id, provider_id
  rate_annual            # e.g. 0.088
  advance_rate           # e.g. 0.85
  tenor_days
  fee_flat, fee_percent
  days_to_settle
  repayment_structure    # bullet | instalment
  amount_committed       # allows partial fills / syndication
  expires_at
  score                  # computed by scoring engine
  explanation            # plain-English reason

Match
  id, invoice_id
  offer_ids              # possibly several, for syndicated deals
  state                  # matched | funded | settled | late | defaulted
  supplier_utility
  created_at, funded_at, settled_at

MarketEvent                # for the learning loop
  type                     # liquidity_change | repayment | default | preference_change
  payload, timestamp
```

---

## 6. The algorithms — with actual formulas

This is the intellectual core. Build these carefully; everything else is plumbing.

### 6.1 The Whole-Offer Value Score (the centrepiece)

**The problem it solves:** two offers, one at 8.2% and one at 8.6%, and the 8.6% one is genuinely better for this supplier. We need a defensible number that says so.

**Step 1 — Hard constraints.** Reject any offer violating `min_advance_rate` or `max_days_to_cash`. These are non-negotiable supplier requirements, not preferences.

**Step 2 — Normalise every attribute to 0–1**, where 1 is always "best for the supplier."

```
cost_score     = 1 - (total_cost - min_cost) / (max_cost - min_cost)
advance_score  = (advance_rate - min_adv) / (max_adv - min_adv)
speed_score    = 1 - (days_to_settle - min_days) / (max_days - min_days)
tenor_score    = (tenor - min_tenor) / (max_tenor - min_tenor)
fee_score      = 1 - (fees - min_fees) / (max_fees - min_fees)
structure_score= 1.0 if matches preferred structure else 0.6
```

Where `total_cost` is the true all-in rupee cost, not the headline rate:

```
total_cost = amount * advance_rate * rate_annual * (tenor_days / 365)
           + fee_flat
           + amount * fee_percent
```

**Step 3 — Combine using the supplier's weights.**

```
V(offer) = w_cost * cost_score
         + w_advance * advance_score
         + w_speed * speed_score
         + w_tenor * tenor_score
         + w_fees * fee_score
         + w_structure * structure_score
```

**Step 4 — Apply a liquidity-urgency multiplier.** If the supplier flagged urgent cash need, speed and advance get boosted before normalisation. This is what makes the score *contextual* rather than a generic weighted average.

**Why this is defensible:** it is a direct application of Che's scoring-rule framework for multi-attribute auctions, where a buyer publishes a scoring rule and suppliers bid against it. We invert it for the financing context. We can name the theory on the slide.

**How suppliers set weights (three modes, because MSMEs won't know their own weights):**

1. **Presets** — "Cheapest money", "Cash fastest", "Maximum cash now". One click.
2. **Sliders** — six sliders, live re-ranking as you drag. This is the demo moment.
3. **Inferred** — show three pairs of hypothetical offers, ask which they'd take, infer weights from the choices. This is simplified adaptive conjoint analysis. **Build this last — it is a bonus, not core.**

### 6.2 Risk scoring with honest uncertainty

**Default probability:**

```
PD = model(buyer_credit_grade,
           buyer_payment_delay_history,
           invoice_amount_vs_supplier_typical,
           tenor_days,
           supplier_years_operating,
           sector_stress_index,
           buyer_network_centrality)
```

Use logistic regression or a small gradient-boosted tree on synthetic data. Explainability matters more than accuracy here.

**The uncertainty band — this is the differentiator:**

```
uncertainty = base_uncertainty
            + 0.05 * count(fields tagged "unknown")
            + 0.03 * count(fields tagged "inferred")
            + thin_file_penalty(supplier.data_completeness)

PD_range = [PD - uncertainty, PD + uncertainty]
```

Every opportunity is displayed as, for example: **"Estimated default risk 2.1%, range 1.4%–2.8%. Delivery confirmation unavailable."**

This single UI element answers the problem statement's "distinguish verified from uncertain information" requirement more directly than anything else we build.

**Buyer-network risk propagation (optional, high-impact):** build a small graph of who owes whom. If a buyer starts paying late, propagate elevated risk to all suppliers depending on that buyer. Demo-able as a nice visual.

### 6.3 Suitability filter — who sees the opportunity

An opportunity is surfaced to a provider only if **all** of:

```
1. invoice.amount within [provider.min_ticket, provider.max_ticket]
2. invoice.amount <= provider.available_liquidity
3. PD_upper <= provider.risk_appetite_threshold
4. provider.current_exposure[sector] + amount
       <= provider.sector_limits[sector] * provider.portfolio_size
5. provider.current_exposure[buyer] + amount
       <= provider.buyer_limits * provider.portfolio_size
6. expected_return(PD, rate_floor) >= provider.target_return
```

**Do not skip rules 4 and 5.** They are the reason a provider will visibly decline a profitable-looking invoice in our demo — which is exactly the "portfolio constraints" requirement everyone else will hand-wave.

### 6.4 Provider agent bidding — with winner's-curse protection

Each agent, having decided to bid, constructs its offer:

**Base rate:**
```
required_rate = cost_of_funds
              + expected_loss(PD, 1 - recovery_rate)
              + capital_charge
              + target_margin
```

**Winner's-curse adjustment.** Because the auction winner tends to be whoever most underestimated the risk, each agent adds a shade proportional to uncertainty and to the number of competing bidders:

```
shade = k * uncertainty * log(1 + expected_competitors)
bid_rate = required_rate + shade
```

**Then the agent differentiates on non-price terms based on its own nature:**

- A **conservative bank** offers a lower advance rate but a competitive price, slower settlement.
- An **opportunistic fund** offers a high advance rate and same-day settlement at a higher price.
- A **fintech** offers speed and low fees but small ticket sizes.
- An **NBFC** sits in the middle with flexible repayment structures.

This is what creates a genuinely *multi-dimensional* offer set instead of five offers that differ only by 30 basis points.

**Allocation policy across the invoice stream (the bandit-with-knapsack part):**

Each agent must decide, over a stream of opportunities and a fixed budget, which to fund. It maintains an estimated value per opportunity type and selects to maximise expected risk-adjusted return per rupee of budget:

```
priority = (expected_return - expected_loss) / amount
         + exploration_bonus(times_this_segment_tried)
```

Budget depletes as deals are funded and replenishes as deals settle. **The visible consequence, which is great in a demo: as a provider's liquidity runs low, it bids more selectively and prices higher.** That is a live market responding to changing liquidity — a direct problem-statement requirement.

### 6.5 Clearing — stable matching, continuously

**Why not just "highest score wins"?** Because with many invoices and many providers competing simultaneously, a greedy pick creates unstable outcomes: a provider's capital gets committed to invoice A when it would rather have had invoice B, and the supplier of B would rather have had that provider.

**Use deferred acceptance:**

1. Each invoice (supplier side) proposes to its highest-scoring eligible offer.
2. Each provider tentatively holds the proposals it most prefers by risk-adjusted return, subject to its remaining budget, and rejects the rest.
3. Rejected invoices propose to their next-best offer.
4. Repeat until stable.

Result: a **stable match** — no supplier–provider pair would both prefer to defect. This is the Gale–Shapley algorithm, Nobel-recognised via Roth and Shapley in 2012. Say that on the slide.

**Continuous re-clearing.** Re-run clearing when any of these happen:
- a new invoice enters
- a provider's liquidity changes
- a supplier changes their priority sliders
- an offer expires
- a repayment or default is recorded

This is what makes the market "continuously clearing" rather than a one-shot auction — an explicit problem-statement requirement.

**Partial fills / syndication.** Allow an invoice to be funded by several providers in slices. This solves the thin-liquidity failure mode that killed The Receivables Exchange, and lets providers diversify. Implement as: if the top offer cannot cover the full amount, fill the remainder from the next-best offers, and compute a blended score.

### 6.6 Settlement state machine

```
   submitted
      │ verification passes
      ▼
   verified ──► rejected (fails IRN / duplicate detected)
      │ clearing produces a match
      ▼
   matched
      │ funding conditions satisfied (escrow, provider confirmation)
      ▼
   funded
      │ buyer pays on/before due date          │ buyer pays late      │ no payment
      ▼                                        ▼                      ▼
   settled                                    late                 defaulted
      │                                        │                      │
      └──────────────► LEARNING LOOP ◄─────────┴──────────────────────┘
```

**The key rule, stated in the problem statement:** a match is not complete just because an offer was selected. `matched` ≠ `funded` ≠ `settled`. Make these three states visibly distinct in the UI — most teams will collapse them into one.

### 6.7 The learning loop

When an outcome is recorded:

1. **Update the risk model** — that buyer's payment behaviour updates their profile; the effect propagates through the buyer graph to other invoices on the same buyer.
2. **Update provider agent beliefs** — the agent's estimate for that segment (sector × buyer grade × tenor band) moves toward the observed result.
3. **Release or consume liquidity** — settled deals return capital to the budget; defaults reduce it.
4. **Trigger re-clearing** — freed capital immediately gets reallocated to waiting opportunities.
5. **Recalibrate the uncertainty band** — if our predicted ranges were too narrow, widen them.

**Demo moment:** show a buyer paying 20 days late, then show every other invoice on that buyer being repriced and one provider withdrawing. That is the "dynamic reallocation" requirement made visible in ten seconds.

---

## 7. End-to-end flow, step by step

1. **Supplier submits an invoice.** Enters amount, buyer, due date, and uploads a document.
2. **Verification gate runs.** Mock IRN lookup returns valid/invalid. SHA-256 hash is computed and checked against the registry of already-financed invoices. Fields are tagged verified / inferred / unknown.
3. **Supplier states priorities.** Picks a preset or drags sliders. Sets hard constraints (minimum advance, maximum days to cash).
4. **Risk engine scores.** Produces PD with an uncertainty band and a plain-English summary of the main drivers.
5. **Discovery filter runs.** Of six providers, perhaps four are eligible. The UI *shows why the other two were excluded* — "Fund C: auto-components sector limit at 94%."
6. **Eligible agents generate offers.** Each returns a full multi-term offer, or declines with a reason.
7. **Scoring engine ranks them** by whole-offer value for this supplier, showing the arithmetic.
8. **Supplier drags a slider** — say, speed up — and the ranking visibly reorders live.
9. **Clearing engine runs deferred acceptance** across all live invoices and providers, producing stable matches.
10. **Match created.** State: `matched`.
11. **Funding conditions checked.** Escrow simulated, provider confirms. State: `funded`. Cash reaches supplier in the offered number of days.
12. **Buyer pays** (or is late, or defaults). State: `settled` / `late` / `defaulted`.
13. **Learning loop fires.** Risk model updates, agent beliefs update, liquidity returns, market re-clears.
14. **Go to 1**, forever. The market never stops.

---

## 8. Scope — build vs. don't build

### 8.1 Build (in priority order)

**P0 — without these we have nothing**
- Invoice intake form + mock IRN verification + duplicate-hash detection
- Field-level verified/inferred/unknown tagging with visible badges
- Whole-offer scoring engine with live sliders and transparent arithmetic
- 4–6 provider agents with genuinely different personalities and constraints
- Ranked offer list with plain-English "why this won" explanations

**P1 — this is where the novelty lands**
- Suitability filter with *visible exclusion reasons*
- Portfolio concentration limits causing a visible decline
- Winner's-curse bid shading
- Risk score with uncertainty band
- Deferred-acceptance clearing across multiple simultaneous invoices

**P2 — depth, if time allows**
- Settlement state machine with distinct matched/funded/settled states
- Learning loop with visible risk repricing after a late payment
- Liquidity depletion changing agent behaviour live
- Partial fills / syndication
- Buyer-network risk graph visualisation

**P3 — bonus**
- Inferred preferences via choice pairs (adaptive conjoint)
- Second-score pricing (winner pays the price that would have made the runner-up competitive)
- Market analytics dashboard

### 8.2 Do NOT build

| Don't build | Why |
|---|---|
| Real KYC / AML | Weeks of work, zero demo value |
| A blockchain or DLT layer | we.trade (liquidated 2022), Marco Polo (insolvent 2023) and Contour (wound down 2023) all failed *despite* this. It signals we haven't read the history. |
| Real bank / payment integrations | Impossible and unnecessary |
| A real credit bureau connection | Simulate it |
| User authentication and roles | Use a role-switcher dropdown |
| Free-form LLM negotiation between agents | Research shows agent-to-agent LLM negotiation is an imbalanced game where weaker agents lose money systematically. Our agents must bid **inside** the scoring mechanism, with bounded counter-offers. Use LLMs for explanation text and preference parsing only. |
| Mobile responsiveness | Demo is on a laptop |
| Deployment infrastructure | Run it locally |

---

## 9. Build plan

**Phase 1 (first ~8 hours) — a demoable MVP on its own**
Invoice intake, mock IRN, duplicate hash, field tagging, static risk score, scoring engine with sliders, two or three hand-built offers.
*Checkpoint: can we show a higher-rate offer winning because of speed and advance? If yes, we already have a submission.*

**Phase 2 (next ~12 hours) — the differentiation**
Provider agents with real constraint objects, suitability filter with visible exclusions, bid shading, uncertainty bands, deferred-acceptance clearing across several invoices.
*Checkpoint: can a provider visibly decline a profitable invoice because of a concentration limit?*

**Phase 3 (next ~10 hours) — the depth**
Settlement state machine, learning loop, liquidity dynamics, partial fills.
*Checkpoint: can a late payment visibly reprice other invoices and trigger reallocation?*

**Phase 4 (final hours) — the polish**
Scripted end-to-end demo, seeded data so numbers are memorable, explanation text, slides, and a rehearsed run-through. **Reserve at least three hours for this. A working system nobody understands loses to a simpler system explained well.**

*(See Section 9.5 for how these four phases map onto three people working in parallel rather than in sequence.)*

**Fallbacks, decided in advance:**
- If agent bidding is unstable → fall back to parameterised scripted offers. Keep the scoring engine as the star.
- If deferred acceptance is too complex → run repeated single-round auctions that visibly *re-clear* when conditions change. Still satisfies "dynamic, not one-time."
- If the learning loop won't finish → hard-code one scripted repayment event that triggers a visible repricing.

---

## 9.5 Splitting the work across three people

### 9.5.1 The thinking behind the split

Look back at the architecture in Section 4. It naturally separates into three vertical slices, and each one maps to a different *kind* of thinking:

- **The math brain** — turning invoices, offers and risk into numbers. This is Sections 6.1, 6.2, 6.3.
- **The market simulation** — the agents, the auction, the clock that keeps the market moving. This is Sections 6.4, 6.5, 6.6, 6.7.
- **The face of the product** — the thing judges actually watch. This is the frontend, the demo flow, the seeded data.

This is better than splitting "backend vs frontend vs database," because that split forces constant handoffs — the frontend person is blocked until the backend person finishes an endpoint, who is blocked until someone defines the data model. Instead, split by **owned outcome**: each person can build and test their piece almost independently, using fake data for the parts they don't own yet, and the three pieces snap together because Section 5 (the data model) is agreed on Day 1 and never changes.

**The one rule that makes this work:** everyone reads Sections 3 and 5 (glossary and data model) before writing any code, and agrees on the shape of `Invoice`, `Offer`, `CapitalProvider`, and `Match` objects as literal JSON before splitting up. Once those shapes are frozen, all three people can build against them in parallel using mock data.

### 9.5.2 Person A — "The Scorer" (owns Sections 6.1, 6.2, 6.3)

**One-line mission:** given an invoice and a set of offers, produce a ranked list with honest numbers and plain-English reasons.

**Owns:**
- The whole-offer value score (Section 6.1) — normalisation, weights, sliders, presets
- The risk engine with uncertainty bands (Section 6.2)
- The suitability filter that decides who sees an opportunity (Section 6.3)
- The verification gate (IRN mock + duplicate hash + field tagging) — logically part of this slice since it also just produces trust signals on the invoice

**Builds as one clean module,** e.g. `scoring.py`, with functions like:
```
verify_invoice(invoice) -> VerificationResult
score_risk(invoice, supplier, buyer) -> RiskProfile
filter_eligible_providers(invoice, risk, providers) -> list[CapitalProvider]
score_offer(offer, invoice, supplier_preferences) -> ScoredOffer
```

**Can work entirely standalone:** write these as pure functions that take the agreed data shapes in and return scores out. Test with hand-written fake invoices and fake offers — doesn't need Person B's agents to be built yet, and doesn't need Person C's UI to exist.

**Hardest, most important part of the job:** making the explanation text genuinely readable — "This offer costs ₹3,100 more but delivers ₹50,000 more cash, two days sooner" — not just a score. This is the line judges will remember.

**This is the best-suited role for whoever is strongest at math/stats or is most comfortable translating a formula into readable code.**

### 9.5.3 Person B — "The Market Maker" (owns Sections 6.4, 6.5, 6.6, 6.7)

**One-line mission:** simulate a living market — agents that bid, a clock that clears trades, and a memory that learns.

**Owns:**
- Provider agent objects with personalities (conservative bank, opportunistic fund, fintech, NBFC) and their bidding logic, including winner's-curse shading
- The clearing engine (deferred acceptance / continuous re-clearing)
- The settlement state machine (matched → funded → settled/late/defaulted)
- The learning loop that updates risk and reallocates capital after an outcome

**Builds as one clean module,** e.g. `market.py`, with functions/classes like:
```
class ProviderAgent:
    def evaluate(invoice, risk_profile) -> Offer | None

run_clearing(invoices: list, providers: list[ProviderAgent]) -> list[Match]
advance_settlement(match, event) -> Match   # state transitions
apply_outcome(match, outcome) -> None       # triggers learning loop
```

**Can work entirely standalone:** this person can build and test the *whole market* — agents bidding, deals clearing, settlement advancing, capital reallocating — using Person A's scoring functions once they're frozen (or mocked with a dummy scorer that just returns `amount * rate` early on), and without any UI at all. Success is measurable by printing match outcomes to the console or a log file.

**Hardest, most important part of the job:** making four provider agents feel genuinely different from each other, and making the "decline due to concentration limit" moment actually fire in the demo data. This is the single most novel-looking behaviour in the whole system — worth extra time.

**This is the best-suited role for whoever is strongest at writing clean logic/state machines, or enjoys game-like simulation code.**

### 9.5.4 Person C — "The Storyteller" (owns the frontend, demo data, and pitch)

**One-line mission:** make the market visible, make the numbers land, and make the four-minute demo unforgettable.

**Owns:**
- The React frontend: invoice submission form, verification badges, risk display with uncertainty range, the live slider ranking view, the eligible/excluded provider list with reasons, the match/funded/settled state visualisation
- The seeded demo dataset (Section 12's Sharda/TataCorp example, plus 2–3 backup invoices in case something needs re-running live)
- The demo script itself (Section 10) — rehearsing it, timing it, building the slide with the novelty statement (Section 13)
- Wiring the frontend to Person A's and Person B's modules once they're ready (via a thin FastAPI layer exposing their functions as endpoints)

**Can work entirely standalone at first:** build the entire UI against **hand-written mock JSON** matching the agreed data shapes from Section 5 — a fake list of offers, a fake risk profile, a fake match history. The sliders can reorder mock offers before there's a real scoring engine behind them. This means the UI is fully clickable and demo-able on Day 1, and swapping mock data for real API calls near the end is a small, low-risk step, not a last-minute scramble.

**Hardest, most important part of the job:** the live slider re-ranking moment (Section 10, the "2:15 — the money moment") has to be smooth and instant — no lag, no flicker. This is the visual centrepiece of the whole pitch, so it deserves the most polish time of anything in the UI.

**This is the best-suited role for whoever is strongest at frontend/design, or is the most naturally persuasive presenter — since they'll likely also be the one presenting or co-presenting.**

### 9.5.5 How the three pieces meet

```
Person C's UI  ──calls──►  thin FastAPI layer  ──calls──►  Person A's scoring.py
                                                 ──calls──►  Person B's market.py
```

Person A and Person B's modules never need to call each other directly during early development — Person B's clearing engine calls Person A's `score_offer()` as a function, but both can be stubbed with a one-line fake return value (`return {"score": 0.7, "reason": "placeholder"}`) until the real one is ready. This means **all three people can be productive from hour one**, and integration is a matter of swapping stubs for real functions, not building things in sequence.

### 9.5.6 Suggested checkpoints

- **End of Phase 1 (~hour 8):** Person A's scoring works standalone on fake data; Person B's market prints match results to console on fake data; Person C's UI is fully clickable on mock JSON. **First integration:** wire Person C's slider UI to Person A's real scoring function. This alone is a demoable submission if nothing else finishes.
- **End of Phase 2 (~hour 20):** Person B's agents and clearing are live; Person C wires the eligible/excluded provider list and the offer ranking to real data from both A and B.
- **End of Phase 3 (~hour 30):** settlement states and the learning loop are live; Person C wires the match-state visualisation and the late-payment repricing demo.
- **Final hours:** all three people stop building and rehearse the demo together, using Section 10's script. Nobody writes new code once rehearsal starts.

## 10. Demo script (target: 4 minutes)

**0:00 — The hook.** "Sharda Auto Components has a ₹10 lakh invoice and payroll on Friday. Five lenders are willing to fund it. Every existing marketplace would hand her the 8.2% offer. That is the wrong answer, and we can prove it."

**0:30 — Verification.** Submit the invoice. IRN validates. Show the field badges: amount verified, GST verified, **delivery confirmation unknown**. Then submit the *same* invoice again from a different supplier account — **duplicate financing detected and blocked.** (Fast, visual, and it shows we understand real fraud.)

**1:15 — Risk with honesty.** "Default risk 2.1%, range 1.4% to 2.8% — the range is wide because delivery is unconfirmed." Point out that we show uncertainty rather than hiding it.

**1:45 — Discovery.** Six providers, four eligible. Show the exclusion reasons on screen: *"Fund C excluded — auto-components exposure at 94% of limit."* Say: "This is a portfolio constraint. A real fund would decline this deal, and our market knows that."

**2:15 — The money moment.** Four offers appear, all genuinely different. The lowest rate is 8.2%. Now drag the **speed** slider up. **The ranking reorders live** and an 8.6% offer moves to the top. Read the explanation aloud: *"This offer costs ₹3,100 more but delivers ₹50,000 more cash, two days sooner."*

**3:00 — Clearing and settlement.** Show three invoices clearing simultaneously into stable matches. Show the state machine: matched → funded → settled. Emphasise: "Selecting an offer is not financing. Cash landing is financing."

**3:30 — The loop.** Trigger a late payment on buyer TataCorp. Watch risk scores on other TataCorp invoices rise, one provider withdraw, and capital reallocate automatically.

**3:50 — The close.** Read the novelty statement.

**Rules for the demo:** seed the data so the numbers are always the same. Rehearse it five times. Never let the demo depend on live model training.

---

## 11. Objection handling — what judges will ask

**"TReDS already does this."**
> TReDS runs a reverse auction on one variable — the rate — and requires the buyer to accept the invoice first. We compete on the whole offer, weighted by the supplier's own priorities, with providers bidding under live portfolio constraints, and we re-clear continuously with a learning loop. Those four things are not in TReDS.

**"Isn't this just a weighted average?"**
> The weighted score is the visible surface. Underneath it are three things a weighted average cannot do: hard-constraint filtering, portfolio-aware provider bidding with winner's-curse shading, and stable matching across simultaneous invoices. It is a scoring-rule auction in the sense of Che's multi-attribute auction theory, not a spreadsheet.

**"Suppliers won't know their own weights."**
> Correct, which is why we ship three presets and can infer weights from a few binary choices — simplified conjoint analysis. Sliders are for the demo; presets are for reality.

**"Can suppliers game the weights?"**
> Weights only affect which offer *they* receive. Misstating priorities gives them an offer they like less. There is no incentive to lie. Providers, meanwhile, are protected by second-score-style pricing and bid shading.

**"How do you actually verify an invoice?"**
> Honestly and partially. An IRN proves the invoice was reported to GST. It does not prove goods were delivered — so we label that field `unknown` and widen the risk band. We also fingerprint the document to block duplicate financing, the approach used in production trade-finance registries. We do not claim fraud is solved; Greensill and Stenn collapsed partly on receivables that were weak or did not exist, and claiming certainty here would be the wrong lesson to take from that.

**"Is this legal in India?"**
> We are an intelligence and matching layer, not a lender. Financing is executed by regulated entities — banks and NBFC-Factors — consistent with the Factoring Regulation Act and RBI's rules on who may finance receivables, and consistent with the OCEN model where a Loan Service Provider intermediates but licensed lenders lend. Data flows would run on consent-based rails under the Account Aggregator framework and DPDP Act 2023. We do not lend, hold deposits, or take custody of funds.

**"Why won't a competitor build this?"**
> Most will build a rate auction, because that is what the phrase "competitive marketplace" suggests. The combination of multi-attribute scoring, portfolio-constrained agent bidding, stable continuous clearing, and settlement-gated learning is four separate pieces of theory. Any one is copyable in a weekend. All four together are not.

**"What breaks in the real world?"**
> Thin liquidity. The Receivables Exchange pioneered single-invoice auctions and closed because it could never line up enough committed capital. That is why we built partial fills and syndication in from the start, and why our discovery engine actively surfaces opportunities to suitable providers rather than broadcasting to everyone.

---

## 12. Appendix — the worked example (memorise these numbers)

**The supplier:** Sharda Auto Components, Pune. MSME, 7 years operating, auto-components sector.
**The invoice:** ₹10,00,000 on buyer TataCorp (strong credit, AA grade), 60-day tenor, IRN verified, delivery confirmation unavailable.
**Her situation:** payroll due in 4 days. She needs maximum cash, fast. Cost matters, but less.
**Her priorities:** speed high, advance high, cost medium. Hard constraint: at least 70% advance, cash within 5 days.
**Her risk profile:** PD 2.1%, range 1.4%–2.8% (widened because delivery is unconfirmed).

**The offers:**

| Provider | Rate | Advance | Settles in | Fees | Structure | All-in cost | Cash now | Whole-offer score |
|---|---|---|---|---|---|---|---|---|
| Bank A | 9.0% | 80% | 3 days | 0.5% | Bullet | ₹16,830 | ₹8,00,000 | 0.71 |
| NBFC B | **8.2%** | 70% | 2 days | 0.8% | Bullet | ₹17,430 | ₹7,00,000 | 0.64 |
| Fund C | 8.6% | 90% | Same day | 0.4% | Bullet | ₹16,720 | ₹9,00,000 | **0.89** |
| Fintech D | 9.4% | 75% | 1 day | 0.3% | Instalment | ₹14,580 | ₹7,50,000 | 0.68 |

*(All-in cost = advance × rate × 60/365 + fees. Note that the "cheapest rate" offer, NBFC B, is not even the cheapest in rupees, because its lower advance and higher fees change the arithmetic. This is a great line to deliver out loud.)*

**What a normal marketplace does:** picks NBFC B at 8.2%. Sharda gets ₹7,00,000 in two days.

**What FitFuse does:**
1. Scores Fund C highest at 0.89 — it delivers ₹2,00,000 more cash, same day, and actually costs slightly *less* in rupees than the "cheapest rate" offer.
2. But Fund C's agent checks its own limits: auto-components exposure is at 94% of its 20% sector cap. It can only commit ₹6,00,000, not the full ₹9,00,000.
3. **Partial fill:** the clearing engine syndicates — Fund C takes ₹6,00,000 at its terms, Bank A takes the remaining ₹3,00,000 at a slightly adjusted rate.
4. **Outcome:** Sharda receives ₹9,00,000 — ₹2,00,000 more than the naive answer — with the bulk arriving same-day. Blended all-in cost roughly ₹16,750. Both providers stay inside their risk limits.
5. **Then:** TataCorp pays 5 days late. The learning loop nudges TataCorp's payment-delay profile, widens risk bands on three other TataCorp invoices in the market, and Fund C's agent reprices its next bid on that buyer upward by 15 basis points. Capital freed from a settled deal elsewhere is reallocated within seconds.

**The one-line summary for the slide:**
> Lowest rate: ₹7,00,000 in 2 days. FitFuse: ₹9,00,000 same day, for less money. Same invoice, same lenders, better market.

---

## 13. The novelty statement (for the presentation)

> Every existing invoice marketplace — TReDS, OCEN, C2FO — makes capital providers compete on one number: price. FitFuse is the first agentic clearinghouse where providers compete on the **whole offer** — rate, advance, speed, fees and structure — scored against each supplier's own stated priorities; where every provider agent bids under real liquidity and portfolio-concentration limits and shades its bid to avoid the winner's curse; and where matches are **stable, continuously re-cleared, and only complete when cash actually settles** and the market learns from the outcome.

**The short version, if you only get one sentence:**
> We turned invoice financing from a price auction into a fit auction.

---

## 14. Honest caveats to state out loud

Judges trust teams that name their own limits.

- An IRN proves an invoice was reported to the GST system. It does not prove goods were delivered. No registry fully eliminates fraud, and we do not claim otherwise.
- All data in the prototype is synthetic. The risk model demonstrates the mechanism, not production accuracy.
- Market statistics we quote (the roughly $2.5 trillion global trade finance gap; India's MSME credit gap of around ₹28 lakh crore) are survey and model estimates, not measurements.
- We are not a lender. A real deployment would require licensed financing partners and would sit under RBI's factoring and digital-lending rules.
- Thin liquidity is the historical killer of invoice marketplaces. Our syndication design addresses it; it does not guarantee it away.
