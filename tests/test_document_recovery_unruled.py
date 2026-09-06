import copy

from src.audit_reports.document_recovery_unruled import unruled_tables


def words(rows):
    result = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text is None:
                continue
            right = [95, 180, 240][c]
            result.append({'id': len(result), 'text': text, 'bbox': [right - 4 * len(text), 30 + 12 * r, right, 38 + 12 * r],
                           'block': r, 'line': 0, 'word': c})
    return {'page': 1, 'words': result}


def test_amount_columns_keep_nil_zero_signs_and_missing_occurrences_distinct():
    ocr = words([['Cash', '1,000', '(500)'], ['Loans', '0', '-'], ['Deposits', '200', '400'],
                 ['Other', '300', None], ['Total', '1,500', '(100)']])
    original = copy.deepcopy(ocr)
    table, = unruled_tables(ocr)
    assert (table['row_count'], table['n_cols']) == (5, 3)
    assert [[c['candidate_text'] for c in row['cells']] for row in table['rows']] == [
        ['Cash', '1,000', '(500)'], ['Loans', '0', '-'], ['Deposits', '200', '400'],
        ['Other', '300', None], ['Total', '1,500', '(100)']]
    assert [i for row in table['rows'] for c in row['cells'] for i in c['ocr_word_ids']] == [w['id'] for w in ocr['words']]
    assert ocr == original and table['source_rule_ids'] == []
    assert not table['table_structure_verified'] and not table['row_association_verified']
    assert table['header_word_ids'] == []


def test_prose_dates_and_two_isolated_rows_do_not_establish_a_table():
    assert unruled_tables(words([['During 2022', '100', '200'], ['During 2023', '110', '220']])) == []
    ocr = words([['During', '2022', '2023'], ['the', '2024', '2025'], ['period', '2026', '2027']])
    for w in ocr['words']:
        if w['word'] > 0:
            w['text'] += ' years'
    assert unruled_tables(ocr) == []


def test_continuation_lines_remain_physical_rows_without_borrowing_numbers():
    table, = unruled_tables(words([['Cash', '1,000', '(500)'], ['including held', None, None],
                                   ['Loans', '0', '-'], ['Total', '1,000', '(500)']]))
    assert [c['candidate_text'] for c in table['rows'][1]['cells']] == ['including held', None, None]
    assert table['row_count'] == 4


def test_large_vertical_gap_separates_two_tables_with_the_same_columns():
    ocr = words([['Cash', '100', '200'], ['Loans', '300', '400'], ['Total', '400', '600']] * 2)
    for w in ocr['words'][9:]:
        w['bbox'][1] += 100
        w['bbox'][3] += 100
    tables = unruled_tables(ocr)
    assert len(tables) == 2 and [t['row_count'] for t in tables] == [3, 3]
