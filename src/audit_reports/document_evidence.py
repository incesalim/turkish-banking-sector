"""Source-first evidence, independent of the legacy numerical-table detector.

Retain all typed text spans and their geometry, word occurrences, image regions
and drawing regions. These are observations, not a claim of complete semantic
extraction. Conservation checks catch lost/duplicated text; source-annotated
benchmarks must separately establish row, column, paragraph and note association.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

import fitz

from .document_corpus import Filing, source_identity
from .document_tagged import capture_tagged_structure, verify_tagged_structure

EVIDENCE_VERSION = "source-evidence-1"


@lru_cache(maxsize=1)
def engine_identity() -> dict:
    """Cache identity includes implementation bytes, not a manually bumped label."""
    implementation = hashlib.sha256()
    for filename in ("document_evidence.py", "document_corpus.py", "document_tagged.py"):
        implementation.update((Path(__file__).parent / filename).read_bytes())
    return {"pymupdf": fitz.VersionBind, "mupdf": fitz.VersionFitz,
            "implementation_sha256": implementation.hexdigest()}


def _box(bbox, matrix) -> list[float]:
    rect = fitz.Rect(bbox) * matrix
    rect.normalize()
    return [round(v, 4) for v in rect]


def _canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def text_characters(text: str) -> Counter:
    """Count occurrences, preserving signs, punctuation and repeated numbers.

    Layout spaces can differ when a parser splits a glued word. NFKC handles
    ligatures; case, digits, punctuation and meaningful characters remain exact.
    This intentionally does not pretend to test ordering or semantic association.
    """
    return Counter(c for c in unicodedata.normalize("NFKC", text) if not c.isspace())


def page_evidence(page) -> dict:
    """Observe a page directly; never ask the legacy detector what should count."""
    matrix = page.rotation_matrix
    # ActualText can be positioned at a prior text cursor outside the page even
    # when its corresponding image is visible. Do not clip away that wording.
    raw = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES,
                        clip=fitz.INFINITE_RECT())
    spans = []
    for block_index, block in enumerate(raw.get("blocks", [])):
        if block["type"] != 0:
            continue
        for line_index, line in enumerate(block.get("lines", [])):
            for span_index, span in enumerate(line.get("spans", [])):
                spans.append({
                    "id": len(spans), "block": block_index, "line": line_index,
                    "span": span_index, "text": span["text"],
                    "bbox": _box(span["bbox"], matrix), "font": span["font"],
                    "size": round(span["size"], 4), "flags": span["flags"],
                    "direction": [round(line["dir"][0] * matrix.a + line["dir"][1] * matrix.c, 4),
                                  round(line["dir"][0] * matrix.b + line["dir"][1] * matrix.d, 4)],
                })
    words = [{"id": i, "text": w[4], "bbox": _box(w[:4], matrix),
              "block": w[5], "line": w[6], "word": w[7]}
             for i, w in enumerate(page.get_text("words", clip=fitz.INFINITE_RECT()))]
    literal = [{"id": i, "text": w[4], "bbox": _box(w[:4], matrix),
                "block": w[5], "line": w[6], "word": w[7]}
               for i, w in enumerate(page.get_text("words", clip=fitz.INFINITE_RECT(),
                                                   flags=fitz.TEXTFLAGS_WORDS | fitz.TEXT_IGNORE_ACTUALTEXT))]
    images = []
    for i, info in enumerate(page.get_image_info(hashes=True)):
        images.append({"id": i, "bbox": _box(info["bbox"], matrix),
                       "width": info["width"], "height": info["height"],
                       "digest": info["digest"].hex(),
                       "review_status": "unreviewed"})
    drawings = [{"id": i, "bbox": _box(drawing["rect"], matrix),
                 "type": drawing["type"], "path_items": len(drawing["items"])}
                for i, drawing in enumerate(page.get_drawings())]
    text = "\n".join(s["text"] for s in spans)
    result = {"type": "source_page", "page": page.number + 1,
            "width": page.rect.width, "height": page.rect.height,
            "rotation": page.rotation, "coordinate_space": "display",
            "spans": spans, "words": words, "images": images, "drawings": drawings,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "text_character_count": sum(text_characters(text).values()),
            "replacement_character_count": text.count("\ufffd"),
            "text_clip": "unbounded", "text_geometry_verified": False,
            "actualtext_changes_word_view": words != literal,
            "literal_glyph_words": literal if words != literal else None}
    result["native_structure"] = capture_tagged_structure(page, spans, images)
    return result


def compare_page_text(evidence: dict, captured_lines: list[str]) -> dict:
    """Find omissions/duplications against the source, including repeated values."""
    source = text_characters("".join(s["text"] for s in evidence["spans"]))
    captured = text_characters("".join(captured_lines))
    missing, extra = source - captured, captured - source
    return {"page": evidence["page"], "source_characters": sum(source.values()),
            "captured_characters": sum(captured.values()),
            "missing_characters": dict(sorted(missing.items())),
            "extra_characters": dict(sorted(extra.items())),
            "missing_count": sum(missing.values()), "extra_count": sum(extra.values()),
            "text_conserved": not missing and not extra,
            "association_verified": False}


def verify_evidence_records(records: list[dict], *, expected_source: dict | None = None) -> dict:
    """Verify a stored artifact's integrity before it can become a source for queries.

    Artifact validity is separate from extraction completeness. A well-formed
    image-only page is valid evidence and still has unverified content.
    """
    errors = []
    if not records or records[0].get("type") != "source_manifest":
        return {"valid": False, "errors": ["missing_source_manifest"]}
    manifest = records[0]
    if manifest.get("schema_version") != EVIDENCE_VERSION:
        errors.append("unsupported_schema_version")
    if expected_source is not None and manifest.get("source") != expected_source:
        errors.append("source_identity_mismatch")
    source = manifest.get("source", {})
    digest = source.get("pdf_sha256", "")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        errors.append("invalid_pdf_sha256")
    try:
        Filing(source["bank_ticker"], source["period"], source["kind"])
    except (KeyError, ValueError, TypeError):
        errors.append("invalid_filing_identity")
    if not isinstance(source.get("byte_count"), int) or source["byte_count"] <= 0:
        errors.append("invalid_source_size")
    page_count = manifest.get("page_count")
    if type(page_count) is not int or page_count <= 0:
        errors.append("invalid_page_count")
        page_count = 0
    pages = records[1:]
    expected_pages = list(range(1, len(pages) + 1))
    if page_count != len(pages) or [p.get("page") for p in pages] != expected_pages:
        errors.append("page_inventory_mismatch")
    for p in pages:
        pg = p.get("page")
        errors.extend(f"page_{pg}:{error}" for error in verify_tagged_structure(p))
        literal = p.get("literal_glyph_words")
        if literal is not None and [w["id"] for w in literal] != list(range(len(literal))):
            errors.append(f"page_{pg}:literal_word_identity_mismatch")
        if p.get("type") != "source_page":
            errors.append(f"page_{pg}:invalid_record_type")
        for collection in ("spans", "words", "images", "drawings"):
            items = p.get(collection, [])
            if [x.get("id") for x in items] != list(range(len(items))):
                errors.append(f"page_{pg}:{collection}_identity_mismatch")
        text = "\n".join(s["text"] for s in p.get("spans", []))
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != p.get("text_sha256"):
            errors.append(f"page_{pg}:text_digest_mismatch")
        if sum(text_characters(text).values()) != p.get("text_character_count"):
            errors.append(f"page_{pg}:text_count_mismatch")
    if manifest.get("text_characters") != sum(p.get("text_character_count", 0) for p in pages):
        errors.append("manifest_text_count_mismatch")
    if manifest.get("image_regions") != sum(len(p.get("images", [])) for p in pages):
        errors.append("manifest_image_count_mismatch")
    page_hashes = [hashlib.sha256(_canonical_json(p).encode("utf-8")).hexdigest() for p in pages]
    # Older source-evidence-1 artifacts remain readable. New captures include
    # page hashes so an authenticated viewer can verify one streamed page.
    if "page_sha256" in manifest and manifest["page_sha256"] != page_hashes:
        errors.append("individual_page_digest_mismatch")
    actual_digest = hashlib.sha256(
        "\n".join(_canonical_json(p) for p in pages).encode("utf-8")).hexdigest()
    if actual_digest != manifest.get("pages_sha256"):
        errors.append("page_payload_digest_mismatch")
    return {"valid": not errors, "errors": errors,
            "page_count": len(pages), "semantic_verification": "not_performed"}


def capture_source_evidence(path: str | Path, filing: Filing, *,
                            source_url: str | None = None,
                            object_key: str | None = None) -> list[dict]:
    """Capture one source; fleet callers stream these per-document artifacts."""
    identity = source_identity(path, filing, source_url=source_url, object_key=object_key)
    with fitz.open(path) as doc:
        if doc.needs_pass:
            raise ValueError("PDF requires a password; source capture is unresolved")
        pages = [page_evidence(p) for p in doc]
    if not pages:
        raise ValueError("PDF has no pages")
    # Re-check after reading: a concurrently replaced source must not be labelled
    # with the hash of the earlier bytes. No artifact is published on a mismatch.
    if source_identity(path, filing, source_url=source_url, object_key=object_key) != identity:
        raise ValueError("PDF changed during source capture")
    payload_hash = hashlib.sha256(
        "\n".join(_canonical_json(p) for p in pages).encode("utf-8")).hexdigest()
    manifest = {"type": "source_manifest", "schema_version": EVIDENCE_VERSION,
                "engine": engine_identity(),
                "source": identity, "page_count": len(pages),
                "pages_sha256": payload_hash,
                "page_sha256": [hashlib.sha256(_canonical_json(p).encode("utf-8")).hexdigest() for p in pages],
                "text_characters": sum(p["text_character_count"] for p in pages),
                "image_regions": sum(len(p["images"]) for p in pages),
                "status": "source_preserved", "semantic_verification": "not_performed"}
    records = [manifest, *pages]
    check = verify_evidence_records(records, expected_source=identity)
    if not check["valid"]:
        raise ValueError(f"Source artifact failed verification: {check['errors']}")
    return records


def artifact_digest(records: list[dict]) -> str:
    """Address the complete artifact, including source binding and engine version."""
    return hashlib.sha256(
        ("\n".join(_canonical_json(r) for r in records) + "\n").encode("utf-8")).hexdigest()


def save_evidence(records: list[dict], path: str | Path) -> bool:
    """Atomically persist deterministic compressed evidence; no-op when unchanged."""
    check = verify_evidence_records(records)
    if not check["valid"]:
        raise ValueError(f"Refusing invalid evidence: {check['errors']}")
    path = Path(path)
    payload = ("\n".join(_canonical_json(r) for r in records) + "\n").encode("utf-8")
    compressed = gzip.compress(payload, compresslevel=6, mtime=0)
    if path.exists() and path.read_bytes() == compressed:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(compressed)
            stream.flush()
            os.fsync(stream.fileno())
        # Verify the actual bytes on disk, not only the object before serializing.
        decoded = [json.loads(line) for line in gzip.decompress(temporary.read_bytes()).splitlines()]
        if not verify_evidence_records(decoded)["valid"]:
            raise ValueError("Serialized evidence failed round-trip verification")
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return True
