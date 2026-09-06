"""Source-bound visual text recovery through PyMuPDF's bundled OCR.

This is a separate observation, never a replacement for native source text.
The image-bearing OCR PDF lets a reviewer reproduce every retained word without
rerunning a model. Byte/geometry checks do not establish recognition accuracy.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import tempfile
from pathlib import Path

import fitz

from .document_corpus import Filing, source_identity

MODEL_LOCK = Path(__file__).with_name("document_ocr_models.json")
OCR_VERSION = "source-ocr-page-1"


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def ensure_models(directory: Path) -> dict:
    """Download only pinned, hash-checked language data into the caller's cache."""
    lock = json.loads(MODEL_LOCK.read_text(encoding="utf-8"))
    directory.mkdir(parents=True, exist_ok=True)
    for language, entry in lock["models"].items():
        target = directory / f"{language}.traineddata"
        if target.exists():
            body = target.read_bytes()
        else:
            import requests
            response = requests.get(entry["source_url"], timeout=60)
            response.raise_for_status()
            body = response.content
        if len(body) != entry["bytes"] or _sha(body) != entry["sha256"]:
            raise ValueError(f"OCR language model fails its pinned identity: {language}")
        if not target.exists():
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=directory, suffix=".tmp", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()
    return lock


def _engine(lock: dict, dpi: int, language: str) -> dict:
    import pymupdf
    # Record the native runtime as well as package versions: bundled OCR builds
    # can differ across platforms. No unexposed Tesseract version is invented.
    package = Path(pymupdf.__file__).parent
    binaries = sorted({path for pattern in ("_mupdf*.pyd", "_mupdf*.so", "mupdf*.dll", "libmupdf.so*")
                       for path in package.glob(pattern) if path.is_file()})
    return {"pymupdf": fitz.VersionBind, "mupdf": fitz.VersionFitz,
            "platform": platform.system(), "machine": platform.machine(),
            "native_binaries": {p.name: _sha(p.read_bytes()) for p in binaries},
            "implementation_sha256": _sha(Path(__file__).read_bytes()),
            "method": "pymupdf_full_page_pdfocr", "dpi": dpi, "language": language,
            "model_revision": lock["revision"],
            "models": {name: lock["models"][name]["sha256"] for name in language.split("+")}}


def _observations(page, width: float, height: float) -> tuple[list[dict], list[dict]]:
    # The OCR PDF describes the already-rendered display page. Pixel rounding
    # changes its physical dimensions slightly; scale each axis independently.
    transform = fitz.Matrix(width / page.rect.width, height / page.rect.height)

    def box(value):
        return [round(v, 4) for v in fitz.Rect(value) * transform]

    words = [{"id": i, "text": w[4], "bbox": box(w[:4]), "block": w[5], "line": w[6], "word": w[7]}
             for i, w in enumerate(page.get_text("words", clip=fitz.INFINITE_RECT()))]
    spans = []
    for bi, block in enumerate(page.get_text("dict", flags=0, clip=fitz.INFINITE_RECT())["blocks"]):
        if block["type"] != 0:
            continue
        for li, line in enumerate(block["lines"]):
            for si, span in enumerate(line["spans"]):
                spans.append({"id": len(spans), "block": bi, "line": li, "span": si,
                              "text": span["text"], "bbox": box(span["bbox"]),
                              "font": span["font"], "direction": list(line["dir"])})
    return words, spans


def capture_ocr_page(pdf: Path, filing: Filing, number: int, model_directory: Path, *,
                     dpi: int = 300, language: str = "eng+tur", **provenance) -> tuple[dict, bytes]:
    """Keep source pixels and raw recognition in a reviewable, unverified artifact."""
    if dpi not in (300, 450, 600):
        raise ValueError("OCR DPI must be 300, 450 or 600")
    if language not in ("eng", "tur", "eng+tur", "tur+eng"):
        raise ValueError("OCR language must use the pinned English/Turkish models")
    identity = source_identity(pdf, filing, **provenance)
    lock = ensure_models(model_directory)
    with fitz.open(pdf) as original:
        if not 1 <= number <= len(original):
            raise ValueError("OCR page is outside the source PDF")
        source_page = original[number - 1]
        pix = source_page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
        derivative = pix.pdfocr_tobytes(language=language, tessdata=str(model_directory.resolve()))
        with fitz.open(stream=derivative) as recovered:
            words, spans = _observations(recovered[0], source_page.rect.width, source_page.rect.height)
        record = {"schema_version": OCR_VERSION, "source": identity, "page": number,
                  "width": source_page.rect.width, "height": source_page.rect.height,
                  "rotation": source_page.rotation, "coordinate_space": "display",
                  "engine": _engine(lock, dpi, language),
                  "render": {"width": pix.width, "height": pix.height, "channels": pix.n,
                             "pixels_sha256": _sha(pix.samples)},
                  "ocr_pdf_sha256": _sha(derivative), "words": words, "spans": spans,
                  "recognition_verified": False, "association_verified": False,
                  "status": "ocr_candidates", "confidence": None}
    if source_identity(pdf, filing, **provenance) != identity:
        raise ValueError("Source PDF changed during OCR")
    return record, derivative


