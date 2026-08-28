# FitFuse

> **The cheapest offer is not the best offer. We built the market that knows the difference.**

An agentic multi-dimensional clearinghouse for supply-chain working capital.  
**CSI ORIGIN 2026 — Problem Statement #5**

---

## What FitFuse does

A small supplier with a verified invoice needs cash now. Several lenders are willing to fund it. Every existing marketplace hands her the lowest interest rate — and that is frequently the wrong answer, because an offer that costs slightly more can deliver substantially more cash, substantially faster.

FitFuse runs a market where capital providers compete on the **whole offer** — rate, advance rate, tenor, fees, settlement speed, repayment structure — scored against that specific supplier's stated priorities, with every provider bidding under its own real liquidity and portfolio-concentration limits.

**All data in this prototype is synthetic.** See `AGENTS.md` §3.7.

---

## Repository structure

```
fitfuse/
├── AGENTS.md                  # Shared project governance — read first
├── SCHEMA.md                  # Data contract — shared, no single owner
├── schema.json                # Machine-readable contract
├── DEMO_SCENARIO.md           # Fixed demo fixture spec
├── docs/
│   ├── PERSON_A.md            # Valuation engine brief
│   ├── PERSON_B.md            # Market simulator + API brief
│   ├── PERSON_C.md            # Frontend brief
│   └── CONTEXT.md             # Full project context
├── engine/                    # OWNER: Person A — the valuation brain
│   ├── config.py              # All tunable constants, one place
│   ├── verify.py              # IRN check, duplicate hash, field tagging
│   ├── risk.py                # Default probability + uncertainty band
│   ├── eligibility.py         # Who may see this opportunity, and why not
│   ├── scoring.py             # Whole-offer value score
│   ├── reasons.py             # Template-generated explanations
│   ├── assess.py              # The single public entry point
│   └── mockgen.py             # Synthetic market generator
├── market/                    # OWNER: Person B — the market simulator
│   ├── agents.py              # Provider bidding policies
│   ├── clearing.py            # Deferred-acceptance matching, syndication
│   ├── settlement.py          # State machine
│   ├── learning.py            # Outcome feedback and reallocation
│   └── simulate.py            # The single public entry point
├── api/                       # OWNER: Person B
│   ├── main.py                # FastAPI app
│   ├── models.py              # Pydantic request/response models
│   └── errors.py              # Exception → HTTP status mapping
├── web/                       # OWNER: Person C
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── mocks/             # Hand-written API response mocks
│   │   └── utils/             # API client, formatting helpers
│   ├── public/
│   └── package.json
├── data/
│   ├── mock/
│   │   └── market.json        # Generated, committed
│   └── fixtures/
│       └── demo_scenario.json # The canonical demo, committed
├── tests/
│   ├── engine/                # OWNER: Person A
│   ├── market/                # OWNER: Person B
│   ├── api/                   # OWNER: Person B
│   └── web/                   # OWNER: Person C
├── requirements.txt           # Python dependencies
├── pyproject.toml             # Pytest configuration
└── ruff.toml                  # Linter configuration
```

---

## Quick start

### Python (engine + market + api)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### Common commands

```bash
# Generate mock market (Person A)
python -m engine.mockgen --seed 42 --out data/mock/market.json

# Assess an invoice
python -m engine.assess data/mock/market.json --invoice INV001

# Run market simulator (Person B) — add --settle late to include demo step 8
python -m market.simulate data/mock/market.json --invoice INV001

# Run the API
uvicorn api.main:app --reload --port 8000

# Tests
pytest tests/ -v

# Lint
ruff check .
```

### The demo

Starts the API and the frontend together, both **without** `--reload` — the
file watcher can restart the backend mid-presentation.

```powershell
.\demo.ps1          # Windows
```

```bash
make demo           # macOS / Linux
```

Then http://localhost:5173. `GET /health` says which dataset is loaded.

### Web (Person C)

```bash
cd web
npm install
npm run dev        # uses committed mocks
npm run dev:live   # points at http://localhost:8000
```

---

## Ownership

| Path | Owner | Reviewer |
|---|---|---|
| `engine/`, `data/` | Person A | Person B |
| `market/`, `api/` | Person B | Person A |
| `web/` | Person C | Person B |
| `SCHEMA.md`, `schema.json`, `DEMO_SCENARIO.md`, `AGENTS.md` | **Shared** | **Both others** |

---

## Branch naming

- Person A: `a/<short-description>`
- Person B: `b/<short-description>`
- Person C: `c/<short-description>`
- Pairing: `ab/`, `bc/`, `ac/`

See `AGENTS.md` §4 for the full Git workflow.

---

## Phases

| Phase | Exit criteria |
|---|---|
| **0 — Contract freeze** | Schema agreed, mock market generated, all three tracks runnable independently |
| **1 — Independent build** | Each track's core works against mocks |
| **2 — First integration** | One invoice flows end to end, slider reorders live data |
| **3 — Demo path** | Full eight-step demo runs correctly every time |
| **4 — Hardening** | Error states, edge cases, rehearsal |

---

*Built for CSI ORIGIN 2026. All data is simulated.*