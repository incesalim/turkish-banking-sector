import copy
import json
from pathlib import Path

import pytest

from src.audit_reports.document_table_context import table_context, verify_table_context


@pytest.fixture
def pages():
    return json.loads((Path(__file__).parent / 'fixtures/document_table_context_qnb.json')
                      .read_text(encoding='utf-8'))['pages']


def test_source_reviewed_qnb_table_continues_with_same_instrument_columns(pages):
    before = copy.deepcopy(pages)
    contexts = table_context(pages)
    assert pages == before
    assert contexts[0]['continuations'] == []
    assert contexts[1]['continuations'] == [{
        'kind': 'table_continuation_candidate', 'status': 'unique_source_evidence',
        'from_page': 47, 'from_table_ids': ['p47:ruled0'], 'to_page': 48, 'to_table_id': 'p48:ruled0',
        'title': 'Information on debt instruments included in the calculation of equity',
        'column_identifiers': ['1', '2'], 'method': 'explicit_continued_title_and_ordered_column_identifiers',
        'fragments_merged': False, 'semantic_verification': 'not_performed'}]
    first, second = [c['tables'][0] for c in contexts]
    assert first['column_identifiers']['row'] == 1 and second['column_identifiers']['row'] == 0
    assert first['heading']['source_span_ids'] and second['heading']['source_span_ids']
    # The rendered source has one full-width title and two full-width category
    # bands on page 47; page 48 has two full-width category bands.
    assert [a for a in first['physical_grid']['anchors'] if a['column_span'] > 1] == [
        {'row': r, 'column': 0, 'row_span': 1, 'column_span': 3} for r in (0, 5, 18)]
    assert [a for a in second['physical_grid']['anchors'] if a['column_span'] > 1] == [
        {'row': r, 'column': 0, 'row_span': 1, 'column_span': 3} for r in (3, 10)]


@pytest.mark.parametrize('change', ['no_marker', 'different_title', 'reversed_identifiers',
                                  'different_identifiers', 'missing_identifier_source', 'page_gap',
                                  'another_heading', 'intervening_table'])
def test_similar_layout_cannot_supply_missing_continuation_evidence(pages, change):
    heading = next(e for e in pages[1]['narrative_elements'] if e['id'] == 'p48:narrative7')
    table = pages[1]['tables'][0]
    if change == 'no_marker':
        heading['text'] = heading['text'].replace(' (Continued)', '')
    elif change == 'different_title':
        heading['text'] = 'Another disclosure (Continued)'
    elif change == 'reversed_identifiers':
        table['rows'][0]['cells'][1]['text'], table['rows'][0]['cells'][2]['text'] = '2', '1'
    elif change == 'different_identifiers':
        table['rows'][0]['cells'][2]['text'] = '3'
    elif change == 'missing_identifier_source':
        table['rows'][0]['cells'][1]['word_ids'] = []
    elif change == 'page_gap':
        pages[1]['page'] += 1
    elif change == 'another_heading':
        another = copy.deepcopy(heading)
        another.update(id='ambiguous-title', text='Competing heading (Continued)')
        pages[1]['narrative_elements'].append(another)
    else:
        pages[1]['tables'].append({'id': 'between', 'method': 'other', 'rows': [], 'n_cols': 0,
                                   'bbox': [130, 176, 400, 180]})
    assert table_context(pages)[1]['continuations'] == []


def test_competing_previous_fragments_remain_explicit_without_merging(pages):
    another = copy.deepcopy(pages[0]['tables'][0])
    another['id'] = 'p47:other'
    pages[0]['tables'].append(another)
    link = table_context(pages)[1]['continuations'][0]
    assert link['status'] == 'ambiguous_previous_fragment'
    assert link['from_table_ids'] == ['p47:ruled0', 'p47:other'] and not link['fragments_merged']


@pytest.mark.parametrize('change', ['nonempty_null', 'uncovered_slot', 'shifted_boundary', 'duplicate_cell'])
def test_inconsistent_cell_geometry_does_not_invent_merged_slots(pages, change):
    table = pages[0]['tables'][0]
    if change == 'nonempty_null':
        table['rows'][0]['cells'][1]['text'] = '0'
    elif change == 'uncovered_slot':
        table['rows'][2]['cells'][1].update(bbox=None, text=None, word_ids=[])
    elif change == 'shifted_boundary':
        table['rows'][2]['cells'][1]['bbox'][2] -= 2
    else:
        table['rows'][0]['cells'][1] = copy.deepcopy(table['rows'][1]['cells'][1])
    assert table_context(pages)[0]['tables'][0]['physical_grid'] is None


def test_changed_or_dropped_context_fails_recomputation(pages):
    assert verify_table_context(pages) == []  # Historical structure.
    for page, context in zip(pages, table_context(pages), strict=True):
        page['table_context'] = context
    assert verify_table_context(pages) == []
    pages[1]['table_context']['continuations'][0]['column_identifiers'].reverse()
    assert verify_table_context(pages) == ['page_48:table_context_mismatch']
    del pages[0]['table_context']
    assert 'page_47:table_context_mismatch' in verify_table_context(pages)


def test_independent_continuation_annotation_requires_retained_source_words(pages):
    from src.audit_reports.document_benchmark import check_annotations
    fixture_dir = Path(__file__).parent / 'fixtures'
    fixture = json.loads((fixture_dir / 'document_table_context_qnb.json').read_text(encoding='utf-8'))
    annotation = json.loads((fixture_dir / 'document_annotations/qnbfb_2026q1_solo.json').read_text(encoding='utf-8'))
    annotation['cases'] = [c for c in annotation['cases'] if c.get('kind') == 'table_continuation']
    evidence = [{'source': fixture['source']}, *fixture['source_pages']]
    structure = {'source': fixture['source'], 'pages': pages}
    assert not check_annotations(structure, evidence, annotation)['passed']
    for page, context in zip(pages, table_context(pages), strict=True):
        page['table_context'] = context
    assert check_annotations(structure, evidence, annotation)['passed']
    identifier = pages[1]['table_context']['tables'][0]['column_identifiers']['cells'][0]['word_ids'][0]
    word = next(w for w in evidence[2]['words'] if w['id'] == identifier)
    word['text'] = 'Different instrument'
    assert not check_annotations(structure, evidence, annotation)['passed']
