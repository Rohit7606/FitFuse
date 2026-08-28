"""Engine exceptions, in their own module to keep imports acyclic.

These are re-exported from engine/assess.py, which is where PERSON_A.md §2
tells Person B to import them from. They live here rather than there because
verify.py raises UnknownEntityError and assess.py imports verify.py — defining
them in assess.py makes that a cycle.

Person B maps each of these to an HTTP 400 in api/errors.py.

Owner: Person A
"""

from __future__ import annotations


class UnknownEntityError(Exception):
    """Raised when an invoice_id, provider_id, etc. is not found in the market."""

    def __init__(self, entity_id: str, message: str | None = None):
        self.entity_id = entity_id
        super().__init__(message or f"{entity_id} not in market")


class InvalidWeightsError(Exception):
    """Raised when preference weights do not sum to 1.0 (± tolerance)."""

    def __init__(self, weight_sum: float):
        self.weight_sum = weight_sum
        super().__init__(f"Weights sum to {weight_sum:.2f}, expected 1.0")
