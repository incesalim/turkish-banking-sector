"""Structured OCR blocks and full source-region transcription comparisons.

Raw OCR is never corrected by a benchmark. A source disagreement is exposed with
the independently transcribed text and region, including accents and punctuation.
"""
from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from pathlib import Path


def _normalized(text):
    return ' '.join(unicodedata.normalize('NFC', text).split())


def text_blocks(ocr: dict, lines: list[dict], tables: list[dict]) -> list[dict]:
    words = {w['id']: w for w in ocr['words']}
    groups = defaultdict(list)
    for line in lines:
        groups[words[line['word_ids'][0]]['block']].append(line)
    result = []
    table_words = {t['id']: {n for row in t['rows'] for cell in row['cells'] for n in cell['ocr_word_ids']} for t in tables}
    for block, members in groups.items():
        ids = [i for line in members for i in line['word_ids']]
        associations = [{'table_id': key, 'ocr_word_ids': [i for i in ids if i in members]}
                        for key, members in table_words.items()]
        result.append({'id': f"p{ocr['page']}:ocr_block{block}", 'method': 'ocr_physical_blocks',
                       'source_block': block, 'line_ids': [line['id'] for line in members],
                       'ocr_word_ids': ids, 'text': '\n'.join(line['text'] for line in members),
                       'bbox': [min(line['bbox'][0] for line in members), min(line['bbox'][1] for line in members),
                                max(line['bbox'][2] for line in members), max(line['bbox'][3] for line in members)],
                       'table_associations': [a for a in associations if a['ocr_word_ids']],
                       'paragraph_boundaries_verified': False, 'reading_order_verified': False,
                       'recognition_verified': False})
    return result


def check_text_regions(ocr: dict, directory: Path) -> dict:
    if not directory.is_dir():
        raise ValueError('Recovery text annotation directory is missing')
    source = ocr['source']
    identity = {k: source[k] for k in ('bank_ticker', 'period', 'kind')}
    checks = []
    for path in sorted(directory.glob('*.json')):
        annotation = json.loads(path.read_text(encoding='utf-8'))
        if annotation['filing'] != identity or annotation['pdf_sha256'] != source['pdf_sha256']:
            continue
        for case in annotation['cases']:
            if case['page'] != ocr['page']:
                continue
            if case['kind'] != 'full_text_region':
                raise ValueError('Unsupported recovery text annotation kind')
            x0, y0, x1, y1 = case['source_bbox']
            selected = [w for w in ocr['words'] if x0 <= (w['bbox'][0] + w['bbox'][2]) / 2 < x1
                        and y0 <= (w['bbox'][1] + w['bbox'][3]) / 2 < y1]
            # Reading order is part of the check. Do not sort into the expected
            # wording or normalize away a missing dot, sign, or negation.
            observed = ' '.join(w['text'] for w in selected)
            matches = _normalized(observed) == _normalized(case['text'])
            checks.append({'id': case['id'], 'source_bbox': case['source_bbox'],
                           'source_transcription': case['text'], 'observed_text': observed,
                           'ocr_word_ids': [w['id'] for w in selected], 'passed': matches,
                           'status': 'matches_source_transcription' if matches else 'source_disagreement'})
    return {'status': ('passed' if all(c['passed'] for c in checks) else 'source_disagreement') if checks else 'not_annotated',
            'scope': 'independently_transcribed_full_text_regions', 'checks': checks,
            'whole_page_verified': False, 'recognition_verified': False}