def verify_ocr_page(record: dict, derivative: bytes, source_pdf: Path | None = None) -> dict:
    """Verify retention against the image-bearing OCR PDF, not model correctness."""
    errors = []
    if record.get("schema_version") != OCR_VERSION:
        return {"valid": False, "errors": ["Unsupported OCR observation"]}
    if (any(not isinstance(record.get(key), (int, float)) or not math.isfinite(record[key]) or record[key] <= 0
            for key in ("width", "height")) or type(record.get("page")) is not int or record["page"] < 1):
        return {"valid": False, "errors": ["Invalid OCR source page geometry"]}
    if (record.get("recognition_verified") is not False or record.get("association_verified") is not False
            or record.get("status") != "ocr_candidates" or record.get("confidence") is not None):
        errors.append("OCR observation claims unsupported recognition/association approval")
    if _sha(derivative) != record.get("ocr_pdf_sha256"):
        errors.append("OCR PDF bytes do not match the observation")
    try:
        with fitz.open(stream=derivative) as recovered:
            if len(recovered) != 1:
                errors.append("OCR derivative must contain one page")
            words, spans = _observations(recovered[0], record["width"], record["height"])
            if words != record["words"] or spans != record["spans"]:
                errors.append("OCR word/span inventory differs from its retained PDF")
            images = recovered[0].get_images()
            if len(images) != 1:
                errors.append("OCR derivative must retain its single rendered source image")
            else:
                pix = fitz.Pixmap(recovered, images[0][0])
                if {"width": pix.width, "height": pix.height, "channels": pix.n,
                    "pixels_sha256": _sha(pix.samples)} != record["render"]:
                    errors.append("OCR derivative image does not match the rendered source pixels")
        for item in record["words"] + record["spans"]:
            if not all(math.isfinite(v) for v in item["bbox"]):
                errors.append("OCR geometry contains nonfinite coordinates")
                break
        if source_pdf is not None:
            source = record["source"]
            filing = Filing(source["bank_ticker"], source["period"], source["kind"])
            actual = source_identity(source_pdf, filing)
            if (actual["pdf_sha256"], actual["byte_count"]) != (source["pdf_sha256"], source["byte_count"]):
                errors.append("OCR observation is for different source bytes")
            else:
                with fitz.open(source_pdf) as original:
                    page = original[record["page"] - 1]
                    if (page.rect.width, page.rect.height, page.rotation) != (
                            record["width"], record["height"], record["rotation"]):
                        errors.append("OCR observation has wrong source page geometry")
                    pix = page.get_pixmap(dpi=record["engine"]["dpi"], colorspace=fitz.csRGB, alpha=False)
                    if _sha(pix.samples) != record["render"]["pixels_sha256"]:
                        errors.append("OCR rendered image differs from the original PDF page")
    except (ValueError, RuntimeError, IndexError, KeyError, TypeError) as error:
        errors.append(f"Invalid OCR observation: {error}")
    return {"valid": not errors, "errors": errors, "recognition_verified": False}


def check_ocr_annotations(record: dict, directory: Path) -> dict:
    """Check only explicitly transcribed tokens and their visual source regions.

    Extra punctuation remains visible in matched words; this deliberately does
    not certify a cleaned cell, its sign, other text, or the whole table.
    """
    if not directory.is_dir():
        raise ValueError("OCR source annotation directory is missing")
    source = record["source"]
    identity = {key: source[key] for key in ("bank_ticker", "period", "kind")}
    checks = []
    same_filing = False
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
            if case["kind"] != "token_in_region":
                raise ValueError("Unsupported OCR annotation kind")
            x0, y0, x1, y1 = case["source_bbox"]
            pattern = re.compile(r"(?<!\w)" + re.escape(case["token"]) + r"(?!\w)")
            matches = [word for word in record["words"]
                       if x0 <= (word["bbox"][0] + word["bbox"][2]) / 2 <= x1
                       and y0 <= (word["bbox"][1] + word["bbox"][3]) / 2 <= y1
                       and pattern.search(word["text"])]
            checks.append({"id": case["id"], "passed": len(matches) == 1,
                           "matched_words": matches, "full_cell_verified": False})
    return {"status": ("passed" if all(c["passed"] for c in checks) else "failed") if checks else
            ("source_revision_or_page_unannotated" if same_filing else "not_annotated"),
            "scope": "annotated_tokens_and_regions_only", "checks": checks,
            "recognition_verified": False}
