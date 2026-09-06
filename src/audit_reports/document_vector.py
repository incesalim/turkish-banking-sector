"""Read matching vector outlines using explicitly source-transcribed characters.

Templates are rebuilt from the hash-bound reference PDF. A match is a candidate
transcription, not a financial cell. Unknown or ambiguous glyphs leave the whole
path unresolved, so an unrecognized parenthesis cannot become a positive amount.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

from .document_corpus import Filing, source_identity

ANCHORS = Path(__file__).with_name("document_vector_anchors.json")
VECTOR_VERSION = "source-vector-page-1"
MAX_RESIDUAL = 0.01
STRETCH_BOUNDS = (0.75, 1.3334)


def atlas_digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def glyph_components(path: dict) -> list[dict]:
    """Group contours by horizontal overlap, including counters inside a glyph."""
    items = []
    for item in path["items"]:
        if item[0] == "re":
            rect = item[1]
            points = [rect.tl, rect.tr, rect.br, rect.bl]
            if item[2] < 0:
                points.reverse()
            items.extend(("l", points[i], points[(i + 1) % 4]) for i in range(4))
        elif item[0] in ("l", "c"):
            items.append(item)
        else:
            return []
    contours, last = [], None
    for item in items:
        start, end = item[1], item[-1]
        if last is None or abs(start.x - last.x) + abs(start.y - last.y) > 0.0005:
            contours.append([])
        contours[-1].append(item)
        last = end
    parts = []
    for contour in contours:
        points = [point for item in contour for point in item[1:]]
        bbox = [min(p.x for p in points), min(p.y for p in points),
                max(p.x for p in points), max(p.y for p in points)]
        parts.append({"bbox": bbox, "items": contour})
    groups = []
    for part in sorted(parts, key=lambda p: p["bbox"][0]):
        if groups and part["bbox"][0] < groups[-1]["bbox"][2] - 0.0005:
            group = groups[-1]
            a, b = group["bbox"], part["bbox"]
            group["bbox"] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
            group["items"].extend(part["items"])
        else:
            groups.append(part)
    result = []
    for group in groups:
        x0, y0, x1, y1 = group["bbox"]
        height = y1 - y0
        if height <= 0:
            return []
        result.append({"bbox": group["bbox"], "ops": [item[0] for item in group["items"]],
                       "points": [coordinate for item in group["items"] for point in item[1:]
                                  for coordinate in ((point.x - x0) / height, (point.y - y0) / height)]})
    return result


def match_glyph(glyph: dict, templates: list[dict]) -> dict:
    matches = []
    for template in templates:
        if glyph["ops"] != template["ops"]:
            continue
        observed, expected = glyph["points"], template["points"]
        if len(observed) != len(expected):
            continue
        denominator = sum(x * x for x in observed[::2])
        if denominator == 0:
            continue
        stretch = sum(a * b for a, b in zip(observed[::2], expected[::2])) / denominator
        if not STRETCH_BOUNDS[0] <= stretch <= STRETCH_BOUNDS[1]:
            continue
        residual = max(abs(a * (stretch if index % 2 == 0 else 1) - b)
                       for index, (a, b) in enumerate(zip(observed, expected)))
        if residual <= MAX_RESIDUAL:
            matches.append({"template_id": template["id"], "character": template["character"],
                            "residual": residual, "horizontal_scale": stretch})
    characters = {m["character"] for m in matches}
    if len(characters) != 1:
        return {"character": None, "reason": "ambiguous_shape" if characters else "unknown_shape",
                "candidate_characters": sorted(characters)}
    best = min(matches, key=lambda m: (m["residual"], m["template_id"]))
    return {**best, "reason": "unique_shape_match"}


def build_atlas(reference: Path, anchors: dict) -> dict:
    filing = Filing(**anchors["filing"])
    identity = source_identity(reference, filing)
    if identity["pdf_sha256"] != anchors["pdf_sha256"]:
        raise ValueError("Vector reference PDF differs from its transcribed source revision")
    templates = []
    with fitz.open(reference) as pdf:
        for seed in anchors["seeds"]:
            page = pdf[seed["page"] - 1]
            x0, y0, x1, y1 = seed["source_bbox"]
            found = [(i, path) for i, path in enumerate(page.get_drawings()) if path["type"] == "f"
                     and x0 <= path["rect"].x0 and path["rect"].x1 <= x1
                     and y0 <= path["rect"].y0 and path["rect"].y1 <= y1]
            if len(found) != 1:
                raise ValueError(f"Vector seed does not resolve to one source path: {seed['id']}")
            drawing_id, path = found[0]
            glyphs = glyph_components(path)
            if len(glyphs) != len(seed["text"]):
                raise ValueError(f"Vector seed character count differs: {seed['id']}")
            learned = set(seed.get("learn_characters", seed["text"]))
            if not learned or learned - set(seed["text"]):
                raise ValueError("Learned vector characters must occur in their transcribed seed")
            for index, (character, glyph) in enumerate(zip(seed["text"], glyphs)):
                if character not in anchors["alphabet"]:
                    raise ValueError("Vector seed contains an undeclared character")
                if character not in learned:
                    continue
                templates.append({"id": len(templates), "character": character,
                                  "seed_id": seed["id"], "page": seed["page"],
                                  "drawing_id": drawing_id, "glyph_index": index, **glyph})
    for template in templates:
        if match_glyph(template, templates)["character"] != template["character"]:
            raise ValueError("Source-transcribed vector characters have ambiguous shapes")
    return {"schema_version": "source-vector-atlas-1", "source": identity,
            "anchors_sha256": atlas_digest(anchors), "templates": templates,
            "pymupdf": fitz.VersionBind, "mupdf": fitz.VersionFitz}


def _page_paths(page, atlas: dict) -> tuple[list[dict], list[dict]]:
    matched, unresolved = [], []
    for drawing_id, path in enumerate(page.get_drawings()):
        if path["type"] != "f":
            continue
        glyphs = glyph_components(path)
        # Large background rectangles are not comparable with these text seeds.
        if not glyphs or any(not 0.2 <= g["bbox"][3] - g["bbox"][1] <= 30 for g in glyphs):
            unresolved.append({"drawing_id": drawing_id, "bbox": list(path["rect"] * page.rotation_matrix),
                               "reason": "unsupported_geometry", "text": None})
            continue
        observations = [{"glyph_index": i, "bbox": list(fitz.Rect(glyph["bbox"]) * page.rotation_matrix),
                         **match_glyph(glyph, atlas["templates"])} for i, glyph in enumerate(glyphs)]
        complete = all(g["character"] is not None for g in observations)
        item = {"drawing_id": drawing_id, "bbox": list(path["rect"] * page.rotation_matrix),
                "glyphs": observations, "text": "".join(g["character"] for g in observations) if complete else None}
        (matched if complete else unresolved).append(item)
    return matched, unresolved


def capture_vector_page(pdf: Path, filing: Filing, number: int, atlas: dict, **provenance) -> dict:
    identity = source_identity(pdf, filing, **provenance)
    with fitz.open(pdf) as original:
        if not 1 <= number <= len(original):
            raise ValueError("Vector page is outside the source PDF")
        page = original[number - 1]
        matched, unresolved = _page_paths(page, atlas)
        record = {"schema_version": VECTOR_VERSION, "source": identity, "page": number,
                "width": page.rect.width, "height": page.rect.height, "rotation": page.rotation,
                "coordinate_space": "display", "matched_paths": matched, "unresolved_paths": unresolved,
                "engine": {"pymupdf": fitz.VersionBind, "mupdf": fitz.VersionFitz,
                           "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                           "atlas_sha256": atlas_digest(atlas), "max_residual": MAX_RESIDUAL,
                           "horizontal_scale_bounds": list(STRETCH_BOUNDS)},
                "reference_source": atlas["source"], "anchors_sha256": atlas["anchors_sha256"],
                "status": "vector_candidates", "recognition_verified": False,
                "association_verified": False, "visibility_verified": False}
    if source_identity(pdf, filing, **provenance) != identity:
        raise ValueError("Source PDF changed during vector reading")
    return record


def verify_vector_page(record: dict, pdf: Path, atlas: dict) -> dict:
    errors = []
    try:
        source = record["source"]
        filing = Filing(source["bank_ticker"], source["period"], source["kind"])
        expected = capture_vector_page(pdf, filing, record["page"], atlas,
                                       source_url=source.get("source_url"), object_key=source.get("object_key"))
        if record != expected:
            errors.append("Vector path/glyph observation differs from its source and reference atlas")
    except (ValueError, KeyError, TypeError, IndexError, RuntimeError) as error:
        errors.append(f"Invalid vector observation: {error}")
    return {"valid": not errors, "errors": errors, "recognition_verified": False}


def check_vector_annotations(record: dict, directory: Path) -> dict:
    if not directory.is_dir():
        raise ValueError("Vector source annotation directory is missing")
    source = record["source"]
    identity = {key: source[key] for key in ("bank_ticker", "period", "kind")}
    checks, same_filing = [], False
    for path in sorted(directory.glob("*.json")):
        annotation = json.loads(path.read_text(encoding="utf-8"))
        if annotation["filing"] != identity:
            continue
        same_filing = True
        if annotation["pdf_sha256"] != source["pdf_sha256"]:
            continue
        for case in annotation["cases"]:
            if case["page"] != record["page"]:
                continue
            x0, y0, x1, y1 = case["source_bbox"]
            matches = [item for item in record["matched_paths"] + record["unresolved_paths"]
                       if x0 <= item["bbox"][0] and item["bbox"][2] <= x1
                       and y0 <= item["bbox"][1] and item["bbox"][3] <= y1]
            text = matches[0]["text"] if len(matches) == 1 else None
            passed = len(matches) == 1 and (text == case["text"] or
                     (case.get("allow_unresolved", False) and text is None))
            checks.append({"id": case["id"], "passed": passed, "recognized": passed and text is not None,
                           "observed_text": text, "matched_drawing_ids": [m["drawing_id"] for m in matches],
                           "full_cell_verified": False})
    return {"status": ("passed" if all(c["passed"] for c in checks) else "failed") if checks else
            ("source_revision_or_page_unannotated" if same_filing else "not_annotated"),
            "scope": "annotated_words_regions_and_abstentions_only", "checks": checks,
            "recognition_verified": False}
