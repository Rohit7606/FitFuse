"""API error handling — maps engine/market exceptions to HTTP status codes.

Error responses follow SCHEMA.md §5.7:
    400 — unknown entity, invalid weights, illegal transition
    422 — malformed body (pydantic)
    500 — unexpected engine/market failure

Never return 500 for a bad request. Never return 200 with an error inside.

Owner: Person B
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

# These exception handlers will be registered on the FastAPI app
# once the engine and market modules are implemented.

async def unknown_entity_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": "unknown_entity",
            "detail": str(exc),
            "entity_id": getattr(exc, "entity_id", None),
        },
    )


async def invalid_weights_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": "invalid_weights",
            "detail": str(exc),
        },
    )


async def illegal_transition_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": "illegal_transition",
            "detail": str(exc),
        },
    )


async def engine_failure_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": "engine_failure",
            "detail": str(exc),
        },
    )
