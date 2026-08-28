"""FastAPI application — five endpoints, all stateless.

Keep this thin. If an endpoint body is more than about fifteen lines,
logic has leaked out of market/ and should move back.

Endpoints:
    GET  /api/market   — raw market for initial render (SCHEMA.md §5.2)
    POST /api/assess   — verification, risk, eligibility (SCHEMA.md §5.3)
    POST /api/offers   — generate and score offers (SCHEMA.md §5.4)
    POST /api/clear    — stable matching + syndication (SCHEMA.md §5.5)
    POST /api/settle   — settlement + learning delta (SCHEMA.md §5.6)
    GET  /health       — quick liveness check

Owner: Person B
"""

from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Local imports — uncomment as implementations land
# from engine.assess import assess as engine_assess, score_offers, UnknownEntityError, InvalidWeightsError
# from market.simulate import generate_offers, clear as market_clear, settle as market_settle
# from market.settlement import IllegalTransitionError

MARKET_PATH = os.getenv("FITFUSE_MARKET", "data/mock/market.json")
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]

app = FastAPI(
    title="FitFuse",
    description="Competitive capital market for supply-chain working capital",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Market data — loaded once at startup. This is NOT session state.
# ---------------------------------------------------------------------------

_market_cache: dict | None = None


def load_market() -> dict:
    """Load and cache the market JSON. Idempotent."""
    global _market_cache
    if _market_cache is None:
        with open(MARKET_PATH, encoding="utf-8") as f:
            _market_cache = json.load(f)
    return _market_cache


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    """Quick liveness check — tells you if the backend is up and what it loaded."""
    try:
        m = load_market()
        return {
            "status": "ok",
            "market": MARKET_PATH,
            "invoices": len(m.get("invoices", [])),
            "providers": len(m.get("providers", [])),
        }
    except FileNotFoundError:
        return {"status": "no_market", "market": MARKET_PATH}


# ---------------------------------------------------------------------------
# Endpoints — stubbed with static responses for Phase 0
# Replace stubs with real logic as engine/ and market/ implementations land.
# ---------------------------------------------------------------------------

@app.get("/api/market")
def get_market():
    """Raw market for initial render. No scoring — must be fast."""
    m = load_market()
    return {
        "meta": m["meta"],
        "suppliers": m["suppliers"],
        "buyers": m["buyers"],
        "invoices": m["invoices"],
        "providers": m["providers"],
    }


@app.post("/api/assess")
def assess_invoice(req: dict):
    """Verification, risk and eligibility for one invoice. No offers."""
    # Phase 0: stub — return 501 until engine is implemented
    raise HTTPException(status_code=501, detail="assess not yet implemented")


@app.post("/api/offers")
def get_offers(req: dict):
    """Generate and score competing offers for one invoice."""
    # Phase 0: stub
    raise HTTPException(status_code=501, detail="offers not yet implemented")


@app.post("/api/clear")
def clear_market(req: dict):
    """Run clearing across the market and return stable matches."""
    # Phase 0: stub
    raise HTTPException(status_code=501, detail="clear not yet implemented")


@app.post("/api/settle")
def settle_match(req: dict):
    """Advance a match through settlement and return before/after/delta."""
    # Phase 0: stub
    raise HTTPException(status_code=501, detail="settle not yet implemented")
