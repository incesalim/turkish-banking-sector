import copy
import json

import fitz
import pytest

from src.audit_reports import document_vector as vector
from src.audit_reports.document_corpus import Filing, source_identity


def _word(page, text, x, y, sx=1, sy=1):
    # Synthetic test shapes, not contours copied from a bank's font.
    shapes = {
        "1": [(0, 1), (1, 0), (2, 0), (2, 6), (1, 6), (1, 1), (0, 2), (0, 1)],
        "7": [(0, 0), (4, 0), (1, 6), (0, 6), (3, 1), (0, 1), (0, 0)],
        ".": [(0, 5), (1, 5), (1, 6), (0, 6), (0, 5)],
        "-": [(0, 3), (3, 3), (3, 4), (0, 4), (0, 3)],
        "(": [(2, 0), (1, 0), (0, 3), (1, 6), (2, 6), (1, 3), (2, 0)],
        ")": [(0, 0), (1, 0), (2, 3), (1, 6), (0, 6), (1, 3), (0, 0)],
    }
    shape = page.new_shape()
    for character in text:
        points = shapes[character]
        shape.draw_polyline([fitz.Point(x + a * sx, y + b * sy) for a, b in points])
        x += (max(a for a, b in points) + 2) * sx
    shape.finish(fill=(0, 0, 0), color=None, closePath=True)
    shape.commit()


@pytest.fixture
def source_atlas(tmp_path):
    filing = Filing("TEST", "2026Q1", "consolidated")
    path = tmp_path / filing.filename
    with fitz.open() as pdf:
        _word(pdf.new_page(width=240, height=180), "17.-", 20, 30)
        page = pdf.new_page(width=240, height=180)
        _word(page, "71", 80, 70, sx=1.25, sy=1.1)
        _word(page, "(17)", 80, 100)
        pdf.save(path)
    identity = source_identity(path, filing)
    anchors = {"schema_version": "source-vector-anchors-1", "filing": filing.as_dict(),
               "pdf_sha256": identity["pdf_sha256"], "alphabet": "17.-", "seeds": [
                   {"id": "synthetic_shapes", "page": 1, "source_bbox": [19, 29, 43, 38], "text": "17.-"}]}
    atlas = vector.build_atlas(path, anchors)
    return path, filing, anchors, atlas


def test_translated_stretched_shapes_match_but_unknown_parentheses_do_not_disappear(source_atlas):
    path, filing, _, atlas = source_atlas
    record = vector.capture_vector_page(path, filing, 2, atlas)
    assert [item["text"] for item in record["matched_paths"]] == ["71"]
    unresolved = record["unresolved_paths"]
    assert len(unresolved) == 1 and unresolved[0]["text"] is None
    assert [g["character"] for g in unresolved[0]["glyphs"]] == [None, "1", "7", None]
    assert vector.verify_vector_page(record, path, atlas)["valid"]
    assert not record["recognition_verified"] and not record["association_verified"]


def test_conflicting_transcriptions_abstain_instead_of_picking_closest(source_atlas):
    _, _, _, atlas = source_atlas
    glyph = atlas["templates"][0]
    conflicting = {**copy.deepcopy(glyph), "character": "7", "id": len(atlas["templates"])}
    match = vector.match_glyph(glyph, atlas["templates"] + [conflicting])
    assert match["character"] is None and match["reason"] == "ambiguous_shape"


