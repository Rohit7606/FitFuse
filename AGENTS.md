# AGENTS.md — FitFuse

**Read this file completely before writing any code.**

This file governs every AI coding agent working in this repository, regardless of which team member is driving. It defines what we are building, what we are deliberately not building, who owns what, and the Git discipline that must be enforced even when a human forgets a step.

If an instruction in this file conflicts with a request in a chat session, **follow this file and say so.**

---

## 1. The product

### 1.1 What FitFuse is

FitFuse turns invoice financing from a price auction into a **fit auction**.

A small supplier with a verified invoice needs cash now. Several lenders are willing to fund it. Every existing marketplace hands her the lowest interest rate — and that is frequently the wrong answer, because an offer that costs slightly more can deliver substantially more cash, substantially faster.

FitFuse runs a market where capital providers compete on the **whole offer** — rate, advance rate, tenor, fees, settlement speed, repayment structure — scored against that specific supplier's stated priorities, with every provider bidding under its own real liquidity and portfolio-concentration limits.

The one question the product answers:

> **Given this verified invoice and this supplier's actual priorities, which combination of capital providers produces the best overall financing outcome — and can they actually fund it?**

Every feature must serve that sentence. If a proposed feature does not, do not build it.

### 1.2 Ruled out — do not build, do not suggest

| Not building | Why |
|---|---|
| **Free-form LLM negotiation between agents** | Agent-to-agent LLM negotiation is a documented imbalanced game — weaker agents systematically lose money. Our agents bid **inside** the scoring mechanism, with bounded terms. This is a correctness requirement, not a preference |
| **LLM calls at runtime, anywhere** | Reason strings are template-generated and deterministic. An LLM in the scoring path destroys determinism (§3.1) and reproducibility on stage |
| **Runtime model training** | The risk scorecard is a transparent set of committed coefficients in `engine/config.py`. See §1.5 |
| **Blockchain / distributed ledger** | we.trade, Marco Polo and Contour all folded despite it. Building one signals we have not read the history |
| **Real KYC / AML / credit-bureau integration** | Weeks of work, zero demo value. Simulated |
| **Real payment rails or bank APIs** | Settlement is a simulated state machine |
| **Login, auth, user accounts, RBAC** | Supplier / provider / market views are a client-side toggle |
| **Document upload, OCR, PDF parsing at runtime** | Invoice fields arrive structured. Live parsing adds failure risk and zero value |
| **Database servers (Postgres, Mongo, Redis)** | JSON files on disk. A database adds operational risk, not capability |
| **Websockets, background jobs, real-time streaming** | Everything is request/response and stateless |
| **Mobile app** | No |

If asked to implement anything on this list, **stop and ask why** before writing code.

### 1.3 The canonical demo

All three tracks build toward one scenario, defined in `DEMO_SCENARIO.md`:

> verified invoice → risk with honest uncertainty → eligible providers discovered → competing multi-term offers → priorities change the winner → syndicated match → settlement → the market learns

Entity IDs, amounts and the exact sequence are fixed in that file. Do not invent alternative demo data.

### 1.4 Data — critical boundary

**All three tracks build against mock data** generated locally by `engine/mockgen.py`, conforming to the frozen contract in `SCHEMA.md`.

There is no real dataset and no collection workstream. Invoice-level supply-chain finance data is not publicly available, and we do not pretend otherwise. If a session drifts toward "let me look up real invoice data" — stop. It does not exist in a usable form, and inventing a source is worse than a clearly-labelled simulation.

**Every number on screen must be honestly labelled as simulated.** See §3.7.

### 1.5 The risk model — a deliberate constraint

`engine/risk.py` uses a **transparent scorecard**: hand-set coefficients, committed in `engine/config.py`, applied as a weighted logistic. Not a trained model.

Why:

- **Determinism.** A model retrained at runtime produces different numbers between demo runs
- **Explainability.** Every factor's contribution is readable directly off the coefficients, which is what makes `reason_text` honest rather than reverse-engineered
- **Defensibility.** "We chose these weights and here is why" survives a judge's question. "The model learned it" does not, on synthetic data

