import copy
import hashlib
import json

import fitz
import pytest

from src.audit_reports.document_recovery_tables import capture_recovery_tables, check_recovery_table_annotations


@pytest.fixture
def pictured_table():
    with fitz.open() as original:
        page = original.new_page(width=240, height=180)
        for x in (20, 100, 160, 220):
            page.draw_line((x, 30), (x, 150), color=(.85, .85, .85), width=.6)
        for x, y, text in [(25, 45, 'Item'), (105, 45, 'Current'), (165, 45, 'Prior'),
                            (25, 80, 'Cash'), (105, 80, '1,000'), (165, 80, '500'),
                            (25, 120, 'Loans'), (105, 120, '0'), (165, 120, '-')]:
            page.insert_text((x, y), text, fontsize=8)
        words = [{'id': i, 'bbox': list(w[:4]), 'text': w[4], 'block': w[5], 'line': w[6], 'word': w[7]}
                 for i, w in enumerate(page.get_text('words'))]
        pix = page.get_pixmap(dpi=300, colorspace=fitz.csRGB, alpha=False)
        with fitz.open() as derivative:
            derivative.new_page(width=240, height=180).insert_image(page.rect, pixmap=pix)
            body = derivative.tobytes()
    ocr = {'page': 1, 'width': 240, 'height': 180, 'words': words,
           'render': {'pixels_sha256': hashlib.sha256(pix.samples).hexdigest()}}
    return ocr, body


def test_light_source_rules_and_row_baselines_keep_zero_and_dash_distinct(pictured_table):
    ocr, body = pictured_table
    result = capture_recovery_tables(ocr, None, body)
    table, = result['tables']
    assert (table['row_count'], table['n_cols']) == (2, 3)
    assert [[c['candidate_text'] for c in row['cells']] for row in table['rows']] == [
        ['Cash', '1,000', '500'], ['Loans', '0', '-']]
    assert 'Current' in table['header_text'] and 'Prior' in table['header_text']
    ids = table['header_word_ids'] + [i for row in table['rows'] for c in row['cells'] for i in c['ocr_word_ids']]
    assert sorted(ids) == [w['id'] for w in ocr['words']]
    assert not table['header_association_verified'] and not table['table_structure_verified']


def test_punctuation_and_uncertain_o_are_row_anchors_without_rewriting_source_words(pictured_table):
    ocr, body = pictured_table
    ocr = copy.deepcopy(ocr)
    for word in ocr['words']:
        if word['text'] == '1,000':
            word['text'] = '1,000!'
        if word['text'] == '0':
            word['text'] = 'o;'
    table, = capture_recovery_tables(ocr, None, body)['tables']
    assert table['row_count'] == 2
    assert table['rows'][0]['cells'][1]['candidate_text'] == '1,000!'
    assert table['rows'][1]['cells'][1]['candidate_text'] == 'o;'


def test_outline_reading_remains_distinct_from_ocr_and_unknown_sign_stays_unknown(pictured_table):
    ocr, body = pictured_table
    word = next(w for w in ocr['words'] if w['text'] == '1,000')
    vector = {'matched_paths': [{'drawing_id': 42, 'bbox': word['bbox'], 'text': '(1,000)'}]}
    cell = capture_recovery_tables(ocr, vector, body)['tables'][0]['rows'][0]['cells'][1]
    assert cell['ocr_text'] == '1,000'
    assert cell['outline_text'] == cell['candidate_text'] == '(1,000)'
    assert cell['drawing_ids'] == [42] and not cell['recognition_verified']
    vector = {'matched_paths': [], 'unresolved_paths': [{'drawing_id': 42, 'bbox': word['bbox'], 'text': None,
                                                       'glyphs': [{'character': None}]}]}
    cell = capture_recovery_tables(ocr, vector, body)['tables'][0]['rows'][0]['cells'][1]
    assert cell['outline_text'] is None and cell['candidate_method'] == 'unresolved_outline'
    assert cell['candidate_text'] is None and cell['ocr_text'] == '1,000'
    assert cell['unresolved_drawing_ids'] == [42]


def test_changed_source_pixels_are_rejected(pictured_table):
    ocr, body = pictured_table
    ocr['render']['pixels_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='pixels differ'):
        capture_recovery_tables(ocr, None, body)


@pytest.mark.parametrize('change', ['swap', 'drop', 'duplicate', 'move'])
def test_independent_source_cell_check_rejects_wrong_row_column_or_content(pictured_table, tmp_path, change):
    ocr, body = pictured_table
    ocr['source'] = {'bank_ticker': 'TEST', 'period': '2026Q1', 'kind': 'consolidated', 'pdf_sha256': 'a' * 64}
    word = next(w for w in ocr['words'] if w['text'] == '1,000')
    vector = {'matched_paths': [{'drawing_id': 42, 'bbox': word['bbox'], 'text': '1,000'}]}
    layout = capture_recovery_tables(ocr, vector, body)
    vd, od = tmp_path / 'vector', tmp_path / 'ocr'
    vd.mkdir()
    od.mkdir()
    (vd / 'case.json').write_text(json.dumps({'filing': {k: ocr['source'][k] for k in ('bank_ticker', 'period', 'kind')},
        'pdf_sha256': 'a' * 64, 'cases': [{'id': 'cash_current', 'page': 1, 'source_bbox': word['bbox'], 'text': '1,000'}]}))
    assert check_recovery_table_annotations(layout, ocr, vector, vd, od)['status'] == 'passed'
    cells = layout['tables'][0]['rows'][0]['cells']
    if change == 'swap':
        cells[1]['candidate_text'], cells[2]['candidate_text'] = cells[2]['candidate_text'], cells[1]['candidate_text']
    elif change == 'drop':
        cells.pop(1)
    elif change == 'duplicate':
        cells.append(copy.deepcopy(cells[1]))
    else:
        cells[1]['bbox'][1] += 70
    assert check_recovery_table_annotations(layout, ocr, vector, vd, od)['status'] == 'failed'