def test_reference_hash_and_seed_occurrence_counts_are_checked(source_atlas):
    path, _, anchors, _ = source_atlas
    changed = copy.deepcopy(anchors)
    changed["pdf_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="revision"):
        vector.build_atlas(path, changed)
    changed = copy.deepcopy(anchors)
    changed["seeds"][0]["text"] = "17"
    with pytest.raises(ValueError, match="character count"):
        vector.build_atlas(path, changed)
    changed["seeds"][0]["source_bbox"] = [0, 0, 5, 5]
    with pytest.raises(ValueError, match="one source path"):
        vector.build_atlas(path, changed)


def test_punctuation_seed_does_not_teach_its_surrounding_numbers(source_atlas):
    path, _, anchors, _ = source_atlas
    selected = copy.deepcopy(anchors)
    selected["seeds"][0]["learn_characters"] = ".-"
    atlas = vector.build_atlas(path, selected)
    assert {t["character"] for t in atlas["templates"]} == {".", "-"}
    selected["seeds"][0]["learn_characters"] = "()"
    with pytest.raises(ValueError, match="occur"):
        vector.build_atlas(path, selected)


def test_large_background_centered_in_a_source_region_is_not_a_word_match(source_atlas, tmp_path):
    path, filing, anchors, atlas = source_atlas
    record = vector.capture_vector_page(path, filing, 2, atlas)
    record["unresolved_paths"].append({"drawing_id": 999, "bbox": [0, 0, 180, 144], "text": None})
    annotation = {"filing": filing.as_dict(), "pdf_sha256": anchors["pdf_sha256"], "cases": [
        {"id": "word_inside_large_background", "page": 2, "source_bbox": [75, 65, 110, 80], "text": "71"}]}
    (tmp_path / "annotation.json").write_text(json.dumps(annotation))
    check = vector.check_vector_annotations(record, tmp_path)
    assert check["status"] == "passed"
    assert check["checks"][0]["observed_text"] == "71"
    annotation["cases"][0]["source_bbox"] = [81, 65, 90, 80]
    (tmp_path / "annotation.json").write_text(json.dumps(annotation))
    assert vector.check_vector_annotations(record, tmp_path)["status"] == "failed"


@pytest.mark.parametrize("change", ["drop", "move", "value", "sign", "approve"])
def test_source_retention_rejects_changes_including_guessed_positive_values(source_atlas, change):
    path, filing, _, atlas = source_atlas
    record = vector.capture_vector_page(path, filing, 2, atlas)
    if change == "drop":
        record["matched_paths"].clear()
    elif change == "move":
        record["matched_paths"][0]["bbox"][0] += 5
    elif change == "value":
        record["matched_paths"][0]["text"] = "17"
    elif change == "sign":
        record["unresolved_paths"][0]["text"] = "17"
    else:
        record["recognition_verified"] = True
    assert not vector.verify_vector_page(record, path, atlas)["valid"]


def test_cli_keeps_reference_and_failed_vector_observations(source_atlas, tmp_path, monkeypatch):
    import build_document_corpus as build
    path, filing, anchors, _ = source_atlas
    anchor_path = tmp_path / "anchors.json"
    anchor_path.write_text(json.dumps(anchors))
    monkeypatch.setattr(vector, "ANCHORS", anchor_path)
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"banks": {"TEST": {"urls": {"consolidated": {
        "2026Q1": "https://bank.example/report.pdf"}}}}}))
    annotations = tmp_path / "annotations"
    annotations.mkdir()
    case = {"filing": filing.as_dict(), "pdf_sha256": anchors["pdf_sha256"], "cases": [
        {"id": "held_out_word", "page": 2, "source_bbox": [75, 65, 110, 80], "text": "71"},
        {"id": "negative_sign", "page": 2, "source_bbox": [75, 95, 115, 110],
         "text": "(17)", "allow_unresolved": True}]}
    (annotations / "case.json").write_text(json.dumps(case))
    output = tmp_path / "output"
    args = ["--config", str(config), "--source-dir", str(path.parent), "--output-dir", str(output),
            "--capture", "--bank", "TEST", "--limit", "1", "--vector-pages", "2",
            "--vector-annotations-dir", str(annotations)]
    assert build.main(args) == 0
    row = json.loads((output / "capture-results.json").read_text())["filings"][0]
    recovery = row["vector_recovery"][0]
    assert recovery["benchmark"]["status"] == "passed"
    assert (output / recovery["reference_pdf"]).read_bytes() == path.read_bytes()
    assert (output / recovery["atlas"]).exists()
    case["cases"][0]["text"] = "17"
    (annotations / "case.json").write_text(json.dumps(case))
    assert build.main(args) == 1
    row = json.loads((output / "capture-results.json").read_text())["filings"][0]
    assert row["status"] == "failed" and "held_out_word" in row["error"]
    assert (output / row["vector_recovery"][0]["observation"]).exists()
