"""Invoice verification — IRN check, duplicate detection, field-confidence tagging.

Produces a Verification object (SCHEMA.md §4.2).
A rejected invoice never proceeds to risk scoring or offers.

Owner: Person A
"""

from __future__ import annotations

import re

from engine.assess import UnknownEntityError


def _is_hex64(s: str) -> bool:
    """Return True if *s* is exactly a 64-character lowercase hex string."""
    return bool(re.fullmatch(r"[0-9a-f]{64}", s))


def _rejected(
    irn_valid: bool,
    reason: str,
    *,
    duplicate_detected: bool = False,
    duplicate_of: str | None = None,
) -> dict:
    """Build a Verification dict for a rejected invoice."""
    return {
        "status": "rejected",
        "irn_valid": irn_valid,
        "duplicate_detected": duplicate_detected,
        "duplicate_of": duplicate_of,
        "field_confidence": {},
        "unknown_field_count": 0,
        "reason_text": reason,
    }


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
    # Look up the invoice — deterministic: invoices are sorted by ID.
    invoices_by_id = {inv["invoice_id"]: inv for inv in market["invoices"]}
    invoice = invoices_by_id.get(invoice_id)
    if invoice is None:
        raise UnknownEntityError(invoice_id, f"Invoice {invoice_id} not in market")

    # ------------------------------------------------------------------
    # 1. IRN validity
    # ------------------------------------------------------------------
    irn = invoice.get("irn")
    if irn is None:
        return _rejected(
            irn_valid=False,
            reason="not registered under GST e-invoicing",
        )
    if not isinstance(irn, str) or not _is_hex64(irn):
        return _rejected(
            irn_valid=False,
            reason="invoice reference number is malformed",
        )

    # ------------------------------------------------------------------
    # 2. Duplicate detection
    # ------------------------------------------------------------------
    doc_hash = invoice["document_hash"]
    supplier_id = invoice["supplier_id"]

    # Candidates: same hash, different invoice, and either
    #   (a) status is "financed" or "settled" (always prior art), or
    #   (b) status is "open" but from a DIFFERENT supplier AND has a
    #       lexicographically smaller invoice_id (the first submitter wins;
    #       the later one is the duplicate).
    # Sort candidates by invoice_id for determinism (AGENTS.md §3.1).
    candidates = sorted(
        (
            inv
            for inv in market["invoices"]
            if inv["document_hash"] == doc_hash
            and inv["invoice_id"] != invoice_id
            and (
                inv["status"] in ("financed", "settled")
                or (
                    inv["status"] == "open"
                    and inv["supplier_id"] != supplier_id
                    and inv["invoice_id"] < invoice_id
                )
            )
        ),
        key=lambda inv: inv["invoice_id"],
    )

    if candidates:
        duplicate_of = candidates[0]["invoice_id"]
        return _rejected(
            irn_valid=True,
            reason=(
                f"Duplicate detected: document fingerprint matches {duplicate_of}. "
                "This invoice has already been submitted for financing."
            ),
            duplicate_detected=True,
            duplicate_of=duplicate_of,
        )

    # ------------------------------------------------------------------
    # 3. Field-confidence tagging (only reached when IRN valid + not dup)
    # ------------------------------------------------------------------
    # Start from any tags the invoice already carries.
    field_confidence = dict(invoice.get("field_confidence", {}) or {})

    # IRN-proven fields: amount and tenor are on the registered document.
    field_confidence["amount_lakh"] = "verified"
    field_confidence["tenor_days"] = "verified"

    # Buyer existence check — the buyer should always be in the market.
    buyer_ids = {b["buyer_id"] for b in market["buyers"]}
    if invoice["buyer_id"] in buyer_ids:
        field_confidence["buyer_gstin"] = "verified"

    # delivery_confirmed: verified if explicitly true/false, unknown if null.
    # null is NOT false — see AGENTS.md §3.6.
    if invoice.get("delivery_confirmed") is not None:
        field_confidence["delivery_confirmed"] = "verified"
    else:
        field_confidence["delivery_confirmed"] = "unknown"

    # supplier_prior_defaults: verified if an integer (including 0), unknown if null.
    # 0 and null are fundamentally different states — see AGENTS.md §3.6.
    supplier = None
    for s in market["suppliers"]:
        if s["supplier_id"] == invoice["supplier_id"]:
            supplier = s
            break

    if supplier is not None:
        if supplier.get("prior_defaults") is not None:
            field_confidence["supplier_prior_defaults"] = "verified"
        else:
            field_confidence["supplier_prior_defaults"] = "unknown"

    # Count unknowns — this number feeds directly into risk.py's uncertainty band.
    unknown_field_count = sum(
        1 for v in field_confidence.values() if v == "unknown"
    )
    inferred_field_count = sum(
        1 for v in field_confidence.values() if v == "inferred"
    )

    # Build reason text.
    parts = ["Invoice registered under a valid IRN and not previously financed."]
    if unknown_field_count > 0:
        unknown_names = [
            k for k, v in sorted(field_confidence.items()) if v == "unknown"
        ]
        readable = [n.replace("_", " ") for n in unknown_names]
        parts.append(
            f"{', '.join(readable).capitalize()} "
            f"{'is' if len(readable) == 1 else 'are'} unavailable."
        )

    return {
        "status": "verified",
        "irn_valid": True,
        "duplicate_detected": False,
        "duplicate_of": None,
        "field_confidence": field_confidence,
        "unknown_field_count": unknown_field_count,
        "inferred_field_count": inferred_field_count,
        "reason_text": " ".join(parts),
    }
