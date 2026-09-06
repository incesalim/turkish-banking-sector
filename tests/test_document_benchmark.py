import copy

import fitz
import pytest

from src.audit_reports.document_benchmark import check_annotations
from src.audit_reports.document_corpus import Filing
from src.audit_reports.document_evidence import capture_source_evidence
from src.audit_reports.document_structure import build_document_structure


@pytest.fixture
def benchmark(tmp_path):
    path = tmp_path / "TEST_2026Q1_consolidated.pdf"
    with fitz.open() as doc:
        p = doc.new_page()
        for y, label, current, prior in [(80, "Capital of Tier 1", "1,000", "900"),
                                          (100, "Capital of Tier 2", "1,000", "800"),
                                          (120, "Total Capital", "2,000", "1,700")]:
            for x, text in [(40, label), (250, current), (350, prior)]:
                p.insert_text((x, y), text)
        doc.save(path)
    evidence = capture_source_evidence(path, Filing("TEST", "2026Q1", "consolidated"))
    structure = build_document_structure(path, evidence)
    # Expected cells and positions are specified from the authored source,
    # independently of the parser result under test.
    annotations = {"pdf_sha256": evidence[0]["source"]["pdf_sha256"], "cases": [{
        "id": "capital_tier_1", "page": 1, "row_label": "Capital of Tier 1", "column_count": 2,
        "cells": [{"column": 0, "text": "1,000", "bbox": [249, 67, 290, 85]},
                  {"column": 1, "text": "900", "bbox": [349, 67, 390, 85]}]}]}
    return structure, evidence, annotations


def test_digits_in_labels_do_not_become_phantom_value_columns(benchmark):
    structure, evidence, annotations = benchmark
    result = check_annotations(structure, evidence, annotations)
    assert result["passed"], result
    assert result["scope"] == "annotated_cases_only"
    cells = structure["pages"][0]["tables"][0]["rows"][0]["cells"]
    assert any(c["text"] == "1" and c["placement"] == "label_text" for c in cells)


@pytest.mark.parametrize("mutation", ["swap_rows", "swap_columns", "swap_same_value_source", "wrong_source"])
def test_benchmark_rejects_wrong_associations_with_numbers_still_present(benchmark, mutation):
    structure, evidence, annotations = benchmark
    changed = copy.deepcopy(structure)
    rows = changed["pages"][0]["tables"][0]["rows"]
    if mutation == "swap_rows":
        rows[0]["cells"], rows[1]["cells"] = rows[1]["cells"], rows[0]["cells"]
    elif mutation == "swap_columns":
        for cell in rows[0]["cells"]:
            if cell["placement"] == "data":
                cell["col_index"] = 1 - cell["col_index"]
    elif mutation == "swap_same_value_source":
        target = next(c for c in rows[0]["cells"] if c["placement"] == "data")
        target["word_ids"] = next(c for c in rows[1]["cells"] if c["placement"] == "data")["word_ids"]
    else:
        changed["source"]["pdf_sha256"] = "0" * 64
    assert not check_annotations(changed, evidence, annotations)["passed"]
