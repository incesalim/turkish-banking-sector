from pathlib import Path

import pytest

from src.audit_reports.document_corpus import (
    Filing, filing_from_filename, preserve_original, reconcile_inventory, registered_sources,
    source_identity,
)


def test_transport_does_not_create_a_false_missing_basis():
    sources = registered_sources({"banks": {"TAKAS": {"urls": {
        "unconsolidated_zip": {"2026Q2": "https://bank.example/report.zip"},
        "unconsolidated": {"2026Q2": "https://bank.example/report.pdf"},
    }}}})
    filing = Filing("TAKAS", "2026Q2", "unconsolidated")
    assert len(sources[filing]) == 2
    report = reconcile_inventory(sources, [("TAKAS", "2026Q2", "unconsolidated",
                                          "takas/TAKAS_2026Q2_unconsolidated.pdf")])
    assert report["registered_filings"] == 1
    assert report["registered_missing"] == []


def test_missing_and_extra_sources_are_retained_without_extraction_results():
    missing = Filing("BANKA", "2026Q1", "consolidated")
    acquired = ("BANKB", "2026Q2", "unconsolidated", "b/BANKB_2026Q2_unconsolidated.pdf")
    report = reconcile_inventory({missing: ["https://bank.example/a.pdf"]}, [acquired],
                                 [Path(missing.filename)])
    assert report["registered_missing"] == [missing.as_dict()]
    assert report["acquired_filings"] == 1
    assert report["filings"][0]["acquisition_status"] == "missing"
    assert report["filings"][1]["registered"] is False


@pytest.mark.parametrize("name", ["A_2026Q0_consolidated.pdf", "A_2026Q5_consolidated.pdf",
                                  "A_2026Q1_unconsolidated_zip.pdf", "A_2026Q1_other.pdf"])
def test_invalid_filing_names_do_not_enter_the_corpus(name):
    assert filing_from_filename(name) is None


def test_object_binding_must_agree_with_its_source_name():
    with pytest.raises(ValueError, match="disagrees"):
        reconcile_inventory({}, [("BANKA", "2026Q1", "consolidated",
                                  "b/BANKB_2026Q1_consolidated.pdf")])


def test_changed_pdf_bytes_invalidate_identity_even_at_the_same_path(tmp_path):
    filing = Filing("BANKA", "2026Q1", "consolidated")
    path = tmp_path / filing.filename
    path.write_bytes(b"%PDF-1.7\nfirst revision\n")
    first = source_identity(path, filing)
    path.write_bytes(b"%PDF-1.7\nother revision\n")
    second = source_identity(path, filing)
    assert first["pdf_sha256"] != second["pdf_sha256"]
    assert second["byte_count"] == path.stat().st_size
    path.write_bytes(b"<html>access denied</html>")
    with pytest.raises(ValueError, match="not a PDF"):
        source_identity(path, filing)


def test_original_archive_is_immutable_and_verified(tmp_path):
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-1.7\noriginal version\n")
    identity = source_identity(source, Filing("TEST", "2026Q1", "consolidated"))
    target = tmp_path / "archive/original.pdf"
    assert preserve_original(source, target, identity)
    assert not preserve_original(source, target, identity)
    assert target.read_bytes() == source.read_bytes()
    target.write_bytes(b"%PDF-1.7\ncorrupted stored version\n")
    with pytest.raises(ValueError, match="fails its content identity"):
        preserve_original(source, target, identity)


def test_changed_source_cannot_be_archived_under_its_previous_identity(tmp_path):
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-1.7\nfirst version\n")
    identity = source_identity(source, Filing("TEST", "2026Q1", "consolidated"))
    source.write_bytes(b"%PDF-1.7\nother version\n")
    target = tmp_path / "archive/original.pdf"
    with pytest.raises(ValueError, match="Source changed"):
        preserve_original(source, target, identity)
    assert not target.exists()
    assert not list(target.parent.glob("*.tmp"))
