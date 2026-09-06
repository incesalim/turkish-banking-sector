import copy

import fitz
import pytest

from src.audit_reports.document_corpus import Filing
from src.audit_reports.document_evidence import capture_source_evidence
from src.audit_reports.document_structure import build_document_structure, verify_document_structure


@pytest.fixture
def document(tmp_path):
    path = tmp_path / "TEST_2026Q1_consolidated.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        for x in (40, 230, 440):
            page.draw_line((x, 50), (x, 140))
        for y in (50, 80, 110, 140):
            page.draw_line((40, y), (440, y))
        for x, y, text in [(50, 70, "Name"), (240, 70, "Responsibility"),
                           (50, 100, "Person A"), (240, 100, "Credit committee"),
                           (50, 130, "Person B"), (240, 130, "Risk committee"),
                           (50, 180, "(*) Appointment subject to approval."),
                           (50, 220, "Narrative with repeated 1,000 and 1,000.")]:
            page.insert_text((x, y), text)
        page = doc.new_page()
        for x, y, text in [(40, 50, "Current period"), (300, 50, "Prior period"),
                           (40, 80, "Assets"), (250, 80, "1,000"), (350, 80, "900"),
                           (40, 100, "Liabilities"), (250, 100, "2,000"), (350, 100, "800"),
                           (40, 120, "Total"), (250, 120, "3,000"), (350, 120, "1,700")]:
            page.insert_text((x, y), text)
        doc.save(path)
    evidence = capture_source_evidence(path, Filing("TEST", "2026Q1", "consolidated"))
    return path, evidence, build_document_structure(path, evidence)


def test_text_only_table_is_structured_and_prose_is_preserved(document):
    _path, evidence, structure = document
    first = structure["pages"][0]
    ruled = [table for table in first["tables"] if table["method"] == "pymupdf_lines_strict"]
    assert len(ruled) == 1
    assert [[cell["text"] for cell in row["cells"]] for row in ruled[0]["rows"]] == [
        ["Name", "Responsibility"], ["Person A", "Credit committee"], ["Person B", "Risk committee"]]
    text = "\n".join(block["text"] for block in first["text_blocks"])
    assert "(*) Appointment subject to approval." in text
    assert "Narrative with repeated 1,000 and 1,000." in text
    assert verify_document_structure(structure, evidence)["valid"]
    assert structure["semantic_verification"] == "not_performed"


@pytest.mark.parametrize("mutation", ["drop_text", "duplicate_text", "change_text", "drop_drawing", "drop_page"])
def test_source_accounting_detects_omissions_and_duplicates(document, mutation):
    _path, evidence, structure = document
    damaged = copy.deepcopy(structure)
    page = damaged["pages"][0]
    if mutation == "drop_text":
        page["text_blocks"].pop()
    elif mutation == "duplicate_text":
        page["text_blocks"].append(page["text_blocks"][0])
    elif mutation == "change_text":
        page["text_blocks"][0]["lines"][0]["text"] = "Invented text"
    elif mutation == "drop_drawing":
        page["source_drawing_ids"].pop()
    else:
        damaged["pages"].pop()
    assert not verify_document_structure(damaged, evidence)["valid"]


def test_word_swap_between_cells_is_detected_even_when_all_values_survive(document):
    _path, evidence, structure = document
    damaged = copy.deepcopy(structure)
    table = next(t for t in damaged["pages"][1]["tables"] if t["method"] == "legacy_numeric_geometry")
    first, second = table["rows"][0]["cells"][0], table["rows"][1]["cells"][0]
    first["word_ids"], second["word_ids"] = second["word_ids"], first["word_ids"]
    result = verify_document_structure(damaged, evidence)
    assert not result["valid"]
    assert "page_2:cell_geometry_mismatch" in result["errors"]


def test_changed_pdf_cannot_be_given_old_evidence(document):
    path, evidence, _structure = document
    path.write_bytes(path.read_bytes() + b" changed revision")
    with pytest.raises(ValueError, match="differs from source evidence"):
        build_document_structure(path, evidence)


def test_raster_dash_rules_recover_text_table_without_ocr(tmp_path):
    path = tmp_path / "TEST_2026Q1_consolidated.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        pixel = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, 6, 1), 0)
        pixel.clear_with(0)
        dash = pixel.tobytes("png")
        for x in (40, 230, 440):
            page.draw_line((x, 50), (x, 110))
        for y in (50, 80, 110):
            for x in range(40, 440, 4):
                page.insert_image(fitz.Rect(x, y, x + 2.4, y + .4), stream=dash)
        for x, y, text in [(50, 70, "Issuer"), (240, 70, "Example Bank"),
                           (50, 100, "Instrument"), (240, 100, "Subordinated bond")]:
            page.insert_text((x, y), text)
        doc.save(path)
    evidence = capture_source_evidence(path, Filing("TEST", "2026Q1", "consolidated"))
    structure = build_document_structure(path, evidence)
    table = next(t for t in structure["pages"][0]["tables"] if t["method"] == "pymupdf_lines_strict")
    assert table["row_count"] == 2 and table["n_cols"] == 2
    assert table["rows"][1]["cells"][1]["text"] == "Subordinated bond"
    assert len(table["image_rule_candidates"]) == 3
    assert len(structure["pages"][0]["source_image_ids"]) == 300
    assert verify_document_structure(structure, evidence)["valid"]
