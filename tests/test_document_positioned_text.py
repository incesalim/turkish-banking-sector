import copy

import pytest

from src.audit_reports.document_positioned_text import positioned_text, verify_positioned_text


@pytest.fixture
def source():
    # The printed label belongs at x=20, on the row below the value. The PDF's
    # accessibility text instead starts at the preceding amount's right edge.
    return {'page': 9, 'actualtext_changes_word_view': True,
            'words': [{'id': 0, 'text': '280.664.505B. EMANET', 'bbox': [500, 90, 700, 100]}],
            'literal_glyph_words': [{'id': 0, 'text': '280.664.505', 'bbox': [500, 90, 550, 100]}],
            'spans': [{'id': 0, 'text': '280.664.505', 'bbox': [500, 90, 550, 100]},
                      {'id': 1, 'text': 'B. EMANET', 'bbox': [550, 90, 620, 100]}],
            'images': [{'id': 0, 'bbox': [20, 110, 100, 120]}],
            'native_structure': {'nodes': [
                {'id': 0, 'kind': 'structure', 'role': 'Span', 'children': [1, 2]},
                {'id': 1, 'kind': 'image', 'bbox': [20, 110, 100, 120], 'source_image_candidates': [0]},
                {'id': 2, 'kind': 'text', 'lines': [{'spans': [
                    {'text': 'B. EMANET', 'source_span_id': 1}]}]}]}}


def test_label_uses_its_declared_image_position_without_changing_source_or_splitting_words(source):
    before = copy.deepcopy(source)
    view = positioned_text(source)
    assert source == before
    assert [p['text'] for p in view['pieces']] == ['280.664.505', 'B. EMANET']
    amount, label = view['pieces']
    assert amount['bbox'] == [500, 90, 550, 100]
    assert label['bbox'] == [20, 110, 100, 120]
    assert label['source_span_id'] == 1 and label['source_image_id'] == 0
    assert label['association_verified'] is False and view['coverage_verified'] is False
    assert view['paired_source_span_ids'] == [1]
    assert verify_positioned_text(view, source)['valid']


@pytest.mark.parametrize('change', ['several_images', 'several_texts', 'ambiguous_image', 'unmapped_span',
                                  'changed_text', 'changed_image', 'duplicate_pair', 'empty_box'])
def test_uncertain_or_inconsistent_native_links_never_choose_an_arbitrary_position(source, change):
    nodes = source['native_structure']['nodes']
    if change in ('several_images', 'several_texts'):
        extra = copy.deepcopy(nodes[1 if change == 'several_images' else 2])
        extra['id'] = 3
        nodes.append(extra)
        nodes[0]['children'].append(3)
    elif change == 'ambiguous_image':
        nodes[1]['source_image_candidates'] = [0, 99]
    elif change == 'unmapped_span':
        nodes[2]['lines'][0]['spans'][0]['source_span_id'] = None
    elif change == 'changed_text':
        nodes[2]['lines'][0]['spans'][0]['text'] = 'A different label'
    elif change == 'changed_image':
        nodes[1]['bbox'] = [130, 110, 200, 120]
    elif change == 'empty_box':
        nodes[1]['bbox'] = source['images'][0]['bbox'] = [20, 110, 20, 120]
    else:
        nodes.append({**nodes[0], 'id': 3})
    view = positioned_text(source)
    assert view['replacement_pair_count'] == 0 and view['issues']
    assert [p['text'] for p in view['pieces']] == ['280.664.505']
    assert view['source_text_preserved_separately'] is True  # Original spans remain the residual source.


@pytest.mark.parametrize('change', ['move', 'text', 'drop', 'duplicate', 'source_link', 'approval'])
def test_derived_view_cannot_lose_or_move_a_source_piece(source, change):
    view = positioned_text(source)
    if change == 'move':
        view['pieces'][1]['bbox'][1] -= 20
    elif change == 'text':
        view['pieces'][0]['text'] = '0'
    elif change == 'drop':
        view['pieces'].pop()
    elif change == 'duplicate':
        view['pieces'].append(copy.deepcopy(view['pieces'][0]))
    elif change == 'source_link':
        view['pieces'][1]['source_span_id'] = 0
    else:
        view['pieces'][1]['association_verified'] = True
    assert not verify_positioned_text(view, source)['valid']


