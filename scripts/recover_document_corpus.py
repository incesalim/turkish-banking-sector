#!/usr/bin/env python3
"""Recover image/outline text into a separate, unverified corpus page store.

Full runs belong in Actions. Native capture and analytical lanes are untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import fitz

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.audit_reports.document_corpus import Filing, registered_sources, reconcile_inventory  # noqa: E402
from src.audit_reports.document_corpus_store import CorpusStore  # noqa: E402
from src.audit_reports.document_recovery import (  # noqa: E402
    RecoveryStore, make_packet, recovery_identity, verify_packet,
)
from build_document_corpus import _write_json, _write_bytes, filing_shard  # noqa: E402


def select_pages(original: Path, explicit: list[int]) -> dict:
    from src.audit_reports.document_capture import _probe_text_layer
    observations = []
    with fitz.open(original) as pdf:
        if any(n > len(pdf) for n in explicit):
            raise ValueError("A requested recovery page is outside the PDF")
        for number in explicit or range(1, len(pdf) + 1):
            page = pdf[number - 1]
            words = page.get_text("words", clip=fitz.INFINITE_RECT())
            layer = _probe_text_layer(page, len(words))
            observations.append({"page": number, "native_words": len(words), "text_layer": layer,
                                 "selected": bool(explicit) or layer != "text"})
        return {"page_count": len(pdf), "method": "explicit" if explicit else "image_outline_detector",
                "detector_sha256": hashlib.sha256((REPO / "src/audit_reports/document_capture.py").read_bytes()).hexdigest(),
                "pages": [p['page'] for p in observations if p['selected']],
                "observations": observations, "selection_completeness_verified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-r2', action='store_true')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--config', type=Path, default=REPO / 'data/banks/audit_report_urls.json')
    parser.add_argument('--source-dir', type=Path, default=REPO / 'data/audit_pdfs')
    parser.add_argument('--output-dir', type=Path, default=REPO / 'data/audit_capture/recovery-v1')
    parser.add_argument('--bank')
    parser.add_argument('--period')
    parser.add_argument('--kind', choices=['consolidated', 'unconsolidated'])
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--pages', default='flagged', help='flagged, or up to four explicit PDF page numbers')
    parser.add_argument('--dpi', type=int, choices=[300, 450, 600], default=300)
    parser.add_argument('--language', choices=['eng', 'tur', 'eng+tur', 'tur+eng'], default='eng+tur')
    parser.add_argument('--shard-count', type=int, default=1)
    parser.add_argument('--shard-index', type=int, default=0)
    args = parser.parse_args(argv)
    if args.limit < 0 or args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        parser.error('Invalid filing limit or group assignment')
    try:
        pages = [] if args.pages == 'flagged' else [int(n.strip()) for n in args.pages.split(',')]
        if args.pages != 'flagged' and (not 1 <= len(pages) <= 4 or min(pages) < 1 or len(set(pages)) != len(pages)):
            raise ValueError()
    except ValueError:
        parser.error('--pages must be flagged or one to four distinct positive PDF pages')
    if os.environ.get('GITHUB_ACTIONS') != 'true' and (not pages or not 1 <= args.limit <= 4):
        parser.error('Local recovery requires explicit pages and --limit 1..4; full recovery belongs in Actions')
    if args.publish and not (args.from_r2 and os.environ.get('GITHUB_ACTIONS') == 'true'):
        parser.error('Publication requires --from-r2 in Actions')
    config = json.loads(args.config.read_text(encoding='utf-8'))
    banks = {b.strip().upper() for b in args.bank.split(',')} if args.bank else None
    if banks is not None and (not banks or banks - set(config['banks'])):
        parser.error('--bank must name registered banks')
    if args.period:
        try:
            Filing(next(iter(config['banks'])), args.period, 'consolidated')
        except ValueError as error:
            parser.error(str(error))
    client = bucket = store = None
    if args.from_r2:
        from src.audit_reports import r2_storage
        client, bucket = r2_storage.get_client(), r2_storage._bucket()
        acquired = r2_storage.list_audit_pdfs()
        store = RecoveryStore(CorpusStore(client, bucket))
    else:
        acquired = []
    inventory = reconcile_inventory(registered_sources(config), acquired, args.source_dir.glob('*.pdf'))
    inventory['acquisition_checked'] = args.from_r2
    if not args.from_r2:
        inventory['registered_missing'] = None
        for row in inventory['filings']:
            row['acquisition_status'] = 'not_checked'
    _write_json(args.output_dir / 'inventory.json', inventory)
    selected = [r for r in inventory['filings'] if (not banks or r['bank_ticker'] in banks)
                and (not args.period or r['period'] == args.period) and (not args.kind or r['kind'] == args.kind)]
    if args.limit:
        selected = selected[:args.limit]
    if not selected:
        parser.error('No filing matches the requested scope')
    assigned = [r for r in selected if filing_shard(r, args.shard_count) == args.shard_index]
    report = {'schema_version': 'corpus-recovery-run-1', 'selected_filings': len(selected),
              'assigned_filings': len(assigned), 'shard_count': args.shard_count, 'shard_index': args.shard_index,
              'filings': [], 'semantically_verified': False}
    _write_json(args.output_dir / 'recovery-results.json', report)
    from src.audit_reports import document_ocr as ocr, document_vector as vector
    from src.audit_reports.document_corpus import source_identity
    atlas = reference = ocr_engine = None
    failures = 0
    for row in assigned:
        filing = Filing(row['bank_ticker'], row['period'], row['kind'])
        outcome = {'filing': filing.as_dict(), 'status': 'running', 'pages': []}
        report['filings'].append(outcome)
        original = args.output_dir / 'inputs' / filing.filename if args.from_r2 else args.source_dir / filing.filename
        source = None
        try:
            if client:
                if len(row['object_keys']) != 1:
                    raise ValueError('Recovery requires one unambiguous acquired PDF object')
                response = client.get_object(Bucket=bucket, Key=row['object_keys'][0])
                _write_bytes(original, response['Body'].read())
            # Identity intentionally contains no mutable URL metadata; source bytes
            # and filing identity bind both observations and all recovery revisions.
            source = source_identity(original, filing)
            selection = select_pages(original, pages)
            outcome['source'] = source
            outcome['selection'] = selection
            if args.publish:
                store.record_selection(source, selection)
            for item in selection['observations']:
                if not item['selected']:
                    continue
                number = item['page']
                page_outcome = {'page': number, 'status': 'running'}
                outcome['pages'].append(page_outcome)
                try:
                    if ocr_engine is None:
                        lock = ocr.ensure_models(args.output_dir / 'models')
                        ocr_engine = ocr._engine(lock, args.dpi, args.language)
                    use_atlas = None
                    if item['text_layer'] == 'vector':
                        if atlas is None:
                            anchors = json.loads(vector.ANCHORS.read_text(encoding='utf-8'))
                            reference = args.output_dir / 'reference' / 'original.pdf'
                            if source['pdf_sha256'] == anchors['pdf_sha256']:
                                _write_bytes(reference, original.read_bytes())
                            elif client:
                                response = client.get_object(Bucket=bucket, Key=anchors['object_key'])
                                _write_bytes(reference, response['Body'].read())
                            else:
                                raise ValueError('Local vector recovery requires the reference filing itself')
                            atlas = vector.build_atlas(reference, anchors)
                        use_atlas = atlas
                    engine = recovery_identity(ocr_engine, use_atlas)
                    cached = store.cached(source, number, engine, original, use_atlas) if store else None
                    if cached:
                        prior, derivative = cached
                        observed, outlines = prior['ocr'], prior['vector']
                    else:
                        observed, derivative = ocr.capture_ocr_page(original, filing, number,
                            args.output_dir / 'models', dpi=args.dpi, language=args.language)
                        outlines = vector.capture_vector_page(original, filing, number, use_atlas) if use_atlas else None
                    benchmarks = {'ocr': ocr.check_ocr_annotations(observed, REPO / 'tests/fixtures/document_ocr_annotations')}
                    if outlines:
                        benchmarks['vector'] = vector.check_vector_annotations(outlines, REPO / 'tests/fixtures/document_vector_annotations')
                    packet = make_packet(observed, outlines, benchmarks, engine)
                    verify_packet(packet, derivative, original, use_atlas)
                    output = args.output_dir / 'sources' / source['pdf_sha256']
                    _write_json(output / f'p{number}.recovery.json', packet)
                    _write_bytes(output / f'p{number}.ocr.pdf', derivative)
                    if use_atlas:
                        _write_json(output / 'atlas.json', use_atlas)
                    if args.publish:
                        store.publish(packet, derivative, original, atlas=use_atlas, reference=reference if use_atlas else None)
                    page_outcome.update(status='recovery_candidates', reused=bool(cached),
                                        ocr_words=len(observed['words']), benchmarks=benchmarks)
                    if any(b['status'] == 'failed' for b in benchmarks.values()):
                        raise ValueError('Source annotation failed; recovery retained for review')
                    if args.publish:
                        (output / f'p{number}.recovery.json').unlink()
                        (output / f'p{number}.ocr.pdf').unlink()
                except Exception as error:
                    failures += 1
                    page_outcome.update(status='failed', error=str(error))
                    if args.publish:
                        store.record_failure(source, number, str(error))
                _write_json(args.output_dir / 'recovery-results.json', report)
            outcome['status'] = ('failed' if any(p['status'] == 'failed' for p in outcome['pages']) else
                                 'recovery_candidates' if outcome['pages'] else 'no_pages_flagged')
        except Exception as error:
            failures += 1
            outcome.update(status='failed', error=str(error))
        _write_json(args.output_dir / 'recovery-results.json', report)
        print(f"{filing.filename}: {outcome['status']}; {len(outcome['pages'])} selected pages", flush=True)
        if args.publish and outcome['status'] != 'failed' and original.is_file():
            # Only the explicitly created input for this filing; no recursive deletion.
            original.unlink()
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
