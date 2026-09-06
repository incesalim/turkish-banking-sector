import copy
import hashlib

import pytest

from src.audit_reports.document_identity_review import contextual_identity_review
from src.audit_reports.document_evidence import _canonical_json
from src.audit_reports.document_quality import bank_patterns


@pytest.fixture
def reviewed():
    filing = {'bank_ticker': 'TEST', 'period': '2026Q1', 'kind': 'consolidated'}
    source = {**filing, 'pdf_sha256': 'a' * 64}
    text = 'Test Bank consolidated financial statements as at 31 March 2026'
    pages = [{'page': 2, 'spans': [{'id': 0, 'text': text, 'bbox': [10, 20, 200, 40]}]}]
    registry = {'schema_version': 'audit-document-identity-reviews-1', 'reviews': [
        {'filing': filing, 'pdf_sha256': source['pdf_sha256'], 'decision': 'supported_in_context',
         'review_method': 'Source visual review', 'reviewed_on': '2026-09-06', 'note': 'A later paragraph discusses the prior year.',
         'witnesses': [{'role': 'filing_introduction', 'page': 2, 'source_span_ids': [0],
                        'text_sha256': hashlib.sha256(text.encode()).hexdigest(), 'source_bbox': [10, 20, 200, 40]}]}]}
    patterns = bank_patterns({'TEST': {'name': 'Test Bank A.Ş.'}})
    return source, pages, registry, patterns


def test_review_applies_only_to_its_exact_pdf_and_retains_automatic_findings(reviewed):
    source, pages, registry, patterns = reviewed
    result = contextual_identity_review(*reviewed)
    assert result['status'] == 'source_bound_review_applies'
    assert result['decision'] == 'supported_in_context' and result['automatic_findings_preserved']
    assert result['semantic_verification'] == 'not_performed'
    source['pdf_sha256'] = 'b' * 64
    assert contextual_identity_review(*reviewed)['status'] == 'source_revision_unreviewed'
    source['bank_ticker'] = 'OTHER'
    assert contextual_identity_review(*reviewed)['status'] == 'not_reviewed'


@pytest.mark.parametrize('change', ['text', 'geometry', 'missing_span', 'duplicate_span', 'page', 'identity', 'decision', 'duplicate_review'])
def test_changed_witnesses_and_unsupported_decisions_cannot_borrow_a_review(reviewed, change):
    source, pages, registry, _patterns = reviewed
    if change == 'text':
        pages[0]['spans'][0]['text'] += ' changed'
    elif change == 'geometry':
        pages[0]['spans'][0]['bbox'][0] += 1
    elif change == 'missing_span':
        pages[0]['spans'] = []
    elif change == 'duplicate_span':
        registry['reviews'][0]['witnesses'][0]['source_span_ids'] = [0, 0]
    elif change == 'page':
        pages[0]['page'] = 3
    elif change == 'identity':
        source['period'] = registry['reviews'][0]['filing']['period'] = '2025Q1'
    elif change == 'decision':
        registry['reviews'][0]['decision'] = 'supported_with_source_contradiction'
    else:
        registry['reviews'].append(copy.deepcopy(registry['reviews'][0]))
    with pytest.raises(ValueError):
        contextual_identity_review(*reviewed)


def test_a_cover_contradiction_is_preserved_and_requires_its_own_source_witness(reviewed):
    source, pages, registry, patterns = reviewed
    text = 'Test Bank consolidated financial statements 31 March 2026; translation of unconsolidated statements'
    pages.append({'page': 1, 'spans': [{'id': 0, 'text': text, 'bbox': [10, 10, 200, 30]}]})
    review = registry['reviews'][0]
    review['decision'] = 'supported_with_source_contradiction'
    review['witnesses'].append({'role': 'contradictory_cover', 'page': 1, 'source_span_ids': [0],
                                'text_sha256': hashlib.sha256(text.encode()).hexdigest(), 'source_bbox': [10, 10, 200, 30]})
    result = contextual_identity_review(*reviewed)
    assert result['decision'] == 'supported_with_source_contradiction'
    assert 'basis_has_competing_source_claims' in result['witnesses'][1]['claim']['issues']


@pytest.fixture
def rendered_review(reviewed):
    source, _pages, registry, patterns = reviewed
    page = {'page': 1, 'width': 595, 'height': 842, 'coordinate_space': 'display',
            'spans': [], 'images': [{'id': 0, 'digest': 'source-image'}]}
    text = 'Test Bank consolidated financial statements as at 31 March 2026'
    registry['reviews'][0]['witnesses'] = [
        {'role': 'filing_introduction', 'page': 1, 'evidence_kind': 'rendered_source_region',
         'source_page_sha256': hashlib.sha256(_canonical_json(page).encode()).hexdigest(),
         'source_bbox': [10, 20, 400, 150], 'transcription': text,
         'text_sha256': hashlib.sha256(text.encode()).hexdigest()}]
    return source, [page], registry, patterns


def test_rendered_review_never_invents_native_spans_or_automatic_reading(rendered_review):
    result = contextual_identity_review(*rendered_review)
    witness = result['witnesses'][0]
    assert result['automatic_findings_preserved'] and result['semantic_verification'] == 'not_performed'
    assert witness['claim']['status'] == 'supported_by_reviewed_transcription'
    assert witness['claim']['automatic_reading_verified'] is False
    assert 'source_span_ids' not in str(witness) and 'observed_text' not in witness
    assert witness['claim']['observations'][0]['banks'][0]['bank_ticker'] == 'TEST'


@pytest.mark.parametrize('change', ['image', 'page_geometry', 'page_hash', 'transcription',
                                  'wrong_identity', 'outside', 'nan', 'reversed', 'invented_span',
                                  'unknown_kind', 'cover_role'])
def test_rendered_review_rejects_changed_or_unsupported_evidence(rendered_review, change):
    _source, pages, registry, _patterns = rendered_review
    witness = registry['reviews'][0]['witnesses'][0]
    if change == 'image':
        pages[0]['images'][0]['digest'] = 'different-image'
    elif change == 'page_geometry':
        pages[0]['width'] += 1
    elif change == 'page_hash':
        witness['source_page_sha256'] = 'b' * 64
    elif change == 'transcription':
        witness['transcription'] += ' changed'
    elif change == 'wrong_identity':
        witness['transcription'] = witness['transcription'].replace('2026', '2025')
        witness['text_sha256'] = hashlib.sha256(witness['transcription'].encode()).hexdigest()
    elif change == 'outside':
        witness['source_bbox'][0] = -1
    elif change == 'nan':
        witness['source_bbox'][0] = float('nan')
    elif change == 'reversed':
        witness['source_bbox'][2] = 5
    elif change == 'invented_span':
        witness['source_span_ids'] = [0]
    elif change == 'unknown_kind':
        witness['evidence_kind'] = 'inferred_from_filename'
    else:
        witness['role'] = 'contradictory_cover'
    with pytest.raises(ValueError):
        contextual_identity_review(*rendered_review)
