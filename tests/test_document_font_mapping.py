import copy
import json

import fitz
import pytest

from src.audit_reports import document_font_mapping as mapping
from src.audit_reports.document_corpus import Filing
from src.audit_reports.document_recovery_text import check_text_regions
from test_document_ocr import retained_observation  # noqa: F401


FILING = Filing('TEST', '2026Q1', 'consolidated')
TEXT = 'İstanbul 123 (45) and loss'
EMPTY_CMAP = (b'/CIDInit /ProcSet findresource begin 12 dict begin begincmap '
              b'/CMapType 2 def 1 begincodespacerange <0000><FFFF> endcodespacerange '
              b'endcmap CMapName currentdict /CMap defineresource pop end end')


def source(tmp_path, *, rotation=0, empty=True, duplicate=False, subset=False):
    original = tmp_path / 'source.pdf'
    with fitz.open() as pdf:
        page = pdf.new_page(width=400, height=300)
        xref = page.insert_font(fontname='embedded', fontbuffer=fitz.Font('cjk').buffer)
        page.insert_text((40,80), TEXT, fontname='embedded', fontsize=12)
        if duplicate:
            page.insert_text((40,80), TEXT, fontname='embedded', fontsize=12)
        page.insert_text((40,120), 'Known native 0 - (42)', fontsize=12)
        if subset:
            pdf.subset_fonts()
        if empty:
            cmap = int(pdf.xref_get_key(xref, 'ToUnicode')[1].split()[0])
            pdf.update_stream(cmap, EMPTY_CMAP)
        page.set_rotation(rotation)
        pdf.save(original)
    return original


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
def test_recovery_retains_characters_glyph_proof_and_display_geometry(tmp_path, rotation):
    original = source(tmp_path, rotation=rotation)
    before = original.read_bytes()
    value = mapping.font_mapping_page(original, FILING, 1)
    assert value['mapped_characters'] == len(TEXT)
    assert value['unresolved_characters'] == value['unbound_missing_trace_characters'] == 0
    assert value['spans'][0]['candidate_text'] == TEXT
    assert value['spans'][0]['native_text'] != TEXT
    assert value['spans'][1]['candidate_text'] == value['spans'][1]['native_text'] == 'Known native 0 - (42)'
    assert all(c['source_span_id'] == 0 for c in value['replacements'])
    assert [c['source_char'] for c in value['replacements']] == list(range(len(TEXT)))
    assert all(c['candidate_text'] == chr(c['font_codepoints'][0]) for c in value['replacements'])
    with fitz.open(original) as pdf:
        raw = pdf[0].get_text('rawdict')['blocks'][0]['lines'][0]['spans'][0]['chars'][0]
        expected = fitz.Rect(raw['bbox']) * pdf[0].rotation_matrix
        assert value['replacements'][0]['bbox'] == pytest.approx(list(expected), abs=1e-4)
    assert original.read_bytes() == before
    assert json.loads(json.dumps(value)) == value
    assert not value['recognition_verified'] and not value['reading_order_verified']


def test_valid_pdf_unicode_is_not_replaced(tmp_path):
    value = mapping.font_mapping_page(source(tmp_path, empty=False), FILING, 1)
    assert value['fonts'] == [] and value['replacements'] == []
    assert value['spans'][0]['candidate_text'] == value['spans'][0]['native_text'] == TEXT
    assert value['missing_unicode_trace_characters'] == 0


@pytest.mark.parametrize('reason', ['duplicate_origin', 'duplicate_font', 'no_font_cmap', 'ineligible_same_name_font'])
def test_ambiguous_or_absent_source_binding_abstains(tmp_path, monkeypatch, reason):
    original = source(tmp_path, duplicate=reason == 'duplicate_origin', subset=reason == 'no_font_cmap')
    if reason == 'duplicate_font':
        real = mapping._font_maps
        def duplicate(pdf, page):
            fonts = real(pdf, page)
            return fonts + [dict(fonts[0], xref=999)]
        monkeypatch.setattr(mapping, '_font_maps', duplicate)
    elif reason == 'ineligible_same_name_font':
        real = mapping._font_resources
        def competitor(pdf, page):
            resources = real(pdf, page)
            # A valid/partial Unicode map does not rule out an entirely missing
            # trace span in another same-name resource with compatible glyph IDs.
            return resources + [dict(resources[0], xref=999)]
        monkeypatch.setattr(mapping, '_font_resources', competitor)
    value = mapping.font_mapping_page(original, FILING, 1)
    assert value['mapped_characters'] == 0
    assert value['unbound_missing_trace_characters'] == value['missing_unicode_trace_characters'] > 0
    assert value['unresolved_characters'] == value['missing_unicode_trace_characters']
    assert value['words'][0]['has_unresolved_characters']
    assert value['spans'][-1]['candidate_text'] == 'Known native 0 - (42)'


def test_only_whitespace_aliases_can_share_a_display_choice():
    assert mapping._choice([32, 160]) == (' ', 'whitespace_equivalence')
    assert mapping._choice([45, 173]) == (None, 'ambiguous_font_codepoints')
    assert mapping._choice([8260, 8725]) == (None, 'ambiguous_font_codepoints')


