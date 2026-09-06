"""Candidate grids from retained source pixels, with separate raw text readings.

Printed vertical rules suggest columns; repeated numeric baselines suggest rows.
Neither observation establishes financial meaning, units or header associations.
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

import fitz
import numpy as np


def _overlap(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0])) / max(a[1] - a[0], b[1] - b[0], 1e-9)


def pixel_vertical_rules(derivative: bytes, ocr: dict) -> list[dict]:
    with fitz.open(stream=derivative) as pdf:
        images = pdf[0].get_images()
        if len(pdf) != 1 or len(images) != 1:
            raise ValueError('Recovery grid requires the retained single source image')
        pix = fitz.Pixmap(pdf, images[0][0])
        if hashlib.sha256(pix.samples).hexdigest() != ocr['render']['pixels_sha256']:
            raise ValueError('Recovery grid pixels differ from the OCR source image')
        pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        dark = pixels[:, :, :3].max(axis=2) < 240
        sx, sy = ocr['width'] / pix.width, ocr['height'] / pix.height
        minimum = 20 / sy
        pieces = []
        for x in range(pix.width):
            ys = np.flatnonzero(dark[:, x])
            if len(ys) < minimum * .7:
                continue
            for run in np.split(ys, np.flatnonzero(np.diff(ys) > max(3, int(1 / sy))) + 1):
                if len(run) < 2:
                    continue
                top, bottom = int(run[0]), int(run[-1]) + 1
                if bottom - top >= minimum and len(run) / (bottom - top) >= .7:
                    pieces.append([x, x + 1, top, bottom])
        groups = []
        for piece in pieces:
            match = next((g for g in reversed(groups) if piece[0] - g[1] <= 1
                          and abs(piece[2] - g[2]) * sy < 3 and abs(piece[3] - g[3]) * sy < 3), None)
            if match is None:
                groups.append(piece[:])
            else:
                match[1] = piece[1]
                match[2] = min(match[2], piece[2])
                match[3] = max(match[3], piece[3])
        rules = []
        for left, right, top, bottom in groups:
            if (right - left) * sx > 2.5:
                continue  # A dark fill is not a thin printed column boundary.
            rules.append({'id': len(rules), 'x': (left + right) / 2 * sx,
                          'y0': top * sy, 'y1': bottom * sy,
                          'pixel_bbox': [left, top, right, bottom]})
        return rules


def _numeric(text: str) -> bool:
    # Geometry only: border punctuation must not make a real row disappear.
    # An OCR 'o' can anchor a baseline but is never rewritten as a numeric zero.
    stripped = text.strip('|}:;![]()., \t')
    return (stripped in ('o', 'O', '-', '−', '–', '—') or
            any(c.isdigit() for c in text) and not any(c.isalpha() for c in text) and '/' not in text)


def _inside(item, bbox):
    b = item['bbox']
    return bbox[0] <= (b[0] + b[2]) / 2 < bbox[2] and bbox[1] <= (b[1] + b[3]) / 2 < bbox[3]


def _text(words):
    groups = defaultdict(list)
    for w in words:
        groups[w['block'], w['line']].append(w)
    return '\n'.join(' '.join(w['text'] for w in sorted(group, key=lambda w: w['word']))
                     for group in groups.values())


def capture_recovery_tables(ocr: dict, vector: dict | None, derivative: bytes) -> dict:
    rules = pixel_vertical_rules(derivative, ocr)
    groups = []
    for rule in sorted(rules, key=lambda r: r['x']):
        matches = [g for g in groups if any(_overlap((rule['y0'], rule['y1']), (r['y0'], r['y1'])) >= .8 for r in g)]
        if matches:
            group = matches[0]
            group.append(rule)
            for other in matches[1:]:
                group.extend(other)
                groups.remove(other)
        else:
            groups.append([rule])
    tables = []
    for group in groups:
        columns = []
        for rule in sorted(group, key=lambda r: r['x']):
            if columns and rule['x'] - columns[-1]['x'] < 3:
                if rule['y1'] - rule['y0'] > columns[-1]['y1'] - columns[-1]['y0']:
                    columns[-1] = rule
            else:
                columns.append(rule)
        if len(columns) < 3:
            continue
        xs = [r['x'] for r in columns]
        top, bottom = min(r['y0'] for r in columns), max(r['y1'] for r in columns)
        col_words = [[w for w in ocr['words'] if _inside(w, [a, top, b, bottom])]
                     for a, b in zip(xs, xs[1:])]
        numeric_columns = [i for i, words in enumerate(col_words) if i > 0
                           and sum(_numeric(w['text']) for w in words) >= 2
                           and sum(_numeric(w['text']) for w in words) / max(len(words), 1) >= .6]
        if len(numeric_columns) < 2:
            continue
        anchors = []
        paths = (vector or {}).get('matched_paths', [])
        unresolved = [p for p in (vector or {}).get('unresolved_paths', []) if p.get('glyphs')]
        for c in numeric_columns:
            bbox = [xs[c], top, xs[c + 1], bottom]
            candidates = [p for p in paths if _inside(p, bbox) and _numeric(p['text'])]
            candidates += [w for w in col_words[c] if _numeric(w['text'])]
            anchors.extend({'y': (w['bbox'][1] + w['bbox'][3]) / 2, 'column': c} for w in candidates)
        baselines = []
        for anchor in sorted(anchors, key=lambda a: a['y']):
            if baselines and anchor['y'] - statistics.median(a['y'] for a in baselines[-1]) <= 2:
                baselines[-1].append(anchor)
            else:
                baselines.append([anchor])
        ys = [statistics.median(a['y'] for a in g) for g in baselines if len({a['column'] for a in g}) >= 2]
        if len(ys) < 2:
            continue
        body_top = max(top, ys[0] - (ys[1] - ys[0]) / 2)
        edges = [body_top, *((a + b) / 2 for a, b in zip(ys, ys[1:])), bottom]
        rows = []
        for r, (y0, y1) in enumerate(zip(edges, edges[1:])):
            cells = []
            for c, (x0, x1) in enumerate(zip(xs, xs[1:])):
                bbox = [x0, y0, x1, y1]
                words = [w for w in col_words[c] if _inside(w, bbox)]
                outlines = [p for p in paths if _inside(p, bbox)]
                unknown = [p for p in unresolved if x0 <= p['bbox'][0] and p['bbox'][2] <= x1
                           and y0 <= p['bbox'][1] and p['bbox'][3] <= y1]
                raw = _text(words)
                shape_text = outlines[0]['text'] if len(outlines) == 1 and c in numeric_columns else None
                abstain = bool(unknown and c in numeric_columns)
                cells.append({'row': r, 'column': c, 'bbox': bbox,
                              'ocr_text': raw, 'ocr_word_ids': [w['id'] for w in words],
                              'outline_text': shape_text, 'drawing_ids': [p['drawing_id'] for p in outlines],
                              'unresolved_drawing_ids': [p['drawing_id'] for p in unknown],
                              'candidate_text': None if abstain else shape_text if shape_text is not None else raw,
                              'candidate_method': 'unresolved_outline' if abstain else 'outline' if shape_text is not None else 'ocr',
                              'recognition_verified': False})
            rows.append({'index': r, 'cells': cells})
        header = [xs[0], top, xs[-1], body_top]
        header_words = [w for w in ocr['words'] if _inside(w, header)]
        tables.append({'id': f"p{ocr['page']}:recovered_grid{len(tables)}", 'method': 'source_pixel_columns_numeric_baselines',
                       'bbox': [xs[0], top, xs[-1], bottom], 'column_boundaries': xs,
                       'source_rule_ids': [r['id'] for r in columns], 'numeric_columns': numeric_columns,
                       'row_count': len(rows), 'n_cols': len(xs) - 1, 'rows': rows,
                       'header_bbox': header, 'header_text': _text(header_words),
                       'header_word_ids': [w['id'] for w in header_words],
                       'header_association_verified': False, 'table_structure_verified': False})
    if not tables:
        # The source image was checked above. Alignment is an alternative only
        # when no ruled grid was found; mixed ruled/unruled pages need review.
        from .document_recovery_unruled import unruled_tables
        tables = unruled_tables(ocr)
    return {'source_pixels_sha256': ocr['render']['pixels_sha256'], 'vertical_rules': rules,
            'tables': tables, 'semantic_verification': 'not_performed'}


def check_recovery_table_annotations(layout: dict, ocr: dict, vector: dict | None,
                                     vector_directory: Path, ocr_directory: Path) -> dict:
    """Test the cell association separately from upstream word recognition tests."""
    source = ocr['source']
    identity = {k: source[k] for k in ('bank_ticker', 'period', 'kind')}
    cells = [c for table in layout['tables'] for row in table['rows'] for c in row['cells']]
    checks = []
    for method, directory in [('vector', vector_directory), ('ocr', ocr_directory)]:
        if not directory.is_dir():
            raise ValueError('Recovery source annotation directory is missing')
        for path in sorted(directory.glob('*.json')):
            annotation = json.loads(path.read_text(encoding='utf-8'))
            if annotation['filing'] != identity or annotation['pdf_sha256'] != source['pdf_sha256']:
                continue
            for case in annotation['cases']:
                if case['page'] != ocr['page'] or case.get('allow_unresolved'):
                    continue
                x0, y0, x1, y1 = case['source_bbox']
                if method == 'vector':
                    words = [p for p in (vector or {}).get('matched_paths', [])
                             if x0 <= p['bbox'][0] and p['bbox'][2] <= x1
                             and y0 <= p['bbox'][1] and p['bbox'][3] <= y1 and p['text'] == case['text']]
                    hits = [c for c in cells if any(w['drawing_id'] in c['drawing_ids'] and _inside(w, c['bbox']) for w in words)]
                    passed = len(words) == len(hits) == 1 and hits[0]['candidate_text'] == case['text']
                else:
                    pattern = re.compile(r'(?<!\w)' + re.escape(case['token']) + r'(?!\w)')
                    words = [w for w in ocr['words'] if _inside(w, [x0, y0, x1, y1]) and pattern.search(w['text'])]
                    hits = [c for c in cells if any(w['id'] in c['ocr_word_ids'] and _inside(w, c['bbox']) for w in words)]
                    passed = len(words) == len(hits) == 1 and bool(pattern.search(hits[0]['ocr_text']))
                checks.append({'id': f"{method}:{case['id']}", 'passed': passed,
                               'cells': [[c['row'], c['column']] for c in hits], 'full_cell_verified': False})
    return {'status': ('passed' if all(c['passed'] for c in checks) else 'failed') if checks else 'not_annotated',
            'scope': 'annotated_recovery_cell_regions_only', 'checks': checks, 'semantically_verified': False}
