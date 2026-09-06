import copy
import gzip
import json

import pytest

from src.audit_reports.document_corpus_store import CorpusStore, PREFIX
from src.audit_reports.document_recovery import RecoveryStore, make_packet, recovery_identity, recovery_view
from test_document_corpus_store import MemoryR2
from test_document_ocr import retained_observation  # noqa: F401


@pytest.fixture
def recovery(retained_observation):  # noqa: F811
    ocr, derivative, original = retained_observation
    packet = make_packet(ocr, None, {"ocr": {"status": "not_annotated"}}, recovery_identity(ocr["engine"], None))
    client = MemoryR2()
    return RecoveryStore(CorpusStore(client, "test")), client, packet, derivative, original


def test_source_bound_publication_replay_and_failure_preserve_previous_recovery(recovery):
    store, client, packet, derivative, original = recovery
    first = store.publish(packet, derivative, original)
    writes = list(client.writes)
    assert all(k.startswith(PREFIX) for k in writes)
    assert not any('/filings/' in k or k.endswith('/catalog.json') for k in writes)
    assert store.publish(packet, derivative, original) == first
    assert client.writes == writes
    assert store.cached(packet['source'], 1, packet['engine'], original, None) == (packet, derivative)
    failed = store.record_failure(packet['source'], 1, 'OCR interrupted')
    assert failed['pages']['1']['current'] == first['pages']['1']['current']
    assert store.cached(packet['source'], 1, packet['engine'], original, None) is None
    assert store.publish(packet, derivative, original) == first


@pytest.mark.parametrize('change', ['word', 'line', 'page', 'approval', 'engine', 'pixels'])
def test_corrupt_or_misassociated_recovery_never_becomes_indexed(recovery, change):
    store, client, packet, derivative, original = recovery
    packet = copy.deepcopy(packet)
    if change == 'word':
        packet['ocr']['words'][0]['text'] = 'Invented'
    elif change == 'line':
        packet['view']['lines'].pop()
    elif change == 'page':
        packet['page'] = 2
    elif change == 'approval':
        packet['semantically_verified'] = True
    elif change == 'engine':
        packet['engine']['implementation_sha256'] = '0' * 64
    else:
        derivative += b'changed'
    with pytest.raises(ValueError):
        store.publish(packet, derivative, original)
    assert client.writes == []


def test_interruption_before_index_retains_no_dangling_reference(recovery):
    store, client, packet, derivative, original = recovery
    client.fail_key = store.index_key(packet['source'])
    with pytest.raises(RuntimeError, match='interruption'):
        store.publish(packet, derivative, original)
    assert client.fail_key not in client.objects
    artifacts = set(client.objects)
    client.fail_key = None
    store.publish(packet, derivative, original)
    assert set(client.objects) - artifacts == {store.index_key(packet['source'])}


def test_missing_or_changed_retained_bytes_invalidate_reuse(recovery):
    store, client, packet, derivative, original = recovery
    index = store.publish(packet, derivative, original)
    item = index['pages']['1']['current']['artifacts']['page']
    assert json.loads(gzip.decompress(client.objects[item['key']])) == packet
    client.objects[item['key']] += b'changed'
    assert store.cached(packet['source'], 1, packet['engine'], original, None) is None
    del client.objects[item['key']]
    assert store.cached(packet['source'], 1, packet['engine'], original, None) is None
    engine = copy.deepcopy(packet['engine'])
    engine['ocr']['dpi'] = 450
    assert store.cached(packet['source'], 1, engine, original, None) is None


def test_scope_records_do_not_erase_other_selected_pages_or_approve_unselected_pages(recovery):
    store, client, packet, _, _ = recovery
    source = packet['source']
    selection = {'page_count': 12, 'method': 'explicit', 'pages': [3]}
    store.record_selection(source, selection)
    writes = len(client.writes)
    store.record_selection(source, selection)
    assert len(client.writes) == writes
    index = store.record_selection(source, {**selection, 'pages': [5]})
    assert [s['pages'] for s in index['selections']] == [[3], [5]]
    assert index['pages'] == {} and not index['semantically_verified']


def test_comparison_preserves_disagreement_and_never_turns_dash_into_zero():
    ocr = {'words': [{'id': 0, 'text': '0', 'bbox': [10, 10, 20, 20], 'block': 0, 'line': 0},
                     {'id': 1, 'text': '17.137', 'bbox': [30, 10, 60, 20], 'block': 0, 'line': 0}]}
    vector = {'matched_paths': [{'drawing_id': 5, 'text': '-', 'bbox': [10, 13, 20, 17]},
                               {'drawing_id': 8, 'text': '17.237', 'bbox': [30, 10, 60, 20]}]}
    view = recovery_view(ocr, vector)
    assert view['lines'][0]['word_ids'] == [0, 1]
    assert view['lines'][0]['text'] == '0 17.137'
    assert [c['status'] for c in view['vector_comparisons']] == ['disagreement', 'disagreement']
    assert view['vector_comparisons'][0]['vector_text'] == '-'
    assert not any(c['recognition_verified'] for c in view['vector_comparisons'])
