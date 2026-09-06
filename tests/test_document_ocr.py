import copy
import hashlib
import json

import fitz
import pytest

from src.audit_reports import document_ocr as ocr
from src.audit_reports.document_corpus import Filing, source_identity


@pytest.fixture
def retained_observation(tmp_path):
    """A retained visual PDF is sufficient for inventory tests; no OCR model call."""
    source = tmp_path / "TEST_2026Q1_consolidated.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page(width=240, height=180)
        page.insert_text((20, 40), "Disclosed zero 0 and unknown")
        pdf.save(source)
        pix = page.get_pixmap(dpi=300, colorspace=fitz.csRGB, alpha=False)
        with fitz.open() as derived:
            observation = derived.new_page(width=240, height=180)
            observation.insert_image(observation.rect, pixmap=pix)
            observation.insert_text((20, 40), "Disclosed zero 0 and unknown", render_mode=3)
            body = derived.tobytes()
    with fitz.open(stream=body) as pdf:
        words, spans = ocr._observations(pdf[0], 240, 180)
    record = {"schema_version": ocr.OCR_VERSION,
              "source": source_identity(source, Filing("TEST", "2026Q1", "consolidated")),
              "page": 1, "width": 240, "height": 180, "rotation": 0,
              "coordinate_space": "display", "engine": {"dpi": 300},
              "render": {"width": pix.width, "height": pix.height, "channels": pix.n,
                         "pixels_sha256": hashlib.sha256(pix.samples).hexdigest()},
              "ocr_pdf_sha256": hashlib.sha256(body).hexdigest(), "words": words, "spans": spans,
              "recognition_verified": False, "association_verified": False,
              "status": "ocr_candidates", "confidence": None}
    return record, body, source


def test_retention_check_is_separate_from_recognition_accuracy(retained_observation):
    record, body, source = retained_observation
    assert ocr.verify_ocr_page(record, body, source) == {
        "valid": True, "errors": [], "recognition_verified": False}
    assert any(word["text"] == "0" for word in record["words"])


@pytest.mark.parametrize("change", ["drop", "duplicate", "replace", "move", "span", "approve", "pixels"])
def test_retention_rejects_lost_or_changed_ocr_evidence(retained_observation, change):
    record, body, source = retained_observation
    record = copy.deepcopy(record)
    if change == "drop":
        record["words"].pop()
    elif change == "duplicate":
        record["words"].append(copy.deepcopy(record["words"][0]))
    elif change == "replace":
        next(word for word in record["words"] if word["text"] == "0")["text"] = "1"
    elif change == "move":
        record["words"][0]["bbox"][0] += 10
    elif change == "span":
        record["spans"][0]["text"] = "Changed qualification"
    elif change == "approve":
        record["recognition_verified"] = True
    else:
        record["render"]["pixels_sha256"] = "0" * 64
    assert not ocr.verify_ocr_page(record, body, source)["valid"]


def test_different_source_bytes_and_wrong_pdf_page_are_rejected(retained_observation):
    record, body, source = retained_observation
    record["page"] = 2
    assert not ocr.verify_ocr_page(record, body, source)["valid"]
    record["page"] = 1
    source.write_bytes(source.read_bytes() + b"Changed source")
    assert not ocr.verify_ocr_page(record, body, source)["valid"]


@pytest.mark.parametrize("width", [0, -1, float("nan"), float("inf")])
def test_invalid_geometry_fails_closed(retained_observation, width):
    record, body, _ = retained_observation
    record["width"] = width
    assert not ocr.verify_ocr_page(record, body)["valid"]


def test_model_cache_is_hash_checked_and_never_silently_replaced(tmp_path, monkeypatch):
    models = tmp_path / "models"
    models.mkdir()
    (models / "eng.traineddata").write_bytes(b"corrupt")
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"revision": "test", "models": {"eng": {
        "bytes": 5, "sha256": hashlib.sha256(b"valid").hexdigest(), "source_url": "unused"}}}))
    monkeypatch.setattr(ocr, "MODEL_LOCK", lock)
    with pytest.raises(ValueError, match="pinned identity"):
        ocr.ensure_models(models)
    assert (models / "eng.traineddata").read_bytes() == b"corrupt"
    (models / "eng.traineddata").write_bytes(b"valid")
    assert ocr.ensure_models(models)["revision"] == "test"


