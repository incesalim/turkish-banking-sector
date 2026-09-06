import copy
import gzip
import json

import fitz
import pytest

from src.audit_reports.document_corpus import Filing
from src.audit_reports.document_evidence import (
    artifact_digest, capture_source_evidence, compare_page_text, save_evidence,
    verify_evidence_records,
)


@pytest.fixture
def evidence(tmp_path):
    filing = Filing("TEST", "2026Q1", "consolidated")
    path = tmp_path / filing.filename
    with fitz.open() as doc:
        page = doc.new_page()
        # All-text table: no numerical-table heuristic can decide its inclusion.
        for x, y, text in [(40, 60, "Name"), (250, 60, "Responsibility"),
                           (40, 80, "Person A"), (250, 80, "Credit committee"),
                           (40, 100, "Person B"), (250, 100, "Risk committee"),
                           (40, 150, "Amount 1,000"), (40, 170, "Amount 1,000"),
                           (40, 200, "(*) Includes related parties.")]:
            page.insert_text((x, y), text)
        page.draw_rect(fitz.Rect(35, 45, 450, 110))
        rotated = doc.new_page()
        rotated.insert_text((40, 80), "Rotated explanatory text")
        rotated.set_rotation(90)
        doc.save(path)
    return capture_source_evidence(path, filing)


def test_source_inventory_keeps_text_tables_notes_and_repeated_values(evidence):
    text = "\n".join(s["text"] for s in evidence[1]["spans"])
    assert "Credit committee" in text and "Risk committee" in text
    assert text.count("Amount 1,000") == 2
    assert "(*) Includes related parties." in text
    assert evidence[1]["drawings"]
    assert verify_evidence_records(evidence)["valid"]
    assert evidence[0]["semantic_verification"] == "not_performed"


def test_rotated_coordinates_are_in_display_space(evidence):
    page = evidence[2]
    assert page["rotation"] == 90
    assert page["width"] == 842
    assert page["height"] == 595
    for word in page["words"]:
        x0, y0, x1, y1 = word["bbox"]
        assert 0 <= x0 < x1 <= page["width"]
        assert 0 <= y0 < y1 <= page["height"]


def test_lost_duplicate_cannot_hide_behind_number_presence(evidence):
    page = evidence[1]
    lines = [s["text"] for s in page["spans"]]
    assert compare_page_text(page, lines)["text_conserved"]
    lines.remove("Amount 1,000")
    check = compare_page_text(page, lines)
    assert not check["text_conserved"]
    assert check["missing_count"] == len("Amount1,000")
    assert check["missing_characters"]["0"] == 3


def test_conservation_does_not_claim_to_verify_semantic_association(evidence):
    page = evidence[1]
    lines = [s["text"] for s in page["spans"]]
    result = compare_page_text(page, list(reversed(lines)))
    assert result["text_conserved"]
    assert result["association_verified"] is False


@pytest.mark.parametrize("mutation", ["drop_page", "change_word", "change_bbox", "drop_span"])
def test_artifact_verifier_detects_corrupted_payloads(evidence, mutation):
    damaged = copy.deepcopy(evidence)
    if mutation == "drop_page":
        damaged.pop()
    elif mutation == "change_word":
        damaged[1]["words"][0]["text"] = "invented"
    elif mutation == "change_bbox":
        damaged[1]["words"][0]["bbox"][0] += 10
    else:
        damaged[1]["spans"].pop()
    assert not verify_evidence_records(damaged)["valid"]


def test_artifact_is_reproducible_and_source_bound(evidence, tmp_path):
    output = tmp_path / "source.jsonl.gz"
    assert save_evidence(evidence, output)
    first_bytes, first_time = output.read_bytes(), output.stat().st_mtime_ns
    assert not save_evidence(evidence, output)
    assert output.read_bytes() == first_bytes
    assert output.stat().st_mtime_ns == first_time
    records = [json.loads(line) for line in gzip.decompress(first_bytes).splitlines()]
    assert verify_evidence_records(records)["valid"]
    wrong_source = {**records[0]["source"], "pdf_sha256": "0" * 64}
    assert not verify_evidence_records(records, expected_source=wrong_source)["valid"]


def test_invalid_evidence_cannot_replace_a_good_artifact(evidence, tmp_path):
    output = tmp_path / "source.jsonl.gz"
    save_evidence(evidence, output)
    original = output.read_bytes()
    damaged = copy.deepcopy(evidence)
    damaged.pop()
    with pytest.raises(ValueError, match="Refusing invalid"):
        save_evidence(damaged, output)
    assert output.read_bytes() == original


def test_source_binding_and_engine_are_part_of_the_artifact_address(evidence):
    changed = copy.deepcopy(evidence)
    changed[0]["source"]["period"] = "2026Q2"
    assert artifact_digest(changed) != artifact_digest(evidence)
    changed = copy.deepcopy(evidence)
    changed[0]["engine"]["implementation_sha256"] = "0" * 64
    assert artifact_digest(changed) != artifact_digest(evidence)


def test_manifest_summary_cannot_disagree_with_its_pages(evidence):
    changed = copy.deepcopy(evidence)
    changed[0]["text_characters"] = 0
    changed[0]["image_regions"] = 999
    assert verify_evidence_records(changed)["errors"] == [
        "manifest_text_count_mismatch", "manifest_image_count_mismatch"]


@pytest.mark.parametrize("page_count", [None, "2", -1, True])
def test_invalid_page_count_is_a_failed_check_not_a_verifier_crash(evidence, page_count):
    changed = copy.deepcopy(evidence)
    changed[0]["page_count"] = page_count
    assert "invalid_page_count" in verify_evidence_records(changed)["errors"]
