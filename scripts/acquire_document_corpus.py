#!/usr/bin/env python3
"""Actions-only fill of explicitly registered missing PDF sources; no D1 writes.

Only the requested registry scope is eligible. Existing acquisitions are skipped
before downloading. Source selection and failed cover claims remain named.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from collections import Counter

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.audit_reports.document_acquisition import acquire_filing  # noqa: E402
from src.audit_reports.document_corpus import registered_sources  # noqa: E402
from src.audit_reports.document_corpus_store import CorpusStore  # noqa: E402
from src.audit_reports.document_quality import bank_patterns  # noqa: E402
from build_document_corpus import _write_json, filing_shard  # noqa: E402


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
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        parser.error('Source acquisition must run in Actions')
    if args.limit < 0 or args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        parser.error('Invalid limit or filing group')
    config = json.loads(args.config.read_text(encoding='utf-8'))
    banks = {b.strip().upper() for b in args.bank.split(',')} if args.bank else None
    if banks is not None and banks - set(config['banks']):
        parser.error('Unknown registered bank')
    registered = registered_sources(config)
    selected = [f for f in sorted(registered) if (not banks or f.bank_ticker in banks)
                and (not args.period or f.period == args.period) and (not args.kind or f.kind == args.kind)]
    if args.limit:
        selected = selected[:args.limit]
    if not selected:
        parser.error('No registered filing matches the requested scope')
    assigned = [f for f in selected if filing_shard(f.as_dict(), args.shard_count) == args.shard_index]
    from src.audit_reports import r2_storage
    store = CorpusStore(r2_storage.get_client(), r2_storage._bucket())
    patterns = bank_patterns(config['banks'])
    report = {'schema_version': 'document-acquisition-run-1', 'selected_filings': len(selected),
              'assigned_filings': len(assigned), 'shard_count': args.shard_count, 'shard_index': args.shard_index,
              'filings': [], 'semantic_verification': 'not_performed'}
    for filing in assigned:
        try:
            urls = registered[filing]
            if len(urls) != 1:
                raise ValueError('Source acquisition requires one unambiguous registered URL')
            result = acquire_filing(store, filing, urls[0], patterns)
        except Exception as error:
            result = {'filing': filing.as_dict(), 'status': 'failed', 'error': str(error)}
        report['filings'].append(result)
        report['summary'] = dict(Counter(r['status'] for r in report['filings']))
        _write_json(args.output_dir / 'acquisition-results.json', report)
        print(f"{filing.filename}: {result['status']}", flush=True)
    return int(any(r['status'] in ('failed', 'needs_review') for r in report['filings']))


if __name__ == '__main__':
    raise SystemExit(main())
