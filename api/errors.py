"""API error handling — maps engine/market exceptions to HTTP status codes.

Error responses follow SCHEMA.md §5.7:
    400 — unknown entity, invalid weights, illegal transition
    422 — malformed body (pydantic)
    500 — unexpected engine/market failure

Never return 500 for a bad request. Never return 200 with an error inside.

This module is the single authority on that mapping. It is deliberately not a
set of FastAPI exception handlers: engine/ and market/ raise inside the request
handler, where the endpoint still has to decide whether to continue, so the
mapping is a function the endpoint calls rather than a net the framework casts.
Two mechanisms doing the same job is how a 500 eventually escapes one of them.

Owner: Person B
"""

from __future__ import annotations

from fastapi.responses import JSONResponse

from engine.assess import InvalidWeightsError, UnknownEntityError
from market.settlement import IllegalTransitionError


def error_response(status: int, error: str, detail: str, **extra) -> JSONResponse:
    """The one error body shape — SCHEMA.md §5.7."""
    return JSONResponse(status_code=status,
                        content={"error": error, "detail": detail, **extra})


def to_response(exc: Exception) -> JSONResponse:
    """Map an engine or market exception to its HTTP response.

    A typo'd ID, bad weights or an illegal settlement transition is a bad
    request. Anything else is genuinely ours, and still comes back as a clean
    JSON body rather than a stack trace.
    """
    if isinstance(exc, UnknownEntityError):
        return error_response(400, "unknown_entity", str(exc),
                              entity_id=getattr(exc, "entity_id", None))
    if isinstance(exc, InvalidWeightsError):
        return error_response(400, "invalid_weights", str(exc))
    if isinstance(exc, IllegalTransitionError):
        return error_response(400, "illegal_transition", str(exc),
                              current_state=exc.current_state,
                              target_state=exc.target_state)
    return error_response(500, "engine_failure", f"{type(exc).__name__}: {exc}")
