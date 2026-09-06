"""Apply source-bound contextual reviews without discarding automatic findings."""
from __future__ import annotations

import hashlib

from .document_corpus import Filing
from .document_quality import source_identity_review


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
