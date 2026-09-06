import json

import fitz
import pytest

import build_document_corpus as build


def _config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"banks": {"TEST": {"urls": {"consolidated": {
        "2026Q1": "https://bank.example/report.pdf"}}}}}), encoding="utf-8")
    return path


def _args(tmp_path):
    return ["--config", str(_config(tmp_path)), "--source-dir", str(tmp_path),
            "--output-dir", str(tmp_path / "out")]


def test_unqueried_r2_is_unknown_not_a_missing_source(tmp_path):
    assert build.main(_args(tmp_path)) == 0
    report = json.loads((tmp_path / "out/inventory.json").read_text())
    assert report["registered_missing"] is None
    assert report["acquisition_checked"] is False
    assert report["filings"][0]["acquisition_status"] == "not_checked"


def test_missing_source_fails_capture_and_remains_in_results(tmp_path):
    assert build.main(_args(tmp_path) + ["--capture", "--bank", "TEST"]) == 1
    results = json.loads((tmp_path / "out/capture-results.json").read_text())["filings"]
    assert len(results) == 1
    assert results[0]["status"] == "failed"
    assert "Missing" in results[0]["error"]


def test_capture_keeps_source_artifacts_and_never_claims_verified(tmp_path):
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 50), "A complete source sentence.")
        doc.save(tmp_path / "TEST_2026Q1_consolidated.pdf")
    assert build.main(_args(tmp_path) + ["--capture", "--bank", "TEST"]) == 0
    result = json.loads((tmp_path / "out/capture-results.json").read_text())["filings"][0]
    assert result["status"] == "source_preserved"
    assert result["semantic_verification"] == "not_performed"
    assert (tmp_path / "out" / result["artifact"]).exists()
    assert result["source"]["object_key"] is None


def test_unbounded_local_capture_is_refused(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(SystemExit):
        build.main(_args(tmp_path) + ["--capture"])


def test_read_only_structure_probe_cannot_silently_skip_a_missing_benchmark(tmp_path):
    with pytest.raises(SystemExit):
        build.main(_args(tmp_path) + ["--capture", "--structure", "--bank", "TEST",
                                     "--annotations-dir", str(tmp_path / "missing-benchmark")])


def test_password_protected_pdf_is_preserved_even_when_capture_fails(tmp_path):
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 50), "Protected original")
        doc.save(tmp_path / "TEST_2026Q1_consolidated.pdf", encryption=fitz.PDF_ENCRYPT_AES_256,
                 owner_pw="owner", user_pw="reader")
    assert build.main(_args(tmp_path) + ["--capture", "--bank", "TEST"]) == 1
    result = json.loads((tmp_path / "out/capture-results.json").read_text())["filings"][0]
    assert result["status"] == "failed" and "password" in result["error"]
    archived = tmp_path / "out" / result["original"]
    assert archived.read_bytes() == (tmp_path / "TEST_2026Q1_consolidated.pdf").read_bytes()


def test_r2_capture_reads_current_object_instead_of_a_stale_local_copy(tmp_path, monkeypatch):
    from src.audit_reports import r2_storage as r2
    args = _args(tmp_path)
    local = tmp_path / "TEST_2026Q1_consolidated.pdf"
    local.write_bytes(b"stale local non-PDF")
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 50), "Current source revision")
        body = doc.tobytes()
    key = "test/TEST_2026Q1_consolidated.pdf"
    monkeypatch.setattr(r2, "list_audit_pdfs", lambda: [("TEST", "2026Q1", "consolidated", key)])
    monkeypatch.setattr(r2, "download_to", lambda _key, destination: destination.write_bytes(body))
    assert build.main(args + ["--from-r2", "--capture", "--bank", "TEST"]) == 0
    result = json.loads((tmp_path / "out/capture-results.json").read_text())["filings"][0]
    assert result["source"]["object_key"] == key
    assert result["source"]["byte_count"] == len(body)
    assert local.read_bytes() == b"stale local non-PDF"
