"""Preserve PDF-declared structure without treating its layout as verified.

A PDF may attach ActualText to an image. MuPDF's ordinary text view can place
that replacement at the preceding text cursor, even outside the page. Native
structure keeps its declared container and image region available independently
of that synthetic text geometry. Native tables can themselves be column strips,
so their names are source metadata, not proof of a complete visual table.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque

import fitz


def _box(values, matrix):
    rect = fitz.Rect(values) * matrix
    if rect.is_empty or rect.is_infinite:
        return None
    return [round(value, 4) for value in rect]


def _span_key(text, bbox):
    return text, tuple(bbox or [])


def capture_tagged_structure(page, source_spans: list[dict], source_images: list[dict]) -> dict | None:
    if page.parent.xref_get_key(page.parent.pdf_catalog(), "StructTreeRoot")[0] == "null":
        return None
    raw = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT | fitz.TEXT_COLLECT_STRUCTURE,
                        clip=fitz.INFINITE_RECT())
    if not any(block["type"] == 2 for block in raw["blocks"]):
        return None
    available = defaultdict(deque)
    for span in source_spans:
        available[_span_key(span["text"], span["bbox"])].append(span["id"])
    nodes = []
    matrix = page.rotation_matrix

    def visit(block, parent):
        number = len(nodes)
        node = {"id": number, "parent": parent, "bbox": _box(block["bbox"], matrix)}
        nodes.append(node)
        if block["type"] == 2:
            node.update(kind="structure", role=block["std"], source_role=block["raw"],
                        source_index=block["index"], children=[])
            for child in block["blocks"]:
                node["children"].append(visit(child, number))
        elif block["type"] == 0:
            node.update(kind="text", lines=[])
            for line in block["lines"]:
                spans = []
                for span in line["spans"]:
                    box = _box(span["bbox"], matrix)
                    candidates = available[_span_key(span["text"], box)]
                    spans.append({"text": span["text"], "bbox": box,
                                  "source_span_id": candidates.popleft() if candidates else None})
                node["lines"].append({"spans": spans})
        elif block["type"] == 1:
            box = node["bbox"]
            # The tagged view may clip an image to its declared content region;
            # get_image_info records its full placement. Preserve both regions.
            candidates = [image["id"] for image in source_images if box
                          and image["width"] == block["width"] and image["height"] == block["height"]
                          and image["bbox"][0] - .1 <= box[0] <= box[2] <= image["bbox"][2] + .1
                          and image["bbox"][1] - .1 <= box[1] <= box[3] <= image["bbox"][3] + .1]
            node.update(kind="image", width=block["width"], height=block["height"],
                        source_image_candidates=candidates)
        else:
            node.update(kind="unhandled", source_type=block["type"])
        return number

    roots = [visit(block, None) for block in raw["blocks"]]
    roles = Counter(n["role"] for n in nodes if n["kind"] == "structure")
    unresolved = sum(s["source_span_id"] is None and bool(s["text"].strip())
                     for n in nodes if n["kind"] == "text" for line in n["lines"] for s in line["spans"])
    return {"method": "pdf_declared_structure", "roots": roots, "nodes": nodes,
            "role_counts": dict(roles), "unmapped_nonblank_spans": unresolved,
            "geometry_verified": False, "semantic_verification": "not_performed"}


def verify_tagged_structure(source: dict) -> list[str]:
    tagged = source.get("native_structure")
    if tagged is None:
        return []
    errors, nodes = [], tagged["nodes"]
    if [node["id"] for node in nodes] != list(range(len(nodes))):
        return ["native_node_inventory_mismatch"]
    children = Counter(tagged["roots"])
    spans = {span["id"]: span for span in source["spans"]}
    image_ids = {image["id"] for image in source["images"]}
    for node in nodes:
        if node["kind"] == "structure":
            children.update(node["children"])
            if any(not 0 <= i < len(nodes) or nodes[i]["parent"] != node["id"] or i <= node["id"]
                   for i in node["children"]):
                errors.append("native_parent_mismatch")
        elif node["kind"] == "text":
            for line in node["lines"]:
                for span in line["spans"]:
                    ref = span["source_span_id"]
                    if ref is not None and (ref not in spans or any(
                            span[k] != spans[ref][k] for k in ("text", "bbox"))):
                        errors.append("native_source_span_mismatch")
        elif node["kind"] == "image":
            if not set(node["source_image_candidates"]).issubset(image_ids):
                errors.append("native_source_image_mismatch")
    if children != Counter(range(len(nodes))):
        errors.append("native_child_inventory_mismatch")
    if any(not 0 <= i < len(nodes) or nodes[i]["parent"] is not None for i in tagged["roots"]):
        errors.append("native_root_mismatch")
    return errors
