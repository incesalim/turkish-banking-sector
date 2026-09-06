import gzip
import hashlib
import json

import pytest

from src.audit_reports.document_quality import bank_patterns
from src.audit_reports.document_structure import build_document_structure
from test_document_corpus_store import corpus  # noqa: F401
from review_document_corpus import review_filing


@pytest.fixture
def published(corpus):  # noqa: F811
    store, client, filing, original, evidence, artifact = corpus
    client.objects[evidence[0]['source']['object_key']] = original.read_bytes()
    store.publish(evidence, original, artifact)
    store.publish_structure(build_document_structure(original, evidence), evidence)
    return store, client, filing, evidence[0]['source']['object_key']


def review(published):
    store, _client, filing, key = published
    return review_filing(store, filing, key, bank_patterns({'TEST': {'name': 'Test Bank A.Ş.'}}))


def test_review_reads_both_pdf_copies_and_retained_page_bytes_without_writes(published):
    store, client, filing, key = published
    writes = list(client.writes)
    result = review(published)
    assert client.writes == writes
    assert key in client.reads and store.read_index(filing)['current']['original_key'] in client.reads
    assert result['source_pdf_copies_byte_verified'] is True
    assert result['source_artifact_byte_verified'] is True and result['structure_artifact_byte_verified'] is True
    assert result['counts']['pages'] == 1 and result['counts']['native_words'] > 0
    assert result['identity']['status'] == 'unresolved'  # Synthetic PDF has no report cover.
    assert result['recovery']['index_present'] is False
    assert result['recovery']['selection_completeness_verified'] is False
    assert result['semantic_verification'] == 'not_performed'


@pytest.mark.parametrize('change', ['acquisition', 'original', 'source_bytes', 'structure_bytes',
                                  'source_page_dropped', 'structure_page_dropped', 'source_binding'])
def test_changed_source_bytes_or_damaged_retained_pages_cannot_pass_review(published, change):
    store, client, filing, acquisition = published
    index = store.read_index(filing)
    current = index['current']
    if change in ('acquisition', 'original', 'source_bytes', 'structure_bytes'):
        key = {'acquisition': acquisition, 'original': current['original_key'],
               'source_bytes': current['evidence_key'], 'structure_bytes': current['structure_current']['key']}[change]
        client.objects[key] += b' changed'
    elif change == 'source_binding':
        current['source']['period'] = '2026Q2'
    else:
        structured = change == 'structure_page_dropped'
        key = current['structure_current']['key'] if structured else current['evidence_key']
        lines = gzip.decompress(client.objects[key]).splitlines(keepends=True)
        body = gzip.compress(b''.join(lines[:-1]), mtime=0)
        client.objects[key] = body
        target = current['structure_current'] if structured else current
        target['bytes_sha256' if structured else 'evidence_bytes_sha256'] = hashlib.sha256(body).hexdigest()
    if change in ('source_page_dropped', 'structure_page_dropped', 'source_binding'):
        client.objects[store.index_key(filing)] = json.dumps(index).encode()
    with pytest.raises(ValueError):
        review(published)


def test_uncaptured_filing_is_named_without_becoming_zero_content(published):
    store, client, filing, key = published
    del client.objects[store.index_key(filing)]
    result = review(published)
    assert result == {'filing': filing.as_dict(), 'status': 'capture_missing'}


def test_source_transcription_disagreement_is_retained_in_quality_review(published):
    from src.audit_reports.document_recovery import RecoveryStore
    store, client, filing, _key = published
    source = {**store.read_index(filing)['current']['source'], 'source_url': None, 'object_key': None}
    check = {'id': 'bank', 'passed': False, 'source_transcription': 'İstanbul', 'observed_text': 'Istanbul'}
    index = {'schema_version': 'corpus-recovery-index-1', 'source': source, 'selections': [],
             'pages': {'1': {'current': {'benchmarks': {'text_regions': {'checks': [check]}}}}}}
    client.objects[RecoveryStore.index_key(source)] = json.dumps(index).encode()
    result = review(published)
    assert result['recovery']['source_text_disagreements'] == [{'page': 1, 'checks': [check]}]
    assert result['semantic_verification'] == 'not_performed'


def test_full_local_review_is_refused(monkeypatch):
    from review_document_corpus import main
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    with pytest.raises(SystemExit):
        main([])
