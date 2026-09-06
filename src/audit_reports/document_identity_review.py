"""Apply source-bound contextual reviews without discarding automatic findings."""
from __future__ import annotations

import hashlib
import math

from .document_corpus import Filing
from .document_evidence import _canonical_json
from .document_quality import source_identity_review


def _rendered_witness(filing, page, witness, patterns):
    """Bind a reviewer transcription to a preserved page, without inventing spans.

    The hash verifies the source revision, not the correctness of the reviewer's
    reading. This is explicitly separate from native-text identity evidence.
    """
    if 'source_span_ids' in witness:
        raise ValueError('A rendered review cannot claim native source spans')
    page_hash = hashlib.sha256(_canonical_json(page).encode()).hexdigest()
    if witness['source_page_sha256'] != page_hash:
        raise ValueError('Rendered identity review source page changed')
    box = witness['source_bbox']
    if (page.get('coordinate_space') != 'display' or len(box) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
            or not (0 <= box[0] < box[2] <= page['width'] and 0 <= box[1] < box[3] <= page['height'])):
        raise ValueError('Rendered identity review region is outside its source page')
    text = witness['transcription']
    if not text.strip() or hashlib.sha256(text.encode()).hexdigest() != witness['text_sha256']:
        raise ValueError('Rendered identity review transcription changed')
    # Reuse only the claim parser. Its temporary span must never escape as a
    # purported source span: these claims come from the reviewer's transcription.
    parsed = source_identity_review(filing, [{'page': page['page'], 'spans': [
        {'id': 0, 'text': text, 'bbox': box}]}], patterns)
    claim = {'filing': filing.as_dict(), 'page': page['page'],
             'status': parsed['status'].replace('source_text', 'reviewed_transcription'),
             'issues': [i.replace('source_text', 'reviewed_transcription') for i in parsed['issues']],
             'scope': 'reviewed_source_region_transcription', 'automatic_reading_verified': False,
             'semantic_verification': 'not_performed',
             'observations': [{kind: [{k: v for k, v in item.items()
                                      if k not in ('source_span_ids', 'normalized_text_range')}
                                     for item in observed[kind]]
                               for kind in ('banks', 'quarter_end_dates', 'bases')}
                              for observed in parsed['observations']]}
    return {'claim': claim, 'parsed_status': parsed['status'], 'parsed_issues': parsed['issues']}


def contextual_identity_review(source: dict, pages: list[dict], registry: dict, patterns: dict) -> dict:
    if registry.get('schema_version') != 'audit-document-identity-reviews-1':
        raise ValueError('Unsupported document identity review registry')
    filing = Filing(**{k: source[k] for k in ('bank_ticker', 'period', 'kind')})
    same_filing = [r for r in registry['reviews'] if r['filing'] == filing.as_dict()]
    matches = [r for r in same_filing if r['pdf_sha256'] == source['pdf_sha256']]
    if not matches:
        return {'status': 'source_revision_unreviewed' if same_filing else 'not_reviewed', 'semantic_verification': 'not_performed'}
    if len(matches) != 1:
        raise ValueError('Multiple contextual reviews for one source revision')
    review = matches[0]
    if review['decision'] not in ('supported_in_context', 'supported_with_source_contradiction'):
        raise ValueError('Unsupported contextual identity decision')
    evidence = {p['page']: p for p in pages}
    witnesses = []
    for witness in review['witnesses']:
        page = evidence.get(witness['page'])
        if page is None:
            raise ValueError('Identity review source page is unavailable')
        kind = witness.get('evidence_kind', 'native_source_spans')
        if kind == 'rendered_source_region':
            result = _rendered_witness(filing, page, witness, patterns)
            if witness['role'] != 'filing_introduction' or result['parsed_status'] != 'supported_by_source_text':
                raise ValueError('Reviewed source region does not support the filing identity')
            witnesses.append({**witness, 'claim': result['claim']})
            continue
        if kind != 'native_source_spans':
            raise ValueError('Unsupported identity witness evidence kind')
        spans = {s['id']: s for s in page['spans']}
        ids = witness['source_span_ids']
        if not ids or ids != sorted(set(ids)) or any(i not in spans for i in ids):
            raise ValueError('Identity review source span inventory changed')
        selected = [spans[i] for i in ids]
        text = '\n'.join(s['text'] for s in selected)
        box = [min(s['bbox'][0] for s in selected), min(s['bbox'][1] for s in selected),
               max(s['bbox'][2] for s in selected), max(s['bbox'][3] for s in selected)]
        if hashlib.sha256(text.encode()).hexdigest() != witness['text_sha256'] or box != witness['source_bbox']:
            raise ValueError('Identity review source witness changed')
        claim = source_identity_review(filing, [{**page, 'spans': selected}], patterns)
        if witness['role'] == 'filing_introduction':
            if claim['status'] != 'supported_by_source_text':
                raise ValueError('Reviewed introduction does not support the filing identity')
        elif witness['role'] == 'contradictory_cover':
            if 'basis_has_competing_source_claims' not in claim['issues']:
                raise ValueError('Reviewed cover contradiction is no longer present')
        else:
            raise ValueError('Unsupported identity witness role')
        witnesses.append({**witness, 'observed_text': text, 'claim': claim})
    roles = [w['role'] for w in witnesses]
    if roles.count('filing_introduction') != 1 or (review['decision'] == 'supported_with_source_contradiction') != ('contradictory_cover' in roles):
        raise ValueError('Contextual identity review lacks its required witnesses')
    return {'status': 'source_bound_review_applies', 'decision': review['decision'],
            'review_method': review['review_method'], 'reviewed_on': review['reviewed_on'],
            'note': review['note'], 'witnesses': witnesses, 'automatic_findings_preserved': True,
            'semantic_verification': 'not_performed'}
