import copy
import json
from pathlib import Path

import pytest

from src.audit_reports.document_corpus import Filing
from src.audit_reports.document_corpus_resume import metadata
from src.audit_reports.document_recovery_resume import (
    annotation_identity, record_receipt, request_identity, unchanged_receipt,
)
from test_document_recovery import recovery  # noqa: F401
from test_document_ocr import retained_observation  # noqa: F401

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def published(recovery):  # noqa: F811
    store, client, packet, derivative, original = recovery
    filing = Filing('TEST', '2026Q1', 'consolidated')
    key = 'audit-pdfs/' + filing.filename
    client.objects[key] = original.read_bytes()
    store.publish(packet, derivative, original)
    selection = {'method': 'explicit', 'page_count': 1, 'pages': [1],
                 'selection_completeness_verified': False}
    store.record_selection(packet['source'], selection)
    request = request_identity(REPO, packet['engine']['ocr'], [1])
    acquisition = metadata(key, client.head_object(Bucket='test', Key=key))
    return store, client, filing, original, acquisition, selection, request


def record(published):
    store, _client, filing, original, acquisition, selection, request = published
    return record_receipt(store, filing, original, acquisition, selection, request, 'annotations-one')


def resume(published):
    store, _client, filing, _original, acquisition, _selection, request = published
    return unchanged_receipt(store, filing, acquisition['key'], request, 'annotations-one')


def test_resume_requires_readback_and_uses_only_receipt_body_and_object_metadata(published):
    store, client, *_ = published
    assert resume(published) is None
    expected = record(published)
    writes = list(client.writes)
    client.reads.clear()
    assert resume(published) == expected
    assert len(client.reads) == 2 and '/recovery-receipts/' in client.reads[0]
    assert '/recovery/' in client.reads[1]
    assert expected['semantically_verified'] is False
    assert expected['selection']['selection_completeness_verified'] is False
    assert record(published) == expected
    assert client.writes == writes


@pytest.mark.parametrize('change', ['source', 'source_timestamp', 'page', 'missing_ocr',
                                  'index', 'failure', 'request', 'annotations', 'scope'])
def test_changed_inputs_missing_artifacts_and_failed_pages_invalidate_receipt(published, change):
    store, client, filing, _original, acquisition, _selection, request = published
    saved = record(published)
    current = store.read_index(saved['source'])['pages']['1']['current']
    if change == 'source':
        client.objects[acquisition['key']] += b' changed'
    elif change == 'source_timestamp':
        client.versions[acquisition['key']] = 1
    elif change == 'page':
        client.objects[current['artifacts']['page']['key']] += b' corrupted'
    elif change == 'missing_ocr':
        del client.objects[current['artifacts']['ocr_pdf']['key']]
    elif change == 'index':
        client.versions[store.index_key(saved['source'])] += 1
    elif change == 'failure':
        store.record_failure(saved['source'], 1, 'Later recognition failed')
    elif change == 'request':
        request['numpy'] = 'different-runtime'
    elif change == 'scope':
        request['pages'] = []
    else:
        assert unchanged_receipt(store, filing, acquisition['key'], request, 'changed-annotations') is None
        return
    assert resume(published) is None


@pytest.mark.parametrize('change', ['corruption', 'changed_source', 'failed_page', 'missing_page',
                                  'changed_derived_engine', 'foreign_key'])
def test_invalid_publication_cannot_receive_a_receipt(published, change):
    store, client, filing, original, acquisition, selection, request = published
    from src.audit_reports.document_corpus import source_identity
    source = source_identity(original, filing)
    index = store.read_index(source)
    if change == 'corruption':
        client.objects[index['pages']['1']['current']['artifacts']['page']['key']] += b' corrupt'
    elif change == 'changed_source':
        client.objects[acquisition['key']] += b' revised'
    elif change == 'failed_page':
        store.record_failure(source, 1, 'Failed source annotation')
    elif change == 'missing_page':
        index['pages'] = {}
    elif change == 'changed_derived_engine':
        index['pages']['1']['current']['engine']['table_implementation_sha256'] = '0' * 64
    else:
        index['pages']['1']['current']['artifacts']['page']['key'] = 'foreign/packet.gz'
    if change in ('missing_page', 'changed_derived_engine', 'foreign_key'):
        client.objects[store.index_key(source)] = json.dumps(index).encode()
    with pytest.raises(ValueError):
        record(published)
    assert not any('/recovery-receipts/' in key for key in client.objects)


@pytest.mark.parametrize('method', ['image_outline_detector', 'source_content_detector'])
def test_no_selected_pages_still_requires_source_and_selection_versions(published, method):
    store, client, filing, original, acquisition, selection, request = published
    selection = {**selection, 'method': method, 'pages': []}
    request = {**request, 'pages': []}
    from src.audit_reports.document_corpus import source_identity
    store.record_selection(source_identity(original, filing), selection)
    result = record_receipt(store, filing, original, acquisition, selection, request, 'annotations-one')
    assert result['status'] == 'no_pages_flagged' and result['pages'] == []
    assert len(result['artifacts']) == 2  # Original and versioned selector evidence.
    assert unchanged_receipt(store, filing, acquisition['key'], request, 'annotations-one') == result


def test_annotation_fingerprint_is_per_filing_and_missing_directory_fails(tmp_path):
    for name in ('document_ocr_annotations', 'document_vector_annotations'):
        (tmp_path / 'tests/fixtures' / name).mkdir(parents=True)
    filing = Filing('TEST', '2026Q1', 'consolidated')
    other = Filing('OTHER', '2026Q1', 'consolidated')
    before = annotation_identity(tmp_path, filing)
    path = tmp_path / 'tests/fixtures/document_ocr_annotations/cases.json'
    path.write_text(json.dumps({'filing': other.as_dict(), 'cases': [1]}))
    assert annotation_identity(tmp_path, filing) == before
    path.write_text(json.dumps({'filing': filing.as_dict(), 'cases': [1]}))
    changed = annotation_identity(tmp_path, filing)
    assert changed != before
    path.write_text(json.dumps({'filing': filing.as_dict(), 'cases': [2]}))
    assert annotation_identity(tmp_path, filing) != changed
    with pytest.raises(ValueError, match='directory'):
        annotation_identity(tmp_path / 'absent', filing)


def test_explicit_page_order_has_one_scope_but_other_requests_do_not(published):
    from src.audit_reports.document_recovery_resume import receipt_key
    _store, _client, filing, *_rest, request = published
    a = request_identity(REPO, request['ocr_engine'], [3, 1])
    b = request_identity(REPO, request['ocr_engine'], [1, 3])
    assert a == b and receipt_key(filing, a) == receipt_key(filing, b)
    changed = copy.deepcopy(a)
    changed['pages'] = []
    assert receipt_key(filing, changed) != receipt_key(filing, a)


def test_dropped_receipt_artifact_cannot_turn_off_its_version_check(published):
    from src.audit_reports.document_recovery_resume import receipt_key
    _store, client, filing, *_rest, request = published
    saved = record(published)
    key = receipt_key(filing, request)
    removed = next(t for t in saved['artifacts'] if t['key'].endswith('.ocr.pdf'))
    saved['artifacts'].remove(removed)
    client.objects[key] = json.dumps(saved).encode()
    assert resume(published) is None
