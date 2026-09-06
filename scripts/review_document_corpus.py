#!/usr/bin/env python3
"""Read-only corpus review: source bytes, cover claims, text signals and recovery gaps.

Uses preserved evidence; never re-extracts a PDF or changes a corpus/serving row.
Full runs belong in Actions. Every assigned filing receives a named outcome.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.audit_reports.document_corpus import Filing, registered_sources, reconcile_inventory  # noqa: E402
from src.audit_reports.document_corpus_store import CorpusStore, PREFIX  # noqa: E402
from src.audit_reports.document_quality import (  # noqa: E402
    bank_patterns, source_identity_review, text_legibility_signals,
)
from src.audit_reports.document_recovery import RecoveryStore  # noqa: E402
from build_document_corpus import _write_json, filing_shard  # noqa: E402


def _verify_pdf_bytes(store, key, source):
    response = store.client.get_object(Bucket=store.bucket, Key=key)
    stream, hashed, count = response['Body'], hashlib.sha256(), 0
    try:
        while chunk := stream.read(1024 * 1024):
            hashed.update(chunk)
            count += len(chunk)
    finally:
        stream.close()
    if (count != response['ContentLength'] or count != source['byte_count']
            or hashed.hexdigest() != source['pdf_sha256']):
        raise ValueError(f'Source PDF bytes changed or differ from the captured revision: {key}')


def _artifact(store, key, expected_sha):
    body, _ = store._read(key)
    if body is None or hashlib.sha256(body).hexdigest() != expected_sha:
        raise ValueError('Retained artifact is missing or fails its byte hash')
    return gzip.GzipFile(fileobj=io.BytesIO(body))


def review_filing(store, filing: Filing, acquisition_key: str, patterns: dict) -> dict:
    index = store.read_index(filing)
    if not index or not index.get('current'):
        return {'filing': filing.as_dict(), 'status': 'capture_missing'}
    current = index['current']
    source = current['source']
    if ({k: source[k] for k in ('bank_ticker', 'period', 'kind')} != filing.as_dict()
            or source['object_key'] != acquisition_key):
        raise ValueError('Capture source differs from acquisition binding')
    base = f"{PREFIX}sources/{source['pdf_sha256']}/"
    if (current['original_key'] != base + 'original.pdf'
            or current['evidence_key'] != base + current['artifact_sha256'] + '.jsonl.gz'):
        raise ValueError('Capture artifact key differs from its source/content identity')
    # Check both copies independently. A renamed/replaced acquisition object must
    # not borrow the identity of an older immutable archived PDF.
    _verify_pdf_bytes(store, acquisition_key, source)
    _verify_pdf_bytes(store, current['original_key'], source)
    leading, legibility, counts = [], [], Counter()
    full_hash, pages_hash = hashlib.sha256(), hashlib.sha256()
    with _artifact(store, current['evidence_key'], current['evidence_bytes_sha256']) as stream:
        raw = next(stream)
        full_hash.update(raw)
        manifest = json.loads(raw)
        if (manifest['type'] != 'source_manifest' or manifest['source'] != source
                or manifest['engine'] != current['engine'] or manifest['page_count'] != current['page_count']):
            raise ValueError('Source manifest differs from its filing index')
        for number, raw in enumerate(stream, start=1):
            if not raw.endswith(b'\n'):
                raise ValueError('Source page serialization is truncated')
            full_hash.update(raw)
            payload = raw[:-1]
            if number > 1:
                pages_hash.update(b'\n')
            pages_hash.update(payload)
            if number > manifest['page_count'] or hashlib.sha256(payload).hexdigest() != manifest['page_sha256'][number - 1]:
                raise ValueError('Source page differs from its retained manifest')
            page = json.loads(payload)
            if page['type'] != 'source_page' or page['page'] != number:
                raise ValueError('Source page inventory is not contiguous')
            counts.update(pages=1, native_words=len(page['words']), source_spans=len(page['spans']),
                          text_characters=page['text_character_count'], image_regions=len(page['images']),
                          drawing_regions=len(page['drawings']),
                          actualtext_pages=int(page.get('actualtext_changes_word_view', False)))
            if number <= 3:
                leading.append(page)
            signals = text_legibility_signals(page)
            if signals['needs_text_review']:
                legibility.append(signals)
    if (counts['pages'] != manifest['page_count'] or counts['text_characters'] != manifest['text_characters']
            or counts['image_regions'] != manifest['image_regions']
            or full_hash.hexdigest() != current['artifact_sha256'] or pages_hash.hexdigest() != manifest['pages_sha256']):
        raise ValueError('Source artifact inventory or content hash differs')
    identity = source_identity_review(filing, leading, patterns)
    structure = current.get('structure_current')
    issue_counts, issue_pages, examples = Counter(), Counter(), {}
    if structure:
        if structure['key'] != base + structure['artifact_sha256'] + '.structure.jsonl.gz':
            raise ValueError('Structure artifact key differs from its source/content identity')
        with _artifact(store, structure['key'], structure['bytes_sha256']) as stream:
            header = json.loads(next(stream))
            if (header['type'] != 'structure_manifest' or header['source'] != source
                    or header['engine'] != structure['engine']
                    or header['evidence_artifact_sha256'] != current['artifact_sha256']
                    or header['page_count'] != counts['pages']):
                raise ValueError('Structure manifest differs from retained source evidence')
            seen = 0
            for number, raw in enumerate(stream, start=1):
                if (not raw.endswith(b'\n') or number > header['page_count']
                        or hashlib.sha256(raw[:-1]).hexdigest() != header['page_sha256'][number - 1]):
                    raise ValueError('Structured page differs from its retained manifest')
                page = json.loads(raw)
                if page['page'] != number or page['type'] != 'structured_page':
                    raise ValueError('Structured page inventory is not contiguous')
                seen += 1
                counts.update(table_candidates=len(page['tables']), text_blocks=len(page['text_blocks']),
                              narrative_candidates=len(page.get('narrative_elements', [])))
                kinds = Counter(i['kind'] for i in page['issues'])
                issue_counts.update(kinds)
                issue_pages.update(kinds.keys())
                for issue in page['issues']:
                    sample = examples.setdefault(issue['kind'], [])
                    if len(sample) < 3:
                        sample.append({'page': number, 'issue': issue})
            if seen != counts['pages']:
                raise ValueError('Structured pages are missing')
    recovery_source = {**source, 'source_url': None, 'object_key': None}
    recovery = RecoveryStore(store).read_index(recovery_source)
    selections = (recovery or {}).get('selections', [])
    selected = {n for s in selections for n in s['pages']}
    recovered, failed = set(), []
    for number, page in (recovery or {}).get('pages', {}).items():
        if page.get('last_attempt', {}).get('status') == 'failed':
            failed.append({'page': int(number), 'error': page['last_attempt']['error']})
        elif page.get('current'):
            recovered.add(int(number))
    return {'filing': filing.as_dict(), 'source': source, 'status': 'reviewed',
            'source_pdf_copies_byte_verified': True, 'source_artifact_byte_verified': True,
            'structure_artifact_byte_verified': bool(structure), 'counts': dict(counts),
            'capture_last_attempt': index.get('last_attempt'),
            'evidence_engine': current['engine'], 'structure_engine': structure['engine'] if structure else None,
            'identity': identity, 'legibility_findings': legibility,
            'structure_issues': {k: {'observations': n, 'pages': issue_pages[k], 'examples': examples[k]}
                                 for k, n in sorted(issue_counts.items())},
            'recovery': {'index_present': recovery is not None,
                         'automatic_selection_recorded': any(s['method'] == 'image_outline_detector' for s in selections),
                         'selected_pages_all_requests': sorted(selected), 'recovered_pages': sorted(recovered),
                         'pending_selected_pages': sorted(selected - recovered), 'failed_pages': failed,
                         'unselected_text_review_pages': [p['page'] for p in legibility if p['page'] not in selected],
                         'selection_completeness_verified': False},
            'semantic_verification': 'not_performed'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=REPO / 'data/banks/audit_report_urls.json')
    parser.add_argument('--output-dir', type=Path, default=REPO / 'data/audit_capture/corpus-v1')
    parser.add_argument('--bank')
    parser.add_argument('--period')
    parser.add_argument('--kind', choices=['consolidated', 'unconsolidated'])
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--shard-count', type=int, default=1)
    parser.add_argument('--shard-index', type=int, default=0)
    args = parser.parse_args(argv)
    if (args.limit < 0 or args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count
            or os.environ.get('GITHUB_ACTIONS') != 'true' and not 1 <= args.limit <= 4):
        parser.error('Local reviews require --limit 1..4; full reviews belong in Actions')
    config = json.loads(args.config.read_text(encoding='utf-8'))
    banks = {b.strip().upper() for b in args.bank.split(',')} if args.bank else None
    if banks is not None and banks - set(config['banks']):
        parser.error('Unknown registered bank')
    from src.audit_reports import r2_storage
    store = CorpusStore(r2_storage.get_client(), r2_storage._bucket())
    inventory = reconcile_inventory(registered_sources(config), r2_storage.list_audit_pdfs())
    _write_json(args.output_dir / 'inventory.json', inventory)
    selected = [r for r in inventory['filings'] if (not banks or r['bank_ticker'] in banks)
                and (not args.period or r['period'] == args.period) and (not args.kind or r['kind'] == args.kind)]
    if args.limit:
        selected = selected[:args.limit]
    if not selected:
        parser.error('No filing matches the requested scope')
    assigned = [r for r in selected if filing_shard(r, args.shard_count) == args.shard_index]
    report = {'schema_version': 'document-quality-review-1', 'selected_filings': len(selected),
              'assigned_filings': len(assigned), 'shard_count': args.shard_count, 'shard_index': args.shard_index,
              'review_implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'quality_implementation_sha256': hashlib.sha256((REPO / 'src/audit_reports/document_quality.py').read_bytes()).hexdigest(),
              'filings': [], 'semantic_verification': 'not_performed'}
    patterns = bank_patterns(config['banks'])
    for row in assigned:
        filing = Filing(row['bank_ticker'], row['period'], row['kind'])
        try:
            if len(row['object_keys']) != 1:
                raise ValueError('One unambiguous acquired source is required')
            result = review_filing(store, filing, row['object_keys'][0], patterns)
        except Exception as error:
            result = {'filing': filing.as_dict(), 'status': 'failed', 'error': str(error)}
        report['filings'].append(result)
        report['summary'] = dict(Counter(r['status'] for r in report['filings']))
        report['identity_summary'] = dict(Counter(r['identity']['status'] for r in report['filings'] if 'identity' in r))
        _write_json(args.output_dir / 'quality-results.json', report)
        print(f"{filing.filename}: {result['status']}; identity={(result.get('identity') or {}).get('status', 'unavailable')}", flush=True)
    return int(any(r['status'] != 'reviewed' or r['identity']['status'] == 'source_text_conflict' for r in report['filings']))


if __name__ == '__main__':
    raise SystemExit(main())