Training a model offline and committing the resulting coefficients is permitted. Training at import time or request time is not.

---

## 2. Repository structure

```
fitfuse/
├── AGENTS.md                  # this file — shared, no single owner
├── SCHEMA.md                  # the contract — shared, no single owner
├── schema.json                # machine-readable contract — shared
├── DEMO_SCENARIO.md           # fixed demo fixture spec — shared
├── docs/
│   ├── PERSON_A.md            # valuation engine brief
│   ├── PERSON_B.md            # market simulator + API brief
│   └── PERSON_C.md            # frontend brief
├── engine/                    # OWNER: Person A — the valuation brain
│   ├── __init__.py
│   ├── verify.py              # IRN check, duplicate hash, field tagging
│   ├── risk.py                # default probability + uncertainty band
│   ├── eligibility.py         # who may see this opportunity, and why not
│   ├── scoring.py             # whole-offer value score
│   ├── reasons.py             # template-generated explanations
│   ├── assess.py              # the single public entry point
│   ├── config.py              # all tunable constants, one place
│   └── mockgen.py             # synthetic market generator
├── market/                    # OWNER: Person B — the market simulator
│   ├── __init__.py
│   ├── agents.py              # provider bidding policies
│   ├── clearing.py            # deferred-acceptance matching, syndication
│   ├── settlement.py          # state machine
│   ├── learning.py            # outcome feedback and reallocation
│   └── simulate.py            # the single public entry point
├── api/                       # OWNER: Person B
│   ├── __init__.py
│   ├── main.py                # FastAPI app
│   ├── models.py              # pydantic request/response models
│   └── errors.py
├── web/                       # OWNER: Person C
│   ├── src/
│   ├── public/
│   └── package.json
├── data/                      # OWNER: Person A
│   ├── mock/
│   │   └── market.json        # generated, committed
│   └── fixtures/
│       └── demo_scenario.json # the canonical demo, committed
└── tests/
    ├── engine/                # OWNER: Person A
    ├── market/                # OWNER: Person B
    ├── api/                   # OWNER: Person B
    └── web/                   # OWNER: Person C
```

### 2.1 Ownership table

| Path | Owner | Reviewer required |
|---|---|---|
| `engine/` | Person A | Person B |
| `data/` | Person A | Person B |
| `market/` | Person B | Person A |
| `api/` | Person B | Person A |
| `web/` | Person C | Person B |
| `tests/engine/` | Person A | Person B |
| `tests/market/`, `tests/api/` | Person B | Person A |
| `tests/web/` | Person C | Person B |
| `SCHEMA.md`, `schema.json` | **shared — no single owner** | **both others** |
| `DEMO_SCENARIO.md` | **shared — no single owner** | **both others** |
| `AGENTS.md` | **shared — no single owner** | **both others** |

**Why `engine/` and `market/` are separate owners.** The valuation logic (what is this worth, to whom, and why) and the market mechanics (who bids, who clears, what settles) are different kinds of thinking and different failure modes. Splitting them lets two people work at full speed, and it forces the seam between them to be an explicit function signature rather than a shared mental model.

---

## 3. Hard rules

These are enforced by the agent, not left to memory.

### 3.1 Determinism is mandatory

**The same input must always produce byte-identical output.** A judge will drag the preference slider back and forth on stage. If the ranking flickers between runs at the same slider position, the product looks broken.

Concretely:

- **No `random` at runtime.** Randomness is permitted only inside `engine/mockgen.py`, and only with a seed fixed in `engine/config.py`
- **No `datetime.now()` or `uuid4()` inside scoring or clearing paths.** Timestamps belong in `meta`, generated once at data-build time
- **No iteration over unordered collections.** Sort by ID before any loop whose order could affect output
- **Round consistently.** Monetary outputs to 2 decimal places, scores and rates to 4, using `round()` at serialisation only — never mid-calculation
- **No parallelism** in scoring or clearing. Floating-point reduction order changes results
- **Deferred acceptance must have a deterministic tiebreak.** Ties on score break by ID ascending, always