def test_font_name_match_is_exact_and_accounts_for_subset_truncation():
    assert mapping._trace_names('ABCDEF+Droid Sans Fallback Regular') == [
        'Droid Sans Fallback Regu', 'Droid Sans Fallback Regular']
    assert mapping._trace_names('TimesNewRomanPSMT') == ['TimesNewRomanPSMT']


def test_actual_subset_name_truncation_keeps_embedded_font_binding(tmp_path):
    original = source(tmp_path)
    with fitz.open(original) as pdf:
        font_xref = pdf[0].get_fonts()[0][0]
        descendant = int(pdf.xref_get_key(font_xref, 'DescendantFonts')[1].split()[0][1:])
        descriptor = int(pdf.xref_get_key(descendant, 'FontDescriptor')[1].split()[0])
        name = '/ABCDEF+Droid#20Sans#20Fallback#20Regular'
        pdf.xref_set_key(font_xref, 'BaseFont', name)
        pdf.xref_set_key(descendant, 'BaseFont', name)
        pdf.xref_set_key(descriptor, 'FontName', name)
        renamed = tmp_path / 'renamed.pdf'
        pdf.save(renamed)
    with fitz.open(renamed) as pdf:
        assert pdf[0].get_texttrace()[0]['font'] == 'Droid Sans Fallback Regu'
    assert mapping.font_mapping_page(renamed, FILING, 1)['spans'][0]['candidate_text'] == TEXT


def test_partial_unicode_map_is_not_treated_as_empty(tmp_path):
    original = source(tmp_path)
    with fitz.open(original) as pdf:
        xref = pdf[0].get_fonts()[0][0]
        cmap = int(pdf.xref_get_key(xref, 'ToUnicode')[1].split()[0])
        glyph = fitz.Font('cjk').has_glyph(ord('İ'), fallback=False)
        mapping_entry = f'1 beginbfchar <{glyph:04X}> <0130> endbfchar '.encode()
        pdf.update_stream(cmap, EMPTY_CMAP.replace(b'endcmap', mapping_entry + b'endcmap'))
        partial = tmp_path / 'partial.pdf'
        pdf.save(partial)
    value = mapping.font_mapping_page(partial, FILING, 1)
    assert value['fonts'] == [] and value['replacements'] == []
    assert ''.join(s['candidate_text'] for s in value['spans']).startswith('İ\ufffd')
    assert value['unresolved_characters'] > 0


@pytest.mark.parametrize('change', ['drop', 'text', 'move', 'approve', 'source', 'blocks', 'count'])
def test_packet_recomputes_font_view_from_original_and_rejects_mutations(retained_observation, change):  # noqa: F811
    from src.audit_reports.document_recovery import make_packet, recovery_identity, verify_packet
    ocr, derivative, original = retained_observation
    font = mapping.font_mapping_page(original, FILING, 1)
    packet = make_packet(ocr, None, {}, recovery_identity(ocr['engine'], None), font_mapping=font)
    verify_packet(packet, derivative, original, None)
    if change == 'drop':
        font['words'].pop()
    elif change == 'text':
        font['spans'][0]['candidate_text'] = 'Invented reading'
    elif change == 'move':
        font['words'][0]['bbox'][0] += 1
    elif change == 'approve':
        font['recognition_verified'] = True
    elif change == 'source':
        font['source']['pdf_sha256'] = '0' * 64
    elif change == 'blocks':
        font['blocks'][0]['text'] = 'Disclosed zero 1 and unknown'
    else:
        font['mapped_characters'] += 1
    with pytest.raises(ValueError, match='differs'):
        verify_packet(packet, derivative, original, None)


def test_independent_full_text_annotation_preserves_dotted_i_and_negative_sign(tmp_path):
    original = source(tmp_path)
    value = mapping.font_mapping_page(original, FILING, 1)
    annotations = tmp_path / 'annotations'
    annotations.mkdir()
    annotation = {'filing': FILING.as_dict(), 'pdf_sha256': value['source']['pdf_sha256'], 'cases': [
        {'id': 'full_region', 'kind': 'full_text_region', 'page': 1,
         'source_bbox': [20, 50, 350, 90], 'text': TEXT}]}
    (annotations / 'source.json').write_text(json.dumps(annotation), encoding='utf-8')
    checked = check_text_regions(value, annotations, word_reference='font_word_ids')
    assert checked['status'] == 'passed'
    assert 'font_word_ids' in checked['checks'][0] and 'ocr_word_ids' not in checked['checks'][0]
    changed = copy.deepcopy(value)
    changed['words'][0]['text'] = 'Istanbul'
    assert check_text_regions(changed, annotations)['status'] == 'source_disagreement'
    changed['source']['pdf_sha256'] = '0' * 64
    assert check_text_regions(changed, annotations)['status'] == 'not_annotated'


@pytest.mark.parametrize('number', [0, -1, True, 1.5, 2])
def test_page_scope_must_exist_in_original(tmp_path, number):
    with pytest.raises(ValueError):
        mapping.font_mapping_page(source(tmp_path), FILING, number)
