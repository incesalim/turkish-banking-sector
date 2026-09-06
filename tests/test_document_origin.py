import copy
import hashlib
import json

import pytest

from src.audit_reports.document_corpus import Filing
from src.audit_reports.document_corpus_store import CorpusStore, PREFIX
from src.audit_reports.document_origin import observe_origin, publish_origin
from src.audit_reports.document_quality import bank_patterns
from test_document_acquisition import archive_body, pdf_body
from test_document_corpus_store import MemoryR2

FILING = Filing('TEST', '2026Q1', 'consolidated')
PATTERNS = bank_patterns({'TEST': {'name': 'Test Bank'}})
KEY = 'test/' + FILING.filename
URL = 'https://bank.example/report.pdf'


def observe(client, acquired, downloaded, member=None):
    if acquired is not None:
        client.objects[KEY] = acquired
    def fetch(url):
        assert url == URL
        if isinstance(downloaded, Exception):
            raise downloaded
        return downloaded, {'source_url': url, 'resolved_url': url, 'content_type': 'application/pdf'}
    return observe_origin(CorpusStore(client, 'test'), FILING, KEY, URL, PATTERNS,
                          fetch=fetch, reviewed_member=member, checked_at='2026-09-06T20:00:00+00:00')


def test_identical_official_bytes_are_retained_without_rewriting_acquisition():
    client, body = MemoryR2(), pdf_body()
    result, artifacts = observe(client, body, body)
    assert result['status'] == 'matches_acquired_bytes'
    assert result['origin_identity']['status'] == 'supported_by_source_text'
    assert not client.writes
    stored = publish_origin(CorpusStore(client, 'test'), result, artifacts, PATTERNS)
    assert client.objects[KEY] == body
    assert all(key.startswith(PREFIX) for key in client.writes)
    retained = json.loads(client.objects[stored['review_key']])
    assert retained['acquisition']['sha256'] == retained['origin_pdf']['sha256']
    assert client.objects[retained['transport']['key']] == body
    assert client.objects[retained['origin_pdf']['key']] == body
    assert retained['semantically_verified'] is False
    writes = list(client.writes)
    assert publish_origin(CorpusStore(client, 'test'), result, artifacts, PATTERNS) == stored
    assert client.writes == writes


def test_a_different_revision_is_named_and_both_originals_survive():
    client, old, new = MemoryR2(), pdf_body(), pdf_body('Revised Test Bank 31 March 2026 Consolidated Financial Statements')
    result, artifacts = observe(client, old, new)
    assert result['status'] == 'different_pdf_revision'
    published = publish_origin(CorpusStore(client, 'test'), result, artifacts, PATTERNS)
    assert client.objects[KEY] == old and client.objects[published['origin_pdf']['key']] == new
    assert result['origin_identity']['status'] == 'supported_by_source_text'
    assert result['semantically_verified'] is False


def test_byte_agreement_does_not_hide_wrong_period_in_both_copies():
    client = MemoryR2()
    wrong = pdf_body('Test Bank 31 March 2025 Consolidated Financial Statements')
    result, _ = observe(client, wrong, wrong)
    assert result['status'] == 'matches_acquired_bytes'
    assert result['origin_identity']['status'] == 'source_text_conflict'
    assert result['semantically_verified'] is False


def test_only_explicit_serialized_wrapper_normalization_can_count_as_same_pdf():
    client, body = MemoryR2(), pdf_body()
    result, _ = observe(client, b'\xac\xed\x00\x05' + b'x' * 23 + body, body)
    assert result['status'] == 'same_pdf_after_acquisition_wrapper'
    assert result['acquisition_wrapper']['prefix_bytes'] == 27
    result, _ = observe(client, body + b'\n%metadata changed', body)
    assert result['status'] == 'different_pdf_revision'


def test_zip_transport_and_related_pdf_members_are_distinct_from_selected_report():
    client, body, declaration = MemoryR2(), pdf_body(), pdf_body('Signed responsibility declaration')
    archive = archive_body([('financial.pdf', body), ('declaration.pdf', declaration)])
    member = {'member': 'financial.pdf', 'sha256': hashlib.sha256(body).hexdigest()}
    result, artifacts = observe(client, body, archive, member)
    assert result['status'] == 'matches_acquired_bytes'
    assert result['transport']['sha256'] != result['origin_pdf']['sha256']
    assert artifacts == {'transport': archive, 'origin_pdf': body}
    assert result['related_pdf_content_capture'] == 'pending'
    assert result['selection']['unselected_pdf_members'][0]['name'] == 'declaration.pdf'
    publish_origin(CorpusStore(client, 'test'), result, artifacts, PATTERNS)


@pytest.mark.parametrize('downloaded,status', [(RuntimeError('HTTP 404'), 'origin_unavailable'),
                                              (b'<html>Not a report</html>', 'origin_needs_review')])
def test_unavailable_or_non_pdf_sources_are_explicit_and_preserve_acquired_bytes(downloaded, status):
    client, body = MemoryR2(), pdf_body()
    result, artifacts = observe(client, body, downloaded)
    assert result['status'] == status and result['error']
    publish_origin(CorpusStore(client, 'test'), result, artifacts, PATTERNS)
    assert client.objects[KEY] == body


def test_a_missing_acquisition_is_not_created_by_an_origin_review():
    client = MemoryR2()
    result, artifacts = observe(client, None, pdf_body())
    assert result['status'] == 'acquisition_missing'
    publish_origin(CorpusStore(client, 'test'), result, artifacts, PATTERNS)
    assert KEY not in client.objects


@pytest.mark.parametrize('mutation', ['bytes', 'missing', 'status', 'claims', 'engine', 'approve', 'acquisition'])
def test_changed_source_or_invented_comparison_cannot_be_published(mutation):
    client, body = MemoryR2(), pdf_body()
    result, artifacts = observe(client, body, body)
    result = copy.deepcopy(result)
    if mutation == 'bytes':
        artifacts['origin_pdf'] += b'changed'
    elif mutation == 'missing':
        artifacts.pop('origin_pdf')
    elif mutation == 'status':
        result['status'] = 'different_pdf_revision'
    elif mutation == 'claims':
        result['origin_leading_pages'][0]['spans'][0]['text'] = 'Invented wording'
    elif mutation == 'engine':
        result['engine']['pymupdf'] = 'other'
    elif mutation == 'approve':
        result['semantically_verified'] = True
    else:
        client.objects[KEY] += b'changed'
    with pytest.raises(ValueError):
        publish_origin(CorpusStore(client, 'test'), result, artifacts, PATTERNS)
    assert not client.writes


def test_damaged_origin_index_readback_cannot_claim_published_review():
    class CorruptIndexR2(MemoryR2):
        def put_object(self, **kwargs):
            result = super().put_object(**kwargs)
            if kwargs['Key'].endswith('/index.json'):
                index = json.loads(self.objects[kwargs['Key']])
                index['revisions'] = []
                self.objects[kwargs['Key']] = json.dumps(index).encode()
            return result

    client, body = CorruptIndexR2(), pdf_body()
    result, artifacts = observe(client, body, body)
    with pytest.raises(ValueError, match='readback'):
        publish_origin(CorpusStore(client, 'test'), result, artifacts, PATTERNS)
    assert client.objects[KEY] == body
