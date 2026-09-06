"""Check independently annotated source cases, including row/column association.

Annotations name a PDF byte revision and exact printed labels, cells and regions.
Passing selected cases is a regression result, never a whole-report quality score.
"""
from __future__ import annotations

import unicodedata
import json
import hashlib
from pathlib import Path


def _text(value):
    return " ".join(unicodedata.normalize("NFKC", value or "").split())


def paragraph_digest(text: str) -> str:
    """Hash normalized, independently transcribed prose; retain punctuation."""
    return hashlib.sha256(_text(text).encode("utf-8")).hexdigest()


def _narrative_matches(case, page, sources, pages):
    elements = {e["id"]: (p["page"], e) for p in pages.values() for e in p.get("narrative_elements", [])}

    def source_matches(element, number, bounds=None):
        spans = {s["id"]: s for s in sources[number]["spans"]}
        ids = element.get("span_ids", [])
        if not ids or len(ids) != len(set(ids)) or any(i not in spans for i in ids):
            return False
        actual = [spans[i] for i in ids]
        text = ""
        previous = None
        for span in actual:
            key = span["block"], span["line"]
            text += ("\n" if previous is not None and key != previous else "") + span["text"]
            previous = key
        if _text(text) != _text(element["text"]):
            return False
        return bounds is None or all(bounds[0] <= s["bbox"][0] <= s["bbox"][2] <= bounds[2]
                                     and bounds[1] <= s["bbox"][1] <= s["bbox"][3] <= bounds[3] for s in actual)

    matching = []
    for element in page.get("narrative_elements", []):
        if element["kind"] != case.get("element_kind", "paragraph_candidate"):
            continue
        if paragraph_digest(element["text"]) != case["text_sha256"]:
            continue
        path = element.get("heading_path", [])
        if [_text(h["text"]) for h in path] != [_text(h) for h in case["heading_path"]]:
            continue
        if not source_matches(element, case["page"], case["bbox"]):
            continue
        good = True
        for heading in path:
            number, original = elements.get(heading["id"], (None, None))
            if (original is None or original["kind"] != "heading_candidate"
                    or _text(original["text"]) != _text(heading["text"])
                    or number > case["page"]
                    or (number == case["page"] and original["source_lines"][0] >= element["source_lines"][0])
                    or not source_matches(original, number)):
                good = False
                break
        if good:
            matching.append(element["id"])
    return matching


def check_annotations(structure: dict, evidence: list[dict], annotation: dict) -> dict:
    failures = []
    if (annotation["pdf_sha256"] != evidence[0]["source"]["pdf_sha256"]
            or structure["source"] != evidence[0]["source"]):
        return {"passed": False, "failures": [{"kind": "source_revision_mismatch"}],
                "scope": "annotated_cases_only"}
    if annotation.get("filing") and any(evidence[0]["source"].get(k) != v
                                         for k, v in annotation["filing"].items()):
        return {"passed": False, "failures": [{"kind": "filing_identity_mismatch"}],
                "scope": "annotated_cases_only"}
    sources = {p["page"]: p for p in evidence[1:]}
    pages = {p["page"]: p for p in structure["pages"]}
    for case in annotation["cases"]:
        prefix = {"case": case["id"], "page": case["page"]}
        if case["page"] not in pages or case["page"] not in sources:
            failures.append({**prefix, "kind": "missing_page"})
            continue
        if case.get("kind") == "narrative":
            matching = _narrative_matches(case, pages[case["page"]], sources, pages)
            if len(matching) != 1:
                failures.append({**prefix, "kind": "paragraph_heading_source_mismatch",
                                 "matching_candidates": len(matching)})
            continue
        candidates = [table for table in pages[case["page"]]["tables"]
                      if table["method"] == case.get("method", "legacy_numeric_geometry")]
        matching = []
        for table in candidates:
            rows = [r for r in table["rows"] if _text(r.get("label", r["cells"][0].get("text")
                                                       if r["cells"] else None)) == _text(case["row_label"])]
            for row in rows:
                if table["n_cols"] != case["column_count"]:
                    continue
                good = True
                for expected in case["cells"]:
                    cells = [c for c in row["cells"] if c.get("placement", "data") == "data"
                             and c.get("col_index", c.get("column")) == expected["column"]]
                    if len(cells) != 1 or _text(cells[0]["text"]) != _text(expected["text"]):
                        good = False
                        break
                    cell = cells[0]
                    if not cell["bbox"] or not cell["word_ids"]:
                        good = False
                        break
                    box, bounds = cell["bbox"], expected["bbox"]
                    words = {w["id"]: w for w in sources[case["page"]]["words"]}
                    if any(i not in words for i in cell["word_ids"]):
                        good = False
                        break
                    actual_words = [words[i] for i in cell["word_ids"]]
                    if _text(" ".join(w["text"] for w in actual_words)) != _text(expected["text"]):
                        good = False
                        break
                    if any(not (bounds[0] <= w["bbox"][0] <= w["bbox"][2] <= bounds[2]
                                and bounds[1] <= w["bbox"][1] <= w["bbox"][3] <= bounds[3])
                           for w in actual_words):
                        good = False
                        break
                    if any(not (box[0] <= (w["bbox"][0] + w["bbox"][2]) / 2 <= box[2]
                                and box[1] <= (w["bbox"][1] + w["bbox"][3]) / 2 <= box[3])
                           for w in actual_words):
                        good = False
                        break
                if good:
                    matching.append(table["id"])
        if len(matching) != 1:
            failures.append({**prefix, "kind": "row_column_source_mismatch",
                             "matching_candidates": len(matching)})
    return {"passed": not failures, "failures": failures,
            "cases_checked": len(annotation["cases"]), "scope": "annotated_cases_only"}


def check_registered_annotations(structure: dict, evidence: list[dict], directory: Path) -> dict:
    source = evidence[0]["source"]
    matches, checks = [], []
    for path in sorted(directory.glob("*.json")):
        annotation = json.loads(path.read_text(encoding="utf-8"))
        if not all(source.get(k) == v for k, v in annotation["filing"].items()):
            continue
        matches.append(path.name)
        if annotation["pdf_sha256"] == source["pdf_sha256"]:
            checks.append({"annotation": path.name, **check_annotations(structure, evidence, annotation)})
    if not checks:
        return {"status": "source_revision_unannotated" if matches else "not_annotated",
                "checks": [], "scope": "annotated_cases_only"}
    return {"status": "passed" if all(c["passed"] for c in checks) else "failed",
            "checks": checks, "scope": "annotated_cases_only"}
