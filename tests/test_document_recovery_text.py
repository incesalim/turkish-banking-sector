import copy
import json

import pytest

from src.audit_reports.document_recovery import make_packet, recovery_identity, verify_packet
from src.audit_reports.document_recovery_text import check_text_regions, text_blocks
from test_document_ocr import retained_observation  # noqa: F401


def test_blocks_preserve_all_words_and_expose_table_membership(retained_observation):  # noqa: F811
    ocr, _derivative, _original = retained_observation
    packet = make_packet(ocr, None, {}, recovery_identity(ocr['engine'], None))
    blocks = packet['view']['text_blocks']
    assert [i for b in blocks for i in b['ocr_word_ids']] == [w['id'] for w in ocr['words']]
    first = ocr['words'][0]['id']
    tables = [{'id': 'table1', 'rows': [{'cells': [{'ocr_word_ids': [first]}]}]}]
    associated = text_blocks(ocr, packet['view']['lines'], tables)
    assert associated[0]['table_associations'] == [{'table_id': 'table1', 'ocr_word_ids': [first]}]
    assert [b['text'] for b in associated] == [b['text'] for b in blocks]
    assert all(not b['paragraph_boundaries_verified'] for b in associated)
    packet['view']['text_blocks'][0]['text'] += ' invented prose'
    with pytest.raises(ValueError, match='differs'):
        verify_packet(packet, _derivative, _original, None)


@pytest.mark.parametrize('mutation', ['drop', 'duplicate', 'reorder', 'accent', 'sign', 'negation'])
def test_complete_region_comparison_exposes_omission_order_accents_and_meaning(tmp_path, mutation):
    source = {'bank_ticker': 'TEST', 'period': '2026Q1', 'kind': 'consolidated', 'pdf_sha256': 'a' * 64}
    tokens = ['İstanbul', 'did', 'not', 'report', '(123)', 'losses.']
    ocr = {'source': source, 'page': 1, 'words': [
        {'id': i, 'text': text, 'bbox': [10 + i * 10, 10, 19 + i * 10, 20]} for i, text in enumerate(tokens)]}
    annotation = {'filing': {k: source[k] for k in ('bank_ticker', 'period', 'kind')},
                  'pdf_sha256': source['pdf_sha256'], 'cases': [
                      {'id': 'passage', 'kind': 'full_text_region', 'page': 1,
                       'source_bbox': [0, 0, 100, 30], 'text': ' '.join(tokens)}]}
    (tmp_path / 'sample.json').write_text(json.dumps(annotation), encoding='utf-8')
    assert check_text_regions(ocr, tmp_path)['status'] == 'passed'
    ocr = copy.deepcopy(ocr)
    if mutation == 'drop':
        ocr['words'].pop()
    elif mutation == 'duplicate':
        ocr['words'].append(copy.deepcopy(ocr['words'][0]))
    elif mutation == 'reorder':
        ocr['words'].reverse()
    elif mutation == 'accent':
        ocr['words'][0]['text'] = 'Istanbul'
    elif mutation == 'sign':
        ocr['words'][4]['text'] = '123'
    else:
        ocr['words'][2]['text'] = 'now'
    before = copy.deepcopy(ocr)
    result = check_text_regions(ocr, tmp_path)
    assert result['status'] == 'source_disagreement'
    assert not result['checks'][0]['passed'] and result['checks'][0]['source_transcription'] == ' '.join(tokens)
    assert ocr == before and not result['recognition_verified']
