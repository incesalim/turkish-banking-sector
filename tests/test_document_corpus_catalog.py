import copy

import pytest

from src.audit_reports.document_corpus_catalog import build_catalog

EVIDENCE = {"version": "evidence-one"}
STRUCTURE = {"version": "structure-one"}


def inventory():
    return {"acquisition_checked": True, "filings": [
        {"bank_ticker": bank, "period": "2026Q1", "kind": "consolidated",
         "registered": True, "source_urls": [f"https://{bank}.example/report.pdf"],
         "object_keys": [f"{bank.lower()}/{bank}_2026Q1_consolidated.pdf"] if bank == "ONE" else [],
         "local_paths": ["private/local/path"], "acquisition_status": "acquired" if bank == "ONE" else "missing"}
        for bank in ("ONE", "TWO")]}


def index():
    filing = {"bank_ticker": "ONE", "period": "2026Q1", "kind": "consolidated"}
    revision = {"source": {**filing, "pdf_sha256": "a" * 64}, "engine": EVIDENCE, "page_count": 100,
                "structure_current": {"engine": STRUCTURE, "table_candidates": 80,
                                      "text_blocks": 400, "pages_with_issues": 30}}
    return {"schema_version": "corpus-index-1", "filing": filing, "current": revision,
            "revisions": [revision], "last_attempt": {"status": "structured_candidates"}}


def build(previous=None, indexes=(), inv=None):
    return build_catalog(inv or inventory(), previous, list(indexes),
                         evidence_engine=EVIDENCE, structure_engine=STRUCTURE)


def test_denominator_includes_uncaptured_and_missing_sources():
    catalog = build(indexes=[index()])
    assert catalog["summary"] == {"filings": 2, "registered": 2, "acquired": 1,
                                  "source_preserved": 1, "structured_candidates": 1,
                                  "failed": 0, "stale": 0, "semantically_verified": 0}
    assert catalog["filings"][1]["capture"] is None
    assert all("local_paths" not in row for row in catalog["filings"])


def test_limited_replay_retains_prior_work_and_is_identical():
    first = build(indexes=[index()])
    assert build(first) == first
    assert build(first, [index()]) == first


def test_failure_preserves_previous_source_but_cannot_look_clean():
    first = build(indexes=[index()])
    failed = index()
    failed["last_attempt"] = {"status": "failed", "error": "new PDF cannot be read"}
    result = build(first, [failed])
    assert result["summary"]["source_preserved"] == 1
    assert result["summary"]["failed"] == 1
    assert result["filings"][0]["latest_attempt_failed"]
    assert result["filings"][0]["capture"]["last_error"] == "new PDF cannot be read"


def test_engine_change_marks_saved_results_stale_instead_of_counting_them_as_current():
    first = build(indexes=[index()])
    result = build_catalog(inventory(), first, [], evidence_engine=EVIDENCE,
                           structure_engine={"version": "new-structure"})
    assert result["summary"]["stale"] == 1
    assert result["filings"][0]["structure_stale"]
    assert not result["filings"][0]["source_capture_stale"]


def test_inventory_change_does_not_delete_historical_evidence():
    first = build(indexes=[index()])
    inv = inventory()
    inv["filings"] = inv["filings"][1:]
    result = build(first, inv=inv)
    assert len(result["filings"]) == 2
    assert result["summary"]["filings"] == 1
    assert result["filings"][0]["capture"]["source"] is not None
    assert result["filings"][0]["in_current_inventory"] is False


def test_uncaptured_counts_stay_null_and_unqueried_acquisition_stays_unknown():
    inv = inventory()
    inv["acquisition_checked"] = False
    result = build(inv=inv)
    assert result["summary"]["acquired"] is None
    assert all(row["capture"] is None for row in result["filings"])


def test_wrong_filing_and_unsupported_catalog_are_refused():
    damaged = copy.deepcopy(index())
    damaged["current"]["source"]["bank_ticker"] = "OTHER"
    with pytest.raises(ValueError, match="different filing"):
        build(indexes=[damaged])
    with pytest.raises(ValueError, match="Unsupported corpus catalog"):
        build({"schema_version": "unknown"})
