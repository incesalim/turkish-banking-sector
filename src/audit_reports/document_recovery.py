"""Durable, source-bound OCR/outline observations, separate from native capture.

Recovery never clears source issues or approves a financial value. Its own index
allows page-level retries without changing core capture indexes or serving data.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from .document_corpus import Filing, source_identity
from .document_corpus_store import CorpusStore, PREFIX, _error_code, _json
from .document_ocr import verify_ocr_page
from .document_vector import atlas_digest, verify_vector_page


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def recovery_identity(ocr_engine: dict, atlas: dict | None) -> dict:
    return {"ocr": ocr_engine, "atlas_sha256": atlas_digest(atlas) if atlas else None,
            "vector_implementation_sha256": digest(Path(__file__).with_name("document_vector.py").read_bytes())
            if atlas else None, "implementation_sha256": digest(Path(__file__).read_bytes())}


def recovery_view(ocr: dict, vector: dict | None) -> dict:
    """Retain OCR line membership; expose disagreement without rewriting either read."""
    groups = {}
    for word in ocr["words"]:
        groups.setdefault((word["block"], word["line"]), []).append(word)
    lines = []
    for (block, line), words in groups.items():
        boxes = [w["bbox"] for w in words]
        lines.append({"id": f"ocr:{block}:{line}", "word_ids": [w["id"] for w in words],
                      "text": " ".join(w["text"] for w in words),
                      "bbox": [min(b[0] for b in boxes), min(b[1] for b in boxes),
                               max(b[2] for b in boxes), max(b[3] for b in boxes)]})
    comparisons = []
    for path in (vector or {}).get("matched_paths", []):
        x0, y0, x1, y1 = path["bbox"]
        # A comparison region is a candidate association, not a table cell.
        words = [w for w in ocr["words"] if x0 - 2 <= (w["bbox"][0] + w["bbox"][2]) / 2 <= x1 + 2
                 and y0 - 2 <= (w["bbox"][1] + w["bbox"][3]) / 2 <= y1 + 2]
        words.sort(key=lambda w: (w["bbox"][0], w["id"]))
        observed = "".join(w["text"] for w in words) if words else None
        comparisons.append({"drawing_id": path["drawing_id"], "bbox": path["bbox"],
                            "vector_text": path["text"], "ocr_word_ids": [w["id"] for w in words],
                            "ocr_text": observed, "status": "missing_ocr" if observed is None else
                            "exact_agreement" if observed == path["text"] else "disagreement",
                            "recognition_verified": False, "association_verified": False})
    return {"lines": lines, "vector_comparisons": comparisons,
            "reading_order_verified": False, "table_structure_verified": False}


def make_packet(ocr: dict, vector: dict | None, benchmarks: dict, engine: dict) -> dict:
    if vector and (vector["source"] != ocr["source"] or vector["page"] != ocr["page"]):
        raise ValueError("Recovery observations refer to different source pages")
    return {"schema_version": "source-recovery-page-1", "source": ocr["source"], "page": ocr["page"],
            "width": ocr["width"], "height": ocr["height"], "coordinate_space": "display",
            "engine": engine, "ocr": ocr, "vector": vector, "view": recovery_view(ocr, vector),
            "benchmarks": benchmarks, "status": "recovery_candidates", "semantically_verified": False}


def verify_packet(packet: dict, derivative: bytes, original: Path, atlas: dict | None) -> None:
    if (packet.get("schema_version") != "source-recovery-page-1"
            or packet.get("status") != "recovery_candidates" or packet.get("semantically_verified") is not False):
        raise ValueError("Invalid recovery packet or unsupported approval")
    ocr, vector = packet["ocr"], packet["vector"]
    if packet != make_packet(ocr, vector, packet["benchmarks"], packet["engine"]):
        raise ValueError("Recovery view differs from its retained observations")
    if packet["engine"] != recovery_identity(ocr["engine"], atlas):
        raise ValueError("Recovery engine or reference changed")
    check = verify_ocr_page(ocr, derivative, original)
    if not check["valid"]:
        raise ValueError(f"Invalid OCR retention: {check['errors']}")
    if vector:
        if atlas is None or not verify_vector_page(vector, original, atlas)["valid"]:
            raise ValueError("Invalid vector retention or missing reference")
    elif atlas is not None:
        raise ValueError("Reference atlas supplied without a vector observation")


class RecoveryStore:
    def __init__(self, store: CorpusStore):
        self.store = store

    @staticmethod
    def index_key(source: dict) -> str:
        filing = Filing(source["bank_ticker"], source["period"], source["kind"])
        if len(source["pdf_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in source["pdf_sha256"]):
            raise ValueError("Invalid recovery source hash")
        return (f"{PREFIX}recovery/{filing.bank_ticker}/{filing.period}/{filing.kind}/"
                f"{source['pdf_sha256']}.json")

    def read_index(self, source: dict) -> dict | None:
        body, _ = self.store._read(self.index_key(source))
        if body is None:
            return None
        index = json.loads(body)
        if index.get("schema_version") != "corpus-recovery-index-1" or index.get("source") != source:
            raise ValueError("Recovery index differs from its source")
        return index

    def _update(self, source: dict, update) -> dict:
        key = self.index_key(source)
        for _ in range(8):
            previous, etag = self.store._read(key)
            index = json.loads(previous) if previous else {
                "schema_version": "corpus-recovery-index-1", "source": source,
                "pages": {}, "selections": [], "semantically_verified": False}
            if index.get("source") != source or index.get("schema_version") != "corpus-recovery-index-1":
                raise ValueError("Recovery index differs from its source")
            update(index)
            body = _json(index)
            if body == previous:
                return index
            try:
                self.store.client.put_object(Bucket=self.store.bucket, Key=key, Body=body,
                                             ContentType="application/json",
                                             **({"IfMatch": etag} if etag else {"IfNoneMatch": "*"}))
                return index
            except Exception as error:
                if _error_code(error) not in ("412", "PreconditionFailed"):
                    raise
        raise RuntimeError("Recovery index changed concurrently; retry this page")

    def record_selection(self, source: dict, selection: dict) -> dict:
        def update(index):
            if selection not in index["selections"]:
                index["selections"].append(selection)
        return self._update(source, update)

    def record_failure(self, source: dict, page: int, error: str) -> dict:
        def update(index):
            row = index["pages"].setdefault(str(page), {"current": None, "revisions": []})
            row["last_attempt"] = {"status": "failed", "error": error}
        return self._update(source, update)

    def publish(self, packet: dict, derivative: bytes, original: Path, *,
                atlas: dict | None = None, reference: Path | None = None) -> dict:
        verify_packet(packet, derivative, original, atlas)
        source = packet["source"]
        base = f"{PREFIX}sources/{source['pdf_sha256']}/"
        self.store._immutable(base + "original.pdf", original.read_bytes(), "application/pdf")
        artifacts = {}

        def put(name, body, suffix, content_type):
            sha = digest(body)
            key = base + f"recovery/{sha}.{suffix}"
            self.store._immutable(key, body, content_type)
            artifacts[name] = {"key": key, "sha256": sha, "bytes": len(body)}

        put("ocr_pdf", derivative, "ocr.pdf", "application/pdf")
        if atlas:
            if reference is None:
                raise ValueError("Vector recovery requires its original reference PDF")
            expected = atlas["source"]
            filing = Filing(expected["bank_ticker"], expected["period"], expected["kind"])
            actual = source_identity(reference, filing)
            if actual != expected:
                raise ValueError("Vector reference original differs from its atlas")
            ref_key = f"{PREFIX}sources/{expected['pdf_sha256']}/original.pdf"
            self.store._immutable(ref_key, reference.read_bytes(), "application/pdf")
            artifacts["reference_pdf"] = {"key": ref_key, "sha256": expected["pdf_sha256"], "bytes": expected["byte_count"]}
            put("atlas", gzip.compress(_json(atlas), mtime=0), "atlas.json.gz", "application/gzip")
        body = gzip.compress(_json(packet), mtime=0)
        put("page", body, "recovery.json.gz", "application/gzip")
        revision = {"page": packet["page"], "engine": packet["engine"], "artifacts": artifacts,
                    "benchmarks": packet["benchmarks"], "status": "recovery_candidates",
                    "ocr_words": len(packet["ocr"]["words"]),
                    "vector_words": len((packet["vector"] or {}).get("matched_paths", [])),
                    "disagreements": sum(c["status"] != "exact_agreement" for c in packet["view"]["vector_comparisons"]),
                    "semantically_verified": False}

        def update(index):
            row = index["pages"].setdefault(str(packet["page"]), {"current": None, "revisions": []})
            if revision not in row["revisions"]:
                row["revisions"].append(revision)
            row["current"] = revision
            row["last_attempt"] = {"status": "recovery_candidates"}
        return self._update(source, update)

    def cached(self, source: dict, page: int, engine: dict, original: Path,
               atlas: dict | None) -> tuple[dict, bytes] | None:
        index = self.read_index(source)
        row = (index or {}).get("pages", {}).get(str(page))
        if not row or not row["current"] or row.get("last_attempt", {}).get("status") == "failed":
            return None
        revision = row["current"]
        # A view/association code change must not needlessly run OCR again.
        # Compare recognition inputs, verify retained raw observations, then
        # rebuild the current view. No previous view is carried forward as truth.
        if any(revision['engine'].get(k) != engine.get(k) for k in (
                'ocr', 'atlas_sha256', 'vector_implementation_sha256')):
            return None
        loaded = {}
        for name, item in revision["artifacts"].items():
            suffix = {'page': 'recovery.json.gz', 'ocr_pdf': 'ocr.pdf', 'atlas': 'atlas.json.gz'}.get(name)
            expected = (f"{PREFIX}sources/{item['sha256']}/original.pdf" if name == 'reference_pdf' else
                        f"{PREFIX}sources/{source['pdf_sha256']}/recovery/{item['sha256']}.{suffix}" if suffix else None)
            if item['key'] != expected:
                raise ValueError("Recovery artifact key differs from its source/content identity")
            body, _ = self.store._read(item["key"])
            if body is None or len(body) != item["bytes"] or digest(body) != item["sha256"]:
                return None
            loaded[name] = body
        packet = json.loads(gzip.decompress(loaded["page"]))
        if atlas is not None and json.loads(gzip.decompress(loaded["atlas"])) != atlas:
            raise ValueError("Stored atlas differs from the source-rebuilt reference")
        if packet["source"] != source or packet["page"] != page:
            raise ValueError("Cached recovery is for a different page")
        if packet['engine'] != revision['engine']:
            raise ValueError("Recovery index and packet engines disagree")
        rebuilt = make_packet(packet['ocr'], packet['vector'], packet['benchmarks'], engine)
        verify_packet(rebuilt, loaded["ocr_pdf"], original, atlas)
        return rebuilt, loaded["ocr_pdf"]
