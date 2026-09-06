"""Expose source lines inside tall ruled cells without parsing their figures.

Some PDFs draw only the table's column borders: one physical row then contains
an entire statement. Keep that original grid and provide a separate line view.
Wrapped labels remain separate source lines; this does not certify logical rows.
"""
from __future__ import annotations

from collections import Counter
from statistics import median

from .document_table_context import _grid


def _inside(box, region):
    x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return region[0] <= x <= region[2] and region[1] <= y <= region[3]


def _lines(words):
    """Cluster baseline bands, keeping close or overlapping lines ambiguous."""
    result = []
    for word in sorted(words, key=lambda w: ((w['bbox'][1] + w['bbox'][3]) / 2, w['bbox'][0], w['id'])):
        center = (word['bbox'][1] + word['bbox'][3]) / 2
        height = word['bbox'][3] - word['bbox'][1]
        matches = [line for line in result if abs(center - median(
            (w['bbox'][1] + w['bbox'][3]) / 2 for w in line)) <= .3 * min(
                [height, *(w['bbox'][3] - w['bbox'][1] for w in line)])]
        if len(matches) > 1:
            return None
        if matches:
            matches[0].append(word)
        else:
            result.append([word])
    for line in result:
        line.sort(key=lambda w: (w['bbox'][0], w['bbox'][1], w['id']))
    # Overlapping baseline bands cannot safely supply a row boundary.
    if any(max(w['bbox'][3] for w in a) > min(w['bbox'][1] for w in b)
           for a, b in zip(result, result[1:])):
        return None
    return result


def table_source_rows(page: dict, source: dict) -> dict:
    results = []
    for table in page['tables']:
        grid = _grid(table)
        if grid is None:
            continue
        words = [w for w in source['words'] if _inside(w['bbox'], table['bbox'])]
        by_id = {w['id']: w for w in words}
        cells = [c for r in table['rows'] for c in r['cells']]
        if (len(by_id) != len(words)
                or Counter(i for c in cells for i in c['word_ids']) != Counter(by_id.keys())
                or any(not c['source_text_matches'] or any(not _inside(by_id[i]['bbox'], c['bbox'])
                       for i in c['word_ids']) for c in cells)):
            continue
        split = []
        for row in table['rows']:
            anchors = [a for a in grid['anchors'] if a['row'] == row['index']]
            if (len(anchors) != table['n_cols']
                    or any(a['row_span'] != 1 or a['column_span'] != 1 for a in anchors)):
                continue
            refs = [i for c in row['cells'] for i in c['word_ids']]
            lines = _lines([by_id[i] for i in refs])
            if lines is None or len(lines) < 8:
                continue
            columns = {i: c['column'] for c in row['cells'] for i in c['word_ids']}
            if sum(len({columns[w['id']] for w in line} - {0}) >= 2 for line in lines) < 4:
                continue
            rendered = []
            for index, line in enumerate(lines):
                top, bottom = min(w['bbox'][1] for w in line), max(w['bbox'][3] for w in line)
                rendered.append({'index': index, 'bbox': [table['bbox'][0], top, table['bbox'][2], bottom],
                    'cells': [{'column': c, 'text': ' '.join(w['text'] for w in line if columns[w['id']] == c),
                               'word_ids': [w['id'] for w in line if columns[w['id']] == c],
                               'bbox': [grid['x_edges'][c], top, grid['x_edges'][c + 1], bottom]}
                              for c in range(table['n_cols'])]})
            split.append({'source_row': row['index'], 'lines': rendered})
        if split:
            results.append({'table_id': table['id'], 'split_rows': split})
    return {'schema_version': 'ruled-source-lines-1', 'tables': results,
            'method': 'source_words_within_original_ruled_columns',
            'logical_rows_verified': False, 'semantic_verification': 'not_performed'}


def verify_table_source_rows(page: dict, source: dict) -> list[str]:
    if 'table_source_rows' not in page:
        return []
    return [] if page['table_source_rows'] == table_source_rows(page, source) else ['table_source_rows_mismatch']