Any PR touching `engine/` or `market/` must show that running the same input twice gives identical JSON.

### 3.2 The contract is frozen

`SCHEMA.md` and `schema.json` define the boundary between all three tracks. They may be changed — but only deliberately.

- **Never change a field name, type, or meaning without both other team members knowing.** See §4.3
- **Additive changes are cheap.** Adding an optional field breaks nobody. Prefer this
- **Removing or renaming a field is expensive.** It breaks two other people's work silently
- Every change bumps `meta.schema_version` and adds a line to the changelog at the bottom of `SCHEMA.md`

### 3.3 Nobody blocks on anybody

Each track must be independently runnable from the first commit.

- Person A runs assessment and scoring on `data/mock/market.json` with no API and no frontend
- Person B runs the simulator against A's engine, or against a stub scorer if the engine is mid-change
- Person C runs the frontend against committed mock API responses in `web/src/mocks/`, with a single flag to switch to the live API

**If any track ever says "I'm blocked waiting for X," that is a design failure, not a scheduling problem.** Fix the seam.

### 3.4 Stateless API

The server holds no session state. The client sends the full market scenario with every request and receives a complete result.

- No server-side scenario storage, no session IDs, no in-memory mutation between requests
- Match state, settlement state and learned adjustments live in the request body, not on the server
- A page refresh or a backend restart mid-demo must lose nothing the client cannot immediately re-send
- Caching is permitted only as a pure function of the request body

**This matters more here than in most projects.** The demo walks a market forward through several states — offers, match, funding, settlement, learning. A stateful server would make step 7 depend on steps 1–6 having run cleanly. Statelessness means any step can be re-entered directly.

### 3.5 Currency, rates and units

- **All monetary values in the runtime contract are ₹ lakh, as floats.** Field names carry a `_lakh` suffix. No exceptions in the contract layer
- A ₹10,00,000 invoice is `10.00`. A provider with ₹50 crore of liquidity is `5000.00`
- **Rates and percentages are stored as decimal fractions, never as percent numbers.** 8.8% p.a. is `0.088`. An 85% advance rate is `0.85`
- **Tenor and settlement speed are integer days.** Never fractional, never hours
- Display formatting is a **frontend concern only** — the UI may render `5000.00` as `₹50 cr`. Nothing in `engine/`, `market/` or `api/` ever converts units

### 3.6 Missing versus zero versus unverified

Three distinct states. Conflating them is the fastest way to make the risk model dishonest.

- `null` — the field was not provided at all
- `0` / `0.0` — the value is explicitly zero
- **`field_confidence` tag** — separately records whether a *present* value is `verified`, `inferred`, or `unknown`

A supplier who declares zero prior defaults is not the same as one who did not answer. An invoice amount confirmed against the IRN is not the same as one typed in unverified. Any code branching on these must handle all three explicitly.

### 3.7 Honesty about simulation

Every entity carries `data_source: "synthetic"`. The UI must always show it.

We are demonstrating a mechanism on simulated data, and saying so plainly is a strength — it is the difference between a credible prototype and a team that gets caught overclaiming in Q&A. Never imply a number is measured when it is generated. Never name a real company.

---

## 4. Git workflow — follow this exactly, every time

This section exists so the agent enforces version-control discipline even if a human forgets a step.

### 4.1 Branch naming

- Person A: `a/<short-description>` — e.g. `a/whole-offer-score`
- Person B: `b/<short-description>` — e.g. `b/deferred-acceptance`
- Person C: `c/<short-description>` — e.g. `c/preference-sliders`
- Pairing branches: `ab/<description>`, `bc/<description>`, `ac/<description>` — used for integration work and anything else two people write together

The prefix alone should make it obvious whose track a branch belongs to — never branch without it.

### 4.2 The loop, in order — do not skip steps

1. `git pull origin main` — always, before creating a new branch
2. `git checkout -b <prefix>/<description>`
3. Work, commit in small increments (see §4.4 for message format)
4. `git push origin <branch-name>`
5. Open a PR. Determine the required reviewer from the ownership table in §2.1 and **name them in the PR description, with which area triggered it.** Do not let it merge without that review
6. After merge, **all three** run `git pull origin main` before starting the next branch

