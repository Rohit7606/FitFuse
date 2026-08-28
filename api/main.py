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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import stubs
from api.models import AssessRequest, ClearRequest, OffersRequest, SettleRequest

# Local imports — uncomment as implementations land
# from engine.assess import assess as engine_assess, score_offers, UnknownEntityError, InvalidWeightsError
# from market.simulate import generate_offers, clear as market_clear, settle as market_settle
# from market.settlement import IllegalTransitionError

WEIGHT_TOLERANCE = 0.001  # SCHEMA.md §6: weights sum to 1.0 ± 0.001

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
# Request validation — a bad ID is a 400, never a 500 (SCHEMA.md §5.7)
# ---------------------------------------------------------------------------

def _error(status: int, error: str, detail: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": error, "detail": detail, **extra})


def _find_invoice(invoice_id: str) -> JSONResponse | None:
    """Return an error response if the invoice is unknown, else None."""
    if any(i["invoice_id"] == invoice_id for i in load_market()["invoices"]):
        return None
    return _error(400, "unknown_entity", f"{invoice_id} not in market", entity_id=invoice_id)


def _check_weights(scenario) -> JSONResponse | None:
    """Preference weights must sum to 1.0; the sliders are the usual offender."""
    for override in scenario.preference_overrides:
        total = sum(override.weights.values())
        if abs(total - 1.0) > WEIGHT_TOLERANCE:
            return _error(
                400,
                "invalid_weights",
                f"Weights sum to {total:.2f}, expected 1.0",
            )
    return None


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
# Endpoints — Phase 0 returns contract-valid static responses from api/stubs.py
# so Person C can build against a running API. Swap each stub call for the real
# engine/market call as those land; the response shape does not change.
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
def assess_invoice(req: AssessRequest):
    """Verification, risk and eligibility for one invoice. No offers."""
    return (
        _find_invoice(req.invoice_id)
        or _check_weights(req.scenario)
        or stubs.stub_assessment(req.invoice_id)
    )


@app.post("/api/offers")
def get_offers(req: OffersRequest):
    """Generate and score competing offers. naive_ranking is always returned."""
    return (
        _find_invoice(req.invoice_id)
        or _check_weights(req.scenario)
        or stubs.stub_offers(req.invoice_id)
    )


@app.post("/api/clear")
def clear_market(req: ClearRequest):
    """Run clearing across the market and return stable matches."""
    if not req.invoice_ids:
        return _error(400, "unknown_entity", "invoice_ids must not be empty",
                      entity_id=None)
    for invoice_id in req.invoice_ids:
        if (err := _find_invoice(invoice_id)) is not None:
            return err
    return _check_weights(req.scenario) or stubs.stub_clearing(req.invoice_ids)


@app.post("/api/settle")
def settle_match(req: SettleRequest):
    """Advance a match through settlement and return before/after/delta."""
    if req.outcome not in ("settled", "late", "defaulted"):
        return _error(
            400,
            "illegal_transition",
            f"Cannot settle to state '{req.outcome}'; "
            "expected one of settled, late, defaulted",
        )
    return (
        _check_weights(req.scenario)
        or stubs.stub_settle(req.match_id, req.outcome, req.days_late)
    )
