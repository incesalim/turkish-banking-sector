"""Compact corpus status for the admin, with an extraction-independent denominator."""
from __future__ import annotations

from .document_corpus import Filing

CATALOG_VERSION = "document-corpus-catalog-1"


def filing_id(row: dict) -> str:
    filing = Filing(row["bank_ticker"], row["period"], row["kind"])
    return f"{filing.bank_ticker}|{filing.period}|{filing.kind}"


def summarize_index(index: dict) -> dict:
    if index.get("schema_version") != "corpus-index-1":
        raise ValueError("Unsupported corpus filing index")
    identity = index["filing"]
    filing_id(identity)
    current = index.get("current")
    if current and any(current["source"].get(k) != v for k, v in identity.items()):
        raise ValueError("Corpus index contains a different filing's source")
    structure = current.get("structure_current") if current else None
    last = index.get("last_attempt") or {"status": "not_started"}
    return {
        "source": current["source"] if current else None,
        "evidence_engine": current["engine"] if current else None,
        "page_count": current["page_count"] if current else None,
        "structure_engine": structure["engine"] if structure else None,
        "table_candidates": structure["table_candidates"] if structure else None,
        "text_blocks": structure["text_blocks"] if structure else None,
        "pages_with_issues": structure["pages_with_issues"] if structure else None,
        "source_versions": len({r["source"]["pdf_sha256"] for r in index["revisions"]}),
        "capture_revisions": len(index["revisions"]),
        "last_attempt_status": last["status"], "last_error": last.get("error"),
        "last_attempt_source": last.get("source"),
        "semantic_verification": "not_performed",
    }


def build_catalog(inventory: dict, previous: dict | None, indexes: list[dict], *,
                  evidence_engine: dict, structure_engine: dict) -> dict:
    """Merge scoped progress without erasing other filings or previous good captures.

    The acquisition inventory defines scope, not successful extraction. Old index
    summaries survive a limited run. Absence of an artifact is unknown/not captured,
    never a zero table or prose count.
    """
    if previous and previous.get("schema_version") != CATALOG_VERSION:
        raise ValueError("Unsupported corpus catalog")
    old = {filing_id(row): row for row in (previous or {}).get("filings", [])}
    updates = {filing_id(index["filing"]): summarize_index(index) for index in indexes}
    inventory_rows = {filing_id(row): row for row in inventory["filings"]}
    rows = []
    for key in sorted(inventory_rows.keys() | old.keys()):
        incoming, prior = inventory_rows.get(key), old.get(key)
        if incoming is None:
            # A later inventory cannot delete historical capture evidence.
            row = {**prior, "in_current_inventory": False}
        else:
            row = {k: incoming[k] for k in ("bank_ticker", "period", "kind", "registered",
                                            "source_urls", "object_keys", "acquisition_status")}
            row["in_current_inventory"] = True
            row["capture"] = (prior or {}).get("capture")
        if key in updates:
            row["capture"] = updates[key]
        capture = row.get("capture")
        row["source_capture_stale"] = bool(capture and capture["evidence_engine"]
                                            and capture["evidence_engine"] != evidence_engine)
        row["structure_stale"] = bool(capture and capture["structure_engine"]
                                       and capture["structure_engine"] != structure_engine)
        row["latest_attempt_failed"] = bool(capture and capture["last_attempt_status"] == "failed")
        rows.append(row)
    # An index for a filing absent from both inventories is an input error, not
    # something to silently drop from a success summary.
    if updates.keys() - {filing_id(row) for row in rows}:
        raise ValueError("Capture index has no corresponding corpus inventory entry")
    active = [row for row in rows if row["in_current_inventory"]]
    return {"schema_version": CATALOG_VERSION, "evidence_engine": evidence_engine,
            "structure_engine": structure_engine,
            "summary": {
                "filings": len(active),
                "registered": sum(row["registered"] for row in active),
                "acquired": (sum(row["acquisition_status"] == "acquired" for row in active)
                             if inventory["acquisition_checked"] else None),
                "source_preserved": sum(bool(row.get("capture") and row["capture"]["source"])
                                        for row in active),
                "structured_candidates": sum(bool(row.get("capture") and row["capture"]["structure_engine"])
                                             for row in active),
                "failed": sum(row["latest_attempt_failed"] for row in active),
                "stale": sum(row["source_capture_stale"] or row["structure_stale"] for row in active),
                "semantically_verified": 0,
            }, "filings": rows}
