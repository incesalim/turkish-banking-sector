import copy
import hashlib
import io
from datetime import datetime, timedelta, timezone

import fitz
import pytest

from src.audit_reports.document_corpus import Filing
from src.audit_reports.document_corpus_store import CorpusStore, PREFIX
from src.audit_reports.document_evidence import capture_source_evidence, save_evidence


class ClientError(Exception):
    def __init__(self, response, operation):
        super().__init__(operation)
        self.response = response


class MemoryR2:
    def __init__(self):
        self.objects = {}
        self.writes = []
        self.fail_key = None
        self.versions = {}
        self.reads = []

    @staticmethod
    def etag(body):
        return '"' + hashlib.sha256(body).hexdigest() + '"'

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        body = self.objects[Key]
        self.reads.append(Key)
        return {"Body": io.BytesIO(body), **self.head_object(Bucket=Bucket, Key=Key)}

    def head_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")
        body = self.objects[Key]
        return {"ETag": self.etag(body), "ContentLength": len(body),
                "LastModified": datetime(2026, 1, 1, tzinfo=timezone.utc)
                + timedelta(seconds=self.versions.get(Key, 0))}

    def put_object(self, *, Bucket, Key, Body, ContentType, IfNoneMatch=None, IfMatch=None):
        if Key == self.fail_key:
            raise RuntimeError("Injected upload interruption")
        old = self.objects.get(Key)
        if (IfNoneMatch == "*" and old is not None) or (
                IfMatch is not None and (old is None or self.etag(old) != IfMatch)):
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        self.objects[Key] = Body
        self.versions[Key] = self.versions.get(Key, 0) + 1
        self.writes.append(Key)


@pytest.fixture
def corpus(tmp_path):
    filing = Filing("TEST", "2026Q1", "consolidated")
    pdf = tmp_path / filing.filename
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 80), "Source version one 1,000")
        doc.save(pdf)
    records = capture_source_evidence(pdf, filing, object_key="test/" + filing.filename)
    evidence = tmp_path / "evidence.jsonl.gz"
    save_evidence(records, evidence)
    client = MemoryR2()
    return CorpusStore(client, "test-bucket"), client, filing, pdf, records, evidence


def test_publish_is_incremental_and_does_not_promote_semantic_trust(corpus):
    store, client, filing, pdf, records, evidence = corpus
    first = store.publish(records, pdf, evidence)
    assert len(client.writes) == 3
    assert client.writes[-1] == store.index_key(filing)
    assert all(key.startswith(PREFIX) for key in client.objects)
    assert first["current"]["semantic_verification"] == "not_performed"
    assert store.publish(records, pdf, evidence) == first
    assert len(client.writes) == 3
    assert store.cached_evidence(records[0]["source"], records[0]["engine"]) == records


def test_changed_source_or_engine_cannot_reuse_old_evidence(corpus):
    store, client, filing, pdf, records, evidence = corpus
    store.publish(records, pdf, evidence)
    changed = {**records[0]["source"], "pdf_sha256": "0" * 64}
    assert store.cached_evidence(changed, records[0]["engine"]) is None
    changed_engine = {**records[0]["engine"], "implementation_sha256": "0" * 64}
    assert store.cached_evidence(records[0]["source"], changed_engine) is None


def test_failed_upload_never_creates_a_dangling_index_and_resumes(corpus):
    store, client, filing, pdf, records, evidence = corpus
    from src.audit_reports.document_evidence import artifact_digest
    client.fail_key = (f"{PREFIX}sources/{records[0]['source']['pdf_sha256']}/"
                       f"{artifact_digest(records)}.jsonl.gz")
    with pytest.raises(RuntimeError, match="interruption"):
        store.publish(records, pdf, evidence)
    assert store.index_key(filing) not in client.objects
    assert len(client.objects) == 1  # original is safe to reuse on retry
    client.fail_key = None
    store.publish(records, pdf, evidence)
    assert len(client.writes) == 3


def test_failure_keeps_good_source_and_repeated_failure_does_not_write(corpus):
    store, client, filing, pdf, records, evidence = corpus
    good = store.publish(records, pdf, evidence)
    failed = store.record_failure(filing, "PDF requires password")
    assert failed["current"] == good["current"]
    assert failed["revisions"] == good["revisions"]
    assert failed["last_attempt"]["status"] == "failed"
    count = len(client.writes)
    store.record_failure(filing, "PDF requires password")
    assert len(client.writes) == count


def test_revisions_are_retained_and_limited_runs_do_not_erase_other_filings(corpus):
    store, client, filing, pdf, records, evidence = corpus
    first = store.publish(records, pdf, evidence)
    changed = copy.deepcopy(records)
    changed[0]["engine"]["implementation_sha256"] = "0" * 64
    save_evidence(changed, evidence)
    second = store.publish(changed, pdf, evidence)
    assert len(second["revisions"]) == 2
    assert first["current"] in second["revisions"]
    other = Filing("OTHER", "2026Q1", "consolidated")
    store.record_failure(other, "missing source")
    unchanged = client.objects[store.index_key(other)]
    store.publish(changed, pdf, evidence)
    assert client.objects[store.index_key(other)] == unchanged


def test_corrupt_cached_evidence_cannot_be_skipped_or_overwritten(corpus):
    store, client, filing, pdf, records, evidence = corpus
    index = store.publish(records, pdf, evidence)
    client.objects[index["current"]["evidence_key"]] = b"corrupt"
    with pytest.raises(ValueError, match="corrupted"):
        store.cached_evidence(records[0]["source"], records[0]["engine"])
    with pytest.raises(ValueError, match="different content"):
        store.publish(records, pdf, evidence)


