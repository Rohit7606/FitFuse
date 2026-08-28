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

import math

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
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


def validation_response(exc: RequestValidationError) -> JSONResponse:
    """A 422 that can actually be serialised and actually be read.

    Two problems with the default handler, both found by throwing NaN at it:

    1. The body echoes the offending input, so a request carrying a NaN made
       the error response itself unserialisable and the exception escaped the
       app — a bad request turning into a 500 with no body, which is the one
       thing SCHEMA.md §5.7 forbids. Python's json.loads accepts the bare
       NaN literal, so this is reachable from any HTTP client.
    2. `detail` was a list of objects, and web/src/utils/api.js does
       `throw new Error(err.detail)` — on stage that reads
       "[object Object],[object Object]".

    So: `detail` is a sentence, `errors` keeps pydantic's structured output,
    and every non-finite float in either is rendered as text.
    """
    errors = _json_safe(jsonable_encoder(exc.errors()))
    return error_response(422, "invalid_request", _first_problem(errors),
                          errors=errors)


def _first_problem(errors: list) -> str:
    if not errors:
        return "Request body failed validation."
    first = errors[0]
    where = ".".join(str(part) for part in first.get("loc", ())
                     if part != "body") or "body"
    more = f" (and {len(errors) - 1} more)" if len(errors) > 1 else ""
    return f"{where}: {first.get('msg', 'invalid')}{more}"


def _json_safe(value):
    """Replace anything json.dumps would refuse. NaN and inf are the whole point."""
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)