### 4.3 Rules the agent should actively enforce

- **Never commit directly to `main`.** If asked to make a change, create a branch first
- **Never suggest force-pushing** to a shared branch
- If a change touches `SCHEMA.md`, `schema.json`, or `DEMO_SCENARIO.md`, **pause and confirm both other team members are aware** before committing. These files have no single owner
- If a PR diff touches more than one person's owned folder, **flag it explicitly and name the folders** — it likely means the work should have been split differently, or a shared contract needs updating first
- If a PR touches `engine/` or `data/`, require review from **Person B** specifically — even if the author is Person C
- Pairing branches still need the **third** person's review before merge
- Keep commits scoped to one logical change
- If asked to implement something in the §1.2 ruled-out list, **stop and ask why** before writing code

### 4.4 Commit message convention

```
feat: add concentration-limit check to eligibility filter
fix: prevent fit score exceeding 1.0 when all offers tie
chore: pin numpy version for reproducible rounding
docs: update SCHEMA with syndication fields
test: add two-run determinism harness for clearing
data: regenerate mock market with seed 42
```

### 4.5 Before opening a PR — confirm this checklist, don't just push

**General:**

- [ ] Runs without errors (`python -m engine.assess data/mock/market.json` / `uvicorn api.main:app` / `npm run build`)
- [ ] Linter clean (`ruff check .` for Python, `npm run lint` for web)
- [ ] Commit messages follow §4.4
- [ ] PR description names the required reviewer per §2.1, and which area triggered it
- [ ] No new dependency added without saying why in the PR description

**If the PR touches `engine/`:**

- [ ] Same input twice produces **byte-identical** JSON (§3.1)
- [ ] No `random`, `datetime.now()`, or `uuid4()` outside `mockgen.py`
- [ ] All loops over invoices/providers/offers sorted by ID before iteration
- [ ] Every score confirmed within `[0.0, 1.0]`
- [ ] Every scored offer has a non-empty `reason_text`
- [ ] Every excluded provider has a non-empty `exclusion_reason`
- [ ] Hard constraints (`min_advance_rate`, `max_days_to_cash`) filter **before** scoring, not after
- [ ] `null`, `0.0` and `field_confidence` handled distinctly (§3.6)

**If the PR touches `market/`:**

- [ ] Clearing terminates — deferred acceptance provably halts
- [ ] Tiebreaks are by ID ascending (§3.1)
- [ ] No provider is ever allocated beyond `available_liquidity_lakh`
- [ ] No provider is ever allocated beyond a sector or buyer concentration limit
- [ ] Syndicated allocations sum to exactly the requested advance amount
- [ ] Settlement states transition only along the legal paths in `SCHEMA.md` §4.6

**If the PR touches `api/`:**

- [ ] All five endpoints respond to the shapes in `SCHEMA.md` §5
- [ ] Response validated against `schema.json` in a test
- [ ] No server-side state introduced (§3.4)
- [ ] Malformed request body returns 422 with a readable message, not a 500
- [ ] Unknown ID in a request returns 400 naming the offending ID
- [ ] CORS still permits the frontend dev origin

**If the PR touches `web/`:**

- [ ] Runs against committed mocks with the API switched off
- [ ] Runs against the live API with the flag flipped
- [ ] No `localStorage` / `sessionStorage` usage
- [ ] Every number displayed carries its unit (₹ lakh / ₹ cr, %, days)
- [ ] Every entity shows its `data_source` badge
- [ ] Reason text and exclusion reasons displayed in full, never truncated

**If the PR touches `SCHEMA.md` / `schema.json` / `DEMO_SCENARIO.md`:**

- [ ] `meta.schema_version` bumped
- [ ] Changelog line added at the bottom of `SCHEMA.md`
- [ ] Both other team members named in the PR description
- [ ] `data/mock/market.json` regenerated if the input shape changed
- [ ] Frontend mocks in `web/src/mocks/` updated to match