def test_observation_coordinates_handle_rotated_source_display(tmp_path, monkeypatch):
    source = tmp_path / "TEST_2026Q1_consolidated.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page(width=240, height=180)
        page.insert_text((20, 40), "Rotated source")
        page.set_rotation(90)
        pdf.save(source)
    monkeypatch.setattr(ocr, "ensure_models", lambda path: {"revision": "test", "models": {
        "eng": {"sha256": "1" * 64}}})

    def fake_ocr(pix, **kwargs):
        with fitz.open() as pdf:
            page = pdf.new_page(width=pix.width * 72 / pix.xres, height=pix.height * 72 / pix.yres)
            page.insert_image(page.rect, pixmap=pix)
            page.insert_text((20, 40), "Recognized text", render_mode=3)
            return pdf.tobytes()

    monkeypatch.setattr(fitz.Pixmap, "pdfocr_tobytes", fake_ocr)
    record, derivative = ocr.capture_ocr_page(source, Filing("TEST", "2026Q1", "consolidated"),
                                            1, tmp_path, language="eng")
    assert (record["width"], record["height"], record["rotation"]) == (180, 240, 90)
    assert ocr.verify_ocr_page(record, derivative, source)["valid"]


def test_source_token_check_catches_swaps_and_duplicates_without_certifying_cells(tmp_path, retained_observation):
    record, _, _ = retained_observation
    zero = next(word for word in record["words"] if word["text"] == "0")
    annotation = {"filing": {key: record["source"][key] for key in ("bank_ticker", "period", "kind")},
                  "pdf_sha256": record["source"]["pdf_sha256"], "cases": [
                      {"id": "disclosed_zero", "kind": "token_in_region", "page": 1,
                       "token": "0", "source_bbox": zero["bbox"]}]}
    (tmp_path / "case.json").write_text(json.dumps(annotation))
    first = ocr.check_ocr_annotations(record, tmp_path)
    assert first["status"] == "passed" and not first["recognition_verified"]
    assert first["checks"][0]["full_cell_verified"] is False
    original_box = zero["bbox"]
    zero["bbox"] = record["words"][0]["bbox"]
    assert ocr.check_ocr_annotations(record, tmp_path)["status"] == "failed"
    zero["bbox"] = original_box
    record["words"].append(copy.deepcopy(zero))
    assert ocr.check_ocr_annotations(record, tmp_path)["status"] == "failed"
    record["source"]["pdf_sha256"] = "0" * 64
    assert ocr.check_ocr_annotations(record, tmp_path)["status"] == "source_revision_or_page_unannotated"


def test_cli_keeps_failed_ocr_probe_files_and_reports_the_named_case(tmp_path, monkeypatch, retained_observation):
    import build_document_corpus as build
    record, derivative, source = retained_observation
    monkeypatch.setattr(ocr, "capture_ocr_page", lambda *args, **kwargs: (record, derivative))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"banks": {"TEST": {"urls": {"consolidated": {
        "2026Q1": "https://bank.example/report.pdf"}}}}}))
    directory = tmp_path / "annotations"
    directory.mkdir()
    output = tmp_path / "output"
    args = ["--config", str(config), "--source-dir", str(source.parent), "--output-dir", str(output),
            "--capture", "--bank", "TEST", "--limit", "1", "--ocr-pages", "1",
            "--ocr-annotations-dir", str(directory)]
    assert build.main(args) == 0
    result = json.loads((output / "capture-results.json").read_text())["filings"][0]
    recovery = result["text_recovery"][0]
    assert recovery["benchmark"]["status"] == "not_annotated"
    assert recovery["recognition_verified"] is False
    assert (output / recovery["derivative"]).read_bytes() == derivative
    zero = next(word for word in record["words"] if word["text"] == "0")
    annotation = {"filing": {key: record["source"][key] for key in ("bank_ticker", "period", "kind")},
                  "pdf_sha256": record["source"]["pdf_sha256"], "cases": [
                      {"id": "missing_disclosure", "kind": "token_in_region", "page": 1,
                       "token": "1", "source_bbox": zero["bbox"]}]}
    (directory / "case.json").write_text(json.dumps(annotation))
    assert build.main(args) == 1
    failed = json.loads((output / "capture-results.json").read_text())["filings"][0]
    assert failed["status"] == "failed" and "missing_disclosure" in failed["error"]
    recovery = failed["text_recovery"][0]
    assert recovery["benchmark"]["status"] == "failed"
    assert (output / recovery["derivative"]).read_bytes() == derivative
    assert (output / recovery["observation"]).exists()
