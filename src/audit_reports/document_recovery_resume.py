"""Version receipts for recovery, issued only after source/artifact byte readback.

The shortcut avoids downloading and classifying unchanged PDFs. It does not
approve recognition, selection completeness or table meaning. A changed source,
implementation, annotation, recovery index or artifact invalidates the receipt.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .document_corpus import Filing, source_identity
from .document_corpus_resume import metadata
from .document_corpus_store import PREFIX, _error_code, _json
from .document_recovery import digest


def request_identity(repo: Path, ocr_engine: dict, pages: list[int]) -> dict:
    import numpy as np
    paths = [repo / 'scripts/recover_document_corpus.py', *(repo / 'src/audit_reports' / name for name in (
        'document_corpus.py', 'document_corpus_resume.py', 'document_corpus_store.py',
        'document_ocr.py', 'document_ocr_models.json', 'document_vector.py',
        'document_vector_anchors.json', 'document_recovery.py',
        'document_recovery_tables.py', 'document_recovery_unruled.py', 'document_recovery_text.py',
        'document_recovery_resume.py'))]
    paths.append(repo / 'src/audit_reports/document_quality.py')
    return {'ocr_engine': ocr_engine, 'numpy': np.__version__, 'pages': sorted(pages),
            'implementation': {p.relative_to(repo).as_posix(): digest(p.read_bytes()) for p in paths}}


def annotation_identity(repo: Path, filing: Filing) -> str:
    result = hashlib.sha256()
    for name in ('document_ocr_annotations', 'document_vector_annotations', 'document_recovery_text_annotations'):
        directory = repo / 'tests/fixtures' / name
        if not directory.is_dir():
            raise ValueError('Recovery annotation directory is missing')
        for path in sorted(directory.glob('*.json')):
            body = path.read_bytes()
            if json.loads(body)['filing'] == filing.as_dict():
                result.update(name.encode())
                result.update(path.name.encode())
                result.update(body)
    return result.hexdigest()


def receipt_key(filing: Filing, request: dict) -> str:
    # Explicit probes and automatic selections never stand in for one another.
    scope = digest(_json(request['pages']))
    return f'{PREFIX}recovery-receipts/{filing.bank_ticker}/{filing.period}/{filing.kind}/{scope}.json'


def _head(store, token: dict) -> bool:
    try:
        response = store.client.head_object(Bucket=store.bucket, Key=token['key'])
    except Exception as error:
        if _error_code(error) in ('404', 'NoSuchKey'):
            return False
        raise
    return metadata(token['key'], response) == token


def _read_verified(store, key: str, sha: str, size: int | None = None) -> dict:
    response = store.client.get_object(Bucket=store.bucket, Key=key)
    stream = response['Body']
    hashed, count = hashlib.sha256(), 0
    try:
        while chunk := stream.read(1024 * 1024):
            hashed.update(chunk)
            count += len(chunk)
    finally:
        stream.close()
    if (hashed.hexdigest() != sha or count != response['ContentLength']
            or size is not None and count != size):
        raise ValueError('Recovery receipt artifact failed byte readback')
    return metadata(key, response)


def record_receipt(recovery, filing: Filing, original: Path, acquisition: dict,
                   selection: dict, request: dict, annotation_hash: str) -> dict:
    store = recovery.store
    source = source_identity(original, filing)
    if not _head(store, acquisition):
        raise ValueError('Acquired source changed during recovery')
    index_key = recovery.index_key(source)
    raw, _ = store._read(index_key)
    index = json.loads(raw) if raw else None
    if not index or index['source'] != source or selection not in index['selections']:
        raise ValueError('Recovery selection has not been recorded for this source')
    allowed = {'explicit'} if request['pages'] else {'image_outline_detector', 'source_content_detector'}
    if selection['method'] not in allowed:
        raise ValueError('Recovery selection differs from requested scope')
    if request['pages'] and sorted(selection['pages']) != request['pages']:
        raise ValueError('Explicit recovery selection omits requested pages')
    base = f"{PREFIX}sources/{source['pdf_sha256']}/"
    original_key = base + 'original.pdf'
    store._immutable(original_key, original.read_bytes(), 'application/pdf')
    required = {original_key: (source['pdf_sha256'], source['byte_count'])}
    summaries = []
    for page in selection['pages']:
        row = index['pages'].get(str(page))
        current = (row or {}).get('current')
        if (not current or row.get('last_attempt', {}).get('status') == 'failed'
                or any(b['status'] == 'failed' for b in current['benchmarks'].values())):
            raise ValueError('Recovery receipt requires every selected page to succeed')
        if current['page'] != page or current['engine']['ocr'] != request['ocr_engine']:
            raise ValueError('Recovery page differs from requested page or OCR engine')
        for field, filename in [('implementation_sha256', 'document_recovery.py'),
                                ('table_implementation_sha256', 'document_recovery_tables.py')]:
            if current['engine'].get(field) != request['implementation'][f'src/audit_reports/{filename}']:
                raise ValueError('Recovery page derived implementation changed')
        if current['engine'].get('numpy') != request['numpy']:
            raise ValueError('Recovery page array runtime changed')
        if (current['engine'].get('atlas_sha256') is not None
                and current['engine'].get('vector_implementation_sha256') !=
                request['implementation']['src/audit_reports/document_vector.py']):
            raise ValueError('Recovery page outline implementation changed')
        for name, artifact in current['artifacts'].items():
            suffix = {'page': 'recovery.json.gz', 'ocr_pdf': 'ocr.pdf', 'atlas': 'atlas.json.gz'}.get(name)
            expected = (f"{PREFIX}sources/{artifact['sha256']}/original.pdf" if name == 'reference_pdf' else
                        f"{base}recovery/{artifact['sha256']}.{suffix}" if suffix else None)
            if artifact['key'] != expected:
                raise ValueError('Recovery receipt artifact has a foreign source or content key')
            required[artifact['key']] = (artifact['sha256'], artifact['bytes'])
        if not {'page', 'ocr_pdf'}.issubset(current['artifacts']):
            raise ValueError('Recovery receipt lacks required page artifacts')
        summaries.append({'page': page, 'status': 'recovery_candidates',
                          'ocr_words': current['ocr_words'], 'benchmarks': current['benchmarks']})
    tokens = [_read_verified(store, key, sha, size) for key, (sha, size) in sorted(required.items())]
    # Include the mutable recovery index: later failures or a revised page must
    # invalidate even a previously byte-verified receipt for the same source.
    tokens.append(_read_verified(store, index_key, digest(raw), len(raw)))
    if not _head(store, acquisition) or not all(_head(store, t) for t in tokens):
        raise ValueError('Recovery artifacts changed before receipt publication')
    receipt = {'schema_version': 'corpus-recovery-receipt-1', 'filing': filing.as_dict(),
               'source': source, 'acquisition': acquisition, 'request': request,
               'annotation_sha256': annotation_hash, 'artifacts': tokens,
               'index_sha256': digest(raw),
               'selection': selection, 'pages': summaries,
               'status': 'recovery_candidates' if summaries else 'no_pages_flagged',
               'semantically_verified': False}
    key, body = receipt_key(filing, request), _json(receipt)
    for _ in range(8):
        prior, etag = store._read(key)
        if prior == body:
            return receipt
        try:
            store.client.put_object(Bucket=store.bucket, Key=key, Body=body, ContentType='application/json',
                                    **({'IfMatch': etag} if etag else {'IfNoneMatch': '*'}))
            return receipt
        except Exception as error:
            if _error_code(error) not in ('412', 'PreconditionFailed'):
                raise
    raise RuntimeError('Recovery receipt changed concurrently; retry this filing')


def unchanged_receipt(recovery, filing: Filing, acquisition_key: str,
                      request: dict, annotation_hash: str) -> dict | None:
    store = recovery.store
    raw, _ = store._read(receipt_key(filing, request))
    if raw is None:
        return None
    receipt = json.loads(raw)
    if (receipt.get('schema_version') != 'corpus-recovery-receipt-1'
            or receipt.get('filing') != filing.as_dict() or receipt.get('request') != request
            or receipt.get('annotation_sha256') != annotation_hash
            or receipt.get('acquisition', {}).get('key') != acquisition_key
            or receipt.get('semantically_verified') is not False):
        return None
    source = receipt['source']
    if {k: source[k] for k in ('bank_ticker', 'period', 'kind')} != filing.as_dict():
        raise ValueError('Recovery receipt source filing mismatch')
    tokens = receipt['artifacts']
    keys = {t['key'] for t in tokens}
    if (recovery.index_key(source) not in keys
            or f"{PREFIX}sources/{source['pdf_sha256']}/original.pdf" not in keys):
        return None
    if any(not k.startswith(PREFIX) for k in keys):
        raise ValueError('Recovery receipt refers outside the corpus')
    # Derive the required set from the independently retained index. A dropped
    # token in a damaged receipt cannot make the corresponding artifact optional.
    index_raw, _ = store._read(recovery.index_key(source))
    if index_raw is None or digest(index_raw) != receipt.get('index_sha256'):
        return None
    index = json.loads(index_raw)
    if index.get('source') != source or receipt['selection'] not in index.get('selections', []):
        return None
    required = {recovery.index_key(source), f"{PREFIX}sources/{source['pdf_sha256']}/original.pdf"}
    for page in receipt['selection']['pages']:
        row = index['pages'].get(str(page))
        current = (row or {}).get('current')
        if not current or row.get('last_attempt', {}).get('status') == 'failed':
            return None
        required.update(a['key'] for a in current['artifacts'].values())
    if keys != required or len(tokens) != len(keys):
        return None
    if not all(_head(store, t) for t in [receipt['acquisition'], *tokens]):
        return None
    return receipt
