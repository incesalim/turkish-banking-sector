import copy
import json
from collections import Counter
from pathlib import Path

import pytest

from src.audit_reports.document_table_rows import table_source_rows, verify_table_source_rows


@pytest.fixture
def sample():
    fixture = json.loads((Path(__file__).parent / 'fixtures/document_table_source_rows_tomk.json')
                         .read_text(encoding='utf-8'))
    return fixture['pages'][0], fixture['source_pages'][0]


def test_source_lines_keep_note_references_and_dates_in_their_original_columns(sample):
    page, source = sample
    original = copy.deepcopy(page)
    result = table_source_rows(page, source)
    assert page == original
    split = result['tables'][0]['split_rows'][0]
    assert split['source_row'] == 1 and len(split['lines']) == 64
    rows = [[c['text'] for c in line['cells']] for line in split['lines']]
    assert rows[0] == ['I. KAR PAYI GELİRLERİ', '(1)', '112.338', '-']
    assert rows[-2] == ['XXIV. NET DÖNEM KARI/ZARARI (XIII+XXIII)', '(11)', '148.071', '-']
    assert rows[-1] == ['Hisse Başına Kar/Zarar (Tam TL)', '', '0,09871', '-']
    table = next(t for t in page['tables'] if t['id'] == result['tables'][0]['table_id'])
    observed = Counter(i for line in split['lines'] for c in line['cells'] for i in c['word_ids'])
    assert observed == Counter(i for c in table['rows'][1]['cells'] for i in c['word_ids'])
    assert not observed.keys() & {i for c in table['rows'][0]['cells'] for i in c['word_ids']}
    assert all('value' not in c for line in split['lines'] for c in line['cells'])
    assert result['logical_rows_verified'] is False


@pytest.mark.parametrize('mutation', ['drop_word', 'duplicate_word', 'move_word', 'extra_word', 'overlap_lines'])
def test_incomplete_or_ambiguous_source_bindings_do_not_create_a_line_view(sample, mutation):
    page, source = sample
    table = next(t for t in page['tables'] if t['method'] == 'pymupdf_lines_strict')
    cell = table['rows'][1]['cells'][2]
    word = next(w for w in source['words'] if w['id'] == cell['word_ids'][0])
    if mutation == 'drop_word':
        cell['word_ids'].pop()
    elif mutation == 'duplicate_word':
        cell['word_ids'].append(cell['word_ids'][0])
    elif mutation == 'move_word':
        word['bbox'][0] = word['bbox'][2] = 550
    elif mutation == 'extra_word':
        source['words'].append({**word, 'id': 100000})
    else:
        # A glyph overlaps another baseline but has a different vertical center.
        word['bbox'][1] -= 4
        word['bbox'][3] += 5
    assert table_source_rows(page, source)['tables'] == []


@pytest.mark.parametrize('change', ['text', 'geometry', 'word_ref', 'drop_line', 'duplicate_line', 'drop_table'])
def test_saved_line_views_are_recomputed_from_source_not_trusted(sample, change):
    page, source = sample
    page['table_source_rows'] = table_source_rows(page, source)
    assert verify_table_source_rows(page, source) == []
    rows = page['table_source_rows']['tables'][0]['split_rows'][0]['lines']
    if change == 'text':
        rows[-2]['cells'][2]['text'] = '0'
    elif change == 'geometry':
        rows[-2]['cells'][2]['bbox'][0] += 10
    elif change == 'word_ref':
        rows[-2]['cells'][2]['word_ids'] = rows[0]['cells'][2]['word_ids']
    elif change == 'drop_line':
        rows.pop()
    elif change == 'duplicate_line':
        rows.append(copy.deepcopy(rows[0]))
    else:
        page['table_source_rows']['tables'] = []
    assert verify_table_source_rows(page, source) == ['table_source_rows_mismatch']


def test_independent_source_annotations_require_exact_text_and_column_positions(sample):
    from src.audit_reports.document_benchmark import check_annotations
    folder = Path(__file__).parent / 'fixtures'
    identity = json.loads((folder / 'document_table_source_rows_tomk.json').read_text(encoding='utf-8'))['source']
    annotation = json.loads((folder / 'document_annotations/tomk_2023q3_solo.json').read_text(encoding='utf-8'))
    annotation['cases'] = [c for c in annotation['cases'] if c['kind'] == 'source_table_line']
    assert len(annotation['cases']) == 3
    page, source = sample
    structure, evidence = {'source': identity, 'pages': [page]}, [{'source': identity}, source]
    assert not check_annotations(structure, evidence, annotation)['passed']
    page['table_source_rows'] = table_source_rows(page, source)
    assert check_annotations(structure, evidence, annotation)['passed']
    annotation['cases'][1]['columns'][1] = '-11'
    assert not check_annotations(structure, evidence, annotation)['passed']
