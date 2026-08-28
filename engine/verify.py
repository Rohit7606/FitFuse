"""Invoice verification — IRN check, duplicate detection, field-confidence tagging.

Produces a Verification object (SCHEMA.md §4.2).
A rejected invoice never proceeds to risk scoring or offers.

Owner: Person A
"""

from __future__ import annotations


def verify(invoice_id: str, market: dict) -> dict:
    """Verify an invoice: IRN validity, duplicate detection, field tagging.

    Args:
        invoice_id: must exist in market["invoices"]
        market: MarketInput dict

    Returns:
        Verification dict per SCHEMA.md §4.2

    Three checks, in order:
        1. IRN validity — non-null 64-char hex string
        2. Duplicate detection — shared document_hash across invoices
        3. Field-confidence tagging
    """
    raise NotImplementedError("Person A: implement verify()")