**If the PR touches `data/fixtures/demo_scenario.json`:**

- [ ] The demo still runs end to end — verification, exclusions, offer ranking, slider flip, syndication, settlement, learning
- [ ] Entity IDs still match those named in `DEMO_SCENARIO.md`

---

## 5. Setup and commands

### 5.1 Python (engine + market + api)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` is intentionally short. Do not add to it without justification in the PR:

```
numpy
fastapi
uvicorn
pydantic
pytest
ruff
jsonschema
```

**Note what is absent.** No pandas — we do not read CSVs. No scikit-learn — the scorecard is committed coefficients (§1.5). No networkx — the buyer graph is small enough to hand-roll, and adding a graph library for one adjacency lookup is not worth the dependency.

### 5.2 Common commands

```bash
# regenerate the mock market (Person A)
python -m engine.mockgen --seed 42 --out data/mock/market.json

# assess an invoice and print the ranked offers
python -m engine.assess data/mock/market.json --invoice INV001

# run the market simulator end to end (Person B)
python -m market.simulate data/mock/market.json

# determinism check
python -m engine.assess data/mock/market.json --invoice INV001 > /tmp/run1.json
python -m engine.assess data/mock/market.json --invoice INV001 > /tmp/run2.json
diff /tmp/run1.json /tmp/run2.json && echo "DETERMINISTIC"

# run the API
uvicorn api.main:app --reload --port 8000

# tests
pytest tests/ -v

# lint
ruff check .
```

### 5.3 Web

```bash
cd web
npm install
npm run dev        # uses committed mocks by default
npm run dev:live   # points at http://localhost:8000
npm run build
npm run lint
```

---

## 6. Phases

Milestone-based, not date-based. A phase is complete when its exit criteria are met by all three tracks.

### Phase 0 — Contract freeze

**Exit criteria:**
- `SCHEMA.md` and `schema.json` agreed and committed by all three
- `data/mock/market.json` generated and committed
- `data/fixtures/demo_scenario.json` committed
- `web/src/mocks/` populated with hand-written responses matching the contract
- B's five endpoints stubbed and returning valid static responses
- All three can run their own track locally with zero dependency on the others

Nothing else starts until this is done.

### Phase 1 — Independent build

Each track builds its core against mocks. No cross-track dependencies.

**Exit criteria:**
- A: `assess.py` produces verification, risk and ranked scored offers from `data/mock/market.json`
- B: all five endpoints return contract-valid responses using a stubbed or real engine; agents generate differentiated offers
- C: offer list, preference sliders and provider panel render from committed mocks

### Phase 2 — First integration

**This happens early and deliberately, not at the end.** Even a partly broken engine is worth wiring up.

**Exit criteria:**
- C's frontend hits B's live API
- B's simulator calls A's real engine
- One invoice flows end to end, even if the numbers are wrong
- The slider visibly reorders offers against live data

### Phase 3 — The demo path

Everything focuses on `DEMO_SCENARIO.md` working perfectly.

**Exit criteria:**
- Full eight-step demo runs without a manual intervention or a refresh
- Verification, exclusions, slider flip, syndication, settlement and learning all correct
- Determinism check passes
- The naive-market counterfactual toggle works

### Phase 4 — Hardening

Error states, edge cases, presentation polish, rehearsal.

---

## 7. Style

- Python: type hints on every public function. Docstrings on modules and public functions only, not on obvious internals
- Constants live in `engine/config.py` with a one-line comment explaining what each one means and why it has that value. No magic numbers scattered through the code
- **`market/` imports constants from `engine/config.py`.** There is exactly one config file. Two would drift
- Prefer boring, explicit code over clever code. Someone else has to explain this to a judge under pressure
- Comments explain *why*, not *what*. If the code needs a comment to explain what it does, rewrite the code

---

## 8. Changelog

| Version | Change |
|---|---|
| 1.0 | Initial. Project renamed FitMarket → FitFuse. Intelligence layer split into `engine/` (Person A) and `market/` (Person B) |
