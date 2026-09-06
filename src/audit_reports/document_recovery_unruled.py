"""Unverified physical rows from repeated right-aligned OCR amounts.

No financial meaning or numeric cleanup is applied. Word occurrences and blank
cells survive; a physical row is not necessarily a logical disclosure row.
"""
from __future__ import annotations

import re
import statistics


_AMOUNT = re.compile(r'^[%+\-−]?\(?\d[\d.,]*\)?%?$|^[-−–—]$')


def _bounds(words):
    return [min(w['bbox'][0] for w in words), min(w['bbox'][1] for w in words),
            max(w['bbox'][2] for w in words), max(w['bbox'][3] for w in words)]


def _bands(words):
    groups = []
    for word in sorted(words, key=lambda w: ((w['bbox'][1] + w['bbox'][3]) / 2, w['bbox'][0], w['id'])):
        y = (word['bbox'][1] + word['bbox'][3]) / 2
        if groups and abs(y - statistics.median((w['bbox'][1] + w['bbox'][3]) / 2 for w in groups[-1])) <= 2:
            groups[-1].append(word)
        else:
            groups.append([word])
    return [sorted(group, key=lambda w: (w['bbox'][0], w['id'])) for group in groups]


def unruled_tables(ocr: dict) -> list[dict]:
    bands = _bands(ocr['words'])
    tails = []
    for i, band in enumerate(bands):
        last_label = max((w['bbox'][2] for w in band if any(c.isalpha() for c in w['text'])), default=0)
        words = [w for w in band if w['bbox'][0] >= last_label and _AMOUNT.fullmatch(w['text'])]
        if len(words) >= 2:
            tails.extend((i, w) for w in words)
    aligned = []
    for i, word in sorted(tails, key=lambda item: item[1]['bbox'][2]):
        if aligned and word['bbox'][2] - statistics.median(w['bbox'][2] for _, w in aligned[-1]) <= 4:
            aligned[-1].append((i, word))
        else:
            aligned.append([(i, word)])
    aligned = [group for group in aligned if len({i for i, _ in group}) >= 3]
    if len(aligned) < 2:
        return []
    # Independent blocks must share repeated physical rows. A date in a distant
    # caption cannot become a table column merely by being right-aligned.
    components = []
    for group in aligned:
        rows = {i for i, _ in group}
        matches = [g for g in components if any(len(rows & {i for i, _ in col}) >= 3 for col in g)]
        if matches:
            first = matches[0]
            first.append(group)
            for other in matches[1:]:
                first.extend(other)
                components.remove(other)
        else:
            components.append([group])
    tables = []
    for columns in components:
        if len(columns) < 2:
            continue
        columns.sort(key=lambda group: statistics.median(w['bbox'][2] for _, w in group))
        membership = {w['id']: c for c, group in enumerate(columns) for _, w in group}
        row_ids = sorted({i for group in columns for i, _ in group
                          if len({membership[w['id']] for w in bands[i] if w['id'] in membership}) >= 2})
        chunks = []
        for i in row_ids:
            if chunks and _bounds(bands[i])[1] - _bounds(bands[chunks[-1][-1]])[3] <= 30:
                chunks[-1].append(i)
            else:
                chunks.append([i])
        for chunk in chunks:
            if len(chunk) < 3:
                continue
            active = [[w for i, w in group if i in chunk] for group in columns]
            if any(len(words) < 3 for words in active):
                continue
            lefts = [min(w['bbox'][0] for w in words) for words in active]
            rights = [max(w['bbox'][2] for w in words) for words in active]
            if any(a >= b for a, b in zip(rights, lefts[1:])):
                continue  # Overlapping OCR amounts cannot establish a boundary.
            first, last = chunk[0], chunk[-1]
            body_words = [w for band in bands[first:last + 1] for w in band]
            box = _bounds(body_words)
            # Keep labels/notes in a broad first cell; their semantic association
            # remains unresolved. The gap, not proportional spacing, bounds it.
            labels = [w for w in body_words if w['bbox'][2] < lefts[0]]
            label_right = max((w['bbox'][2] for w in labels), default=box[0])
            xs = [box[0] - .01, (label_right + lefts[0]) / 2,
                  *((a + b) / 2 for a, b in zip(rights, lefts[1:])), rights[-1] + .01]
            rows = []
            # Retain physical continuation lines too; do not attach them to the
            # previous amount row based only on proximity.
            for i in range(first, last + 1):
                band = bands[i]
                y0, y1 = _bounds(band)[1], _bounds(band)[3]
                cells = []
                for c, (x0, x1) in enumerate(zip(xs, xs[1:])):
                    words = [w for w in band if x0 <= (w['bbox'][0] + w['bbox'][2]) / 2 < x1]
                    raw = ' '.join(w['text'] for w in words)
                    cells.append({'row': len(rows), 'column': c, 'bbox': [x0, y0, x1, y1],
                                  'ocr_text': raw, 'ocr_word_ids': [w['id'] for w in words],
                                  'outline_text': None, 'drawing_ids': [], 'unresolved_drawing_ids': [],
                                  'candidate_text': raw if words else None, 'candidate_method': 'ocr' if words else 'unobserved',
                                  'recognition_verified': False})
                rows.append({'index': len(rows), 'cells': cells})
            # Headers are deliberately not borrowed from nearby prose. The
            # original OCR blocks retain all header/footnote words for review.
            tables.append({'id': f"p{ocr['page']}:unruled{len(tables)}", 'method': 'ocr_repeated_amount_alignment',
                           'bbox': [xs[0], box[1], xs[-1], box[3]], 'column_boundaries': xs,
                           'source_rule_ids': [], 'numeric_columns': list(range(1, len(xs) - 1)),
                           'column_anchor_word_ids': [[w['id'] for w in words] for words in active],
                           'row_count': len(rows), 'n_cols': len(xs) - 1, 'rows': rows,
                           'header_bbox': None, 'header_text': '', 'header_word_ids': [],
                           'row_association_verified': False, 'header_association_verified': False,
                           'table_structure_verified': False})
    return tables