def test_regular_native_text_does_not_need_an_alternative_layout(source):
    source['actualtext_changes_word_view'] = False
    source['literal_glyph_words'] = None
    view = positioned_text(source)
    assert view['replacement_pair_count'] == 0
    assert [p['text'] for p in view['pieces']] == [source['words'][0]['text']]
    assert view['pieces'][0]['source_word_view'] == 'words'


def test_native_clipped_image_region_stays_inside_full_source_image(source):
    source['images'][0]['bbox'] = [20, 108, 100, 122]
    view = positioned_text(source)
    assert view['replacement_pair_count'] == 1
    assert view['pieces'][1]['bbox'] == [20, 110, 100, 120]


def test_source_region_annotation_rejects_an_unbound_or_moved_layout(source):
    from src.audit_reports.document_benchmark import check_annotations, paragraph_digest
    identity = {'pdf_sha256': 'a' * 64}
    case = {'id': 'heading_after_previous_amount', 'kind': 'positioned_text', 'page': 9,
            'method': 'native_image_replacement_pair', 'text_sha256': paragraph_digest('B. EMANET'),
            'bbox': [19, 109, 101, 121]}
    annotation = {'pdf_sha256': 'a' * 64, 'cases': [case]}
    structure = {'source': identity, 'pages': [{'page': 9, 'positioned_text': positioned_text(source)}]}
    evidence = [{'source': identity}, source]
    assert check_annotations(structure, evidence, annotation)['passed']
    structure['pages'][0]['positioned_text']['pieces'][1]['bbox'] = [550, 90, 620, 100]
    assert not check_annotations(structure, evidence, annotation)['passed']


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
def test_positioned_table_uses_display_coordinates_exactly_once(rotation):
    from types import SimpleNamespace
    import fitz
    from src.audit_reports.document_structure import _positioned_candidates
    words, spans, images, nodes = [], [], [], []
    for row, label in enumerate(['Alpha', 'Beta', 'Gamma']):
        y = 30 + row * 14
        for column, amount in enumerate(['1,000', '2,000']):
            x = 70 + 50 * column
            words.append({'id': len(words), 'text': amount, 'bbox': [x, y, x + 25, y + 7]})
        spans.append({'id': row, 'text': label, 'bbox': [145, y - 14, 175, y - 7]})
        images.append({'id': row, 'bbox': [15, y, 45, y + 7]})
        base = len(nodes)
        nodes.extend([{'id': base, 'kind': 'structure', 'role': 'Span', 'children': [base + 1, base + 2]},
                      {'id': base + 1, 'kind': 'image', 'bbox': images[-1]['bbox'], 'source_image_candidates': [row]},
                      {'id': base + 2, 'kind': 'text', 'lines': [{'spans': [{'text': label, 'source_span_id': row}]}]}])
    source = {'page': 1, 'words': words, 'literal_glyph_words': words, 'spans': spans,
              'images': images, 'native_structure': {'nodes': nodes}, 'actualtext_changes_word_view': True}
    with fitz.open() as pdf:
        page = pdf.new_page(width=240, height=180)
        page.set_rotation(rotation)
        view, tables, issues = _positioned_candidates(page, source, SimpleNamespace(lines=[]))
    assert not issues and len(tables) == 1
    assert tables[0]['n_cols'] == 2
    assert [r['label'] for r in tables[0]['rows']] == ['Alpha', 'Beta', 'Gamma']
    assert tables[0]['word_view'] == 'positioned_text'
    assert [p['bbox'] for p in view['pieces'][:6]] == [w['bbox'] for w in words]