def test_mismatched_original_or_artifact_is_refused_before_upload(corpus):
    store, client, filing, pdf, records, evidence = corpus
    original = pdf.read_bytes()
    pdf.write_bytes(original + b"changed")
    with pytest.raises(ValueError, match="does not match"):
        store.publish(records, pdf, evidence)
    assert not client.writes
    pdf.write_bytes(original)
    changed = copy.deepcopy(records)
    changed[0]["engine"]["implementation_sha256"] = "0" * 64
    save_evidence(changed, evidence)
    with pytest.raises(ValueError, match="does not match"):
        store.publish(records, pdf, evidence)
    assert not client.writes


def test_store_rejects_access_outside_its_own_namespace(corpus):
    store, client, *_ = corpus
    with pytest.raises(ValueError, match="outside"):
        store._immutable("state/bank_audit.db.gz", b"bad", "application/gzip")
    assert not client.writes


def test_access_denied_is_not_relabelled_as_a_missing_object(corpus, monkeypatch):
    store, client, filing, *_ = corpus

    def forbidden(**kwargs):
        raise ClientError({"Error": {"Code": "AccessDenied"}}, "GetObject")

    monkeypatch.setattr(client, "get_object", forbidden)
    with pytest.raises(ClientError):
        store._read(store.index_key(filing))


def test_structure_is_source_bound_and_replay_writes_nothing(corpus):
    from src.audit_reports.document_structure import build_document_structure
    store, client, filing, pdf, records, evidence = corpus
    structure = build_document_structure(pdf, records)
    store.publish(records, pdf, evidence)
    index = store.publish_structure(structure, records)
    assert index["current"]["structure_current"]["status"] == "structured_candidates"
    assert store.cached_structure(records, structure["engine"]) == structure
    writes = len(client.writes)
    store.publish(records, pdf, evidence)
    repeated = store.publish_structure(structure, records)
    assert len(client.writes) == writes
    assert len(repeated["revisions"]) == 1
    assert len(repeated["current"]["structure_revisions"]) == 1
    changed_engine = {**structure["engine"], "implementation_sha256": "0" * 64}
    assert store.cached_structure(records, changed_engine) is None


def test_corrupt_structure_is_never_reused(corpus):
    from src.audit_reports.document_structure import build_document_structure
    store, client, filing, pdf, records, evidence = corpus
    structure = build_document_structure(pdf, records)
    store.publish(records, pdf, evidence)
    index = store.publish_structure(structure, records)
    key = index["current"]["structure_current"]["key"]
    client.objects[key] = b"broken"
    with pytest.raises(ValueError, match="corrupted"):
        store.cached_structure(records, structure["engine"])


def test_concurrent_filing_index_update_keeps_both_failures_and_revision(corpus, monkeypatch):
    store, client, filing, pdf, records, evidence = corpus
    store.record_failure(filing, "original failure")
    real_put = client.put_object
    raced = False

    def put_with_race(**kwargs):
        nonlocal raced
        if kwargs["Key"] == store.index_key(filing) and not raced:
            raced = True
            store.record_failure(filing, "concurrent update")
        return real_put(**kwargs)

    monkeypatch.setattr(client, "put_object", put_with_race)
    index = store.publish(records, pdf, evidence)
    assert raced
    assert len(index["revisions"]) == 1
    assert index["last_attempt"]["status"] == "source_preserved"
    assert [f["error"] for f in index["failed_attempts"]] == ["original failure", "concurrent update"]


def test_cli_publication_and_restart_use_verified_cache_without_any_rewrite(corpus, tmp_path, monkeypatch):
    import json
    import build_document_corpus as build
    from src.audit_reports import document_evidence, r2_storage
    store, client, filing, pdf, records, evidence = corpus
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"banks": {"TEST": {"urls": {"consolidated": {
        "2026Q1": "https://bank.example/report.pdf"}}}}}))
    key = "test/" + filing.filename
    payload = pdf.read_bytes()
    client.objects[key] = payload
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(r2_storage, "get_client", lambda: client)
    monkeypatch.setattr(r2_storage, "_bucket", lambda: "test-bucket")
    monkeypatch.setattr(r2_storage, "list_audit_pdfs", lambda: [("TEST", "2026Q1", "consolidated", key)])
    monkeypatch.setattr(r2_storage, "download_to", lambda _key, dest: dest.write_bytes(payload))
    args = ["--config", str(config), "--from-r2", "--capture", "--publish", "--structure",
            "--discard-published", "--source-dir", str(tmp_path), "--output-dir", str(tmp_path / "out")]
    assert build.main(args) == 0
    writes = len(client.writes)

    def must_not_extract(*args, **kwargs):
        raise AssertionError("Unchanged verified source should be reused")

    monkeypatch.setattr(document_evidence, "capture_source_evidence", must_not_extract)
    client.reads.clear()
    assert build.main(args) == 0
    assert len(client.writes) == writes
    result = json.loads((tmp_path / "out/capture-results.json").read_text())["filings"][0]
    assert result["evidence_reused"] is True
    assert result["reuse_check"] == "verified_object_versions_unchanged"
    assert key not in client.reads
    assert result["status"] == "structured_candidates"
    assert not (tmp_path / "out" / result["original"]).exists()
    client.reads.clear()
    assert build.main(args + ["--recheck-bytes"]) == 0
    assert key in client.reads
    assert len(client.writes) == writes
