"""Risk scoring — default probability with an honest uncertainty band.

Credit risk sits primarily with the BUYER, not the supplier.
The financier pays the supplier now and collects from the buyer later.
See SCHEMA.md §2.6.

Uses a transparent scorecard: hand-set coefficients committed in config.py,
applied as a weighted logistic. Not a trained model (AGENTS.md §1.5).

Owner: Person A
"""

from __future__ import annotations


def score_risk(
    invoice: dict,
    supplier: dict,
    buyer: dict,
    verification: dict,
) -> dict:
    """Compute default probability with uncertainty band.

    Args:
        invoice: invoice record from market["invoices"]
        supplier: supplier record from market["suppliers"]
        buyer: buyer record from market["buyers"]
        verification: Verification dict from verify.verify()

    Returns:
        RiskProfile dict per SCHEMA.md §4.3

    Deterministic. No I/O, no globals, no mutation of inputs.
    """
    raise NotImplementedError("Person A: implement score_risk()")
