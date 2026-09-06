import copy
import json

import pytest
import fitz

from test_document_ocr import retained_observation  # noqa: F401


def test_raster_selection_uses_display_bounds_once_and_counts_text_inside_images(tmp_path):
    import recover_document_corpus as cli
    with fitz.open() as picture:
        picture.new_page(width=200, height=100).insert_text((10, 30), 'Disclosed figures 1,000')
        pix = picture[0].get_pixmap()
    for rotation in (0, 90, 180, 270):
        path = tmp_path / f'rotation{rotation}.pdf'
        with fitz.open() as pdf:
            page = pdf.new_page(width=240, height=180)
            page.insert_text((10, 20), 'A typed banner outside the image has many words here')
            page.insert_image(fitz.Rect(20, 70, 220, 170), pixmap=pix)
            page.set_rotation(rotation)
            pdf.save(path)
        selection = cli.select_pages(path, [])
        assert selection['pages'] == [1]
        assert selection['observations'][0]['text_layer'] == 'raster'
        assert selection['observations'][0]['native_words_inside_images'] == 0


@pytest.mark.parametrize('args', [[], ['--limit', '1'], ['--pages', '1'],
                                ['--pages', '0', '--limit', '1'], ['--pages', '1,1', '--limit', '1'],
                                ['--pages', '1', '--limit', '1', '--publish']])
def test_local_recovery_and_publication_require_explicit_bounded_scope(args, monkeypatch):
    import recover_document_corpus as cli
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    with pytest.raises(SystemExit):
        cli.main(args)


def test_cli_retains_selected_page_and_names_corrupted_observation(retained_observation, tmp_path, monkeypatch):  # noqa: F811
    import recover_document_corpus as cli
    from src.audit_reports import document_ocr as ocr
    record, derivative, source = retained_observation
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'banks': {'TEST': {'urls': {'consolidated': {
        '2026Q1': 'https://bank.example/report.pdf'}}}}}))
    monkeypatch.setattr(ocr, 'ensure_models', lambda _: {})
    monkeypatch.setattr(ocr, '_engine', lambda *_: record['engine'])
    monkeypatch.setattr(ocr, 'capture_ocr_page', lambda *_a, **_kw: (record, derivative))
    output = tmp_path / 'out'
    args = ['--config', str(config), '--source-dir', str(source.parent), '--output-dir', str(output),
            '--bank', 'TEST', '--period', '2026Q1', '--kind', 'consolidated', '--limit', '1', '--pages', '1']
    assert cli.main(args) == 0
    report = json.loads((output / 'recovery-results.json').read_text())
    assert report['filings'][0]['selection']['pages'] == [1]
    assert report['filings'][0]['pages'][0]['status'] == 'recovery_candidates'
    assert len(list(output.rglob('p1.recovery.json'))) == 1
    corrupt = copy.deepcopy(record)
    corrupt['words'][0]['text'] = 'Invented'
    monkeypatch.setattr(ocr, 'capture_ocr_page', lambda *_a, **_kw: (corrupt, derivative))
    assert cli.main(args) == 1
    report = json.loads((output / 'recovery-results.json').read_text())
    assert report['filings'][0]['status'] == 'failed'
    assert 'Invalid OCR retention' in report['filings'][0]['pages'][0]['error']


def test_published_cli_replay_skips_pdf_work_and_explicit_recheck_reuses_raw_observations(
        retained_observation, tmp_path, monkeypatch):  # noqa: F811
    import recover_document_corpus as cli
    from src.audit_reports import document_ocr as ocr, r2_storage as r2
    from test_document_corpus_store import MemoryR2
    record, derivative, source = retained_observation
    client = MemoryR2()
    key = 'audit-pdfs/' + source.name
    client.objects[key] = source.read_bytes()
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'banks': {'TEST': {'urls': {'consolidated': {
        '2026Q1': 'https://bank.example/report.pdf'}}}}}))
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setattr(r2, 'get_client', lambda: client)
    monkeypatch.setattr(r2, '_bucket', lambda: 'test')
    monkeypatch.setattr(r2, 'list_audit_pdfs', lambda: [('TEST', '2026Q1', 'consolidated', key)])
    monkeypatch.setattr(ocr, 'ensure_models', lambda _: {})
    monkeypatch.setattr(ocr, '_engine', lambda *_: record['engine'])
    calls = []

    def capture(*_args, **_kwargs):
        calls.append('ocr')
        return record, derivative

    monkeypatch.setattr(ocr, 'capture_ocr_page', capture)
    output = tmp_path / 'out'
    args = ['--config', str(config), '--source-dir', str(source.parent), '--output-dir', str(output),
            '--bank', 'TEST', '--period', '2026Q1', '--kind', 'consolidated', '--limit', '1', '--pages', '1',
            '--from-r2', '--publish']
    assert cli.main(args) == 0
    writes = list(client.writes)
    assert calls == ['ocr']
    selector = cli.select_pages

    def forbidden(*_):
        raise AssertionError('Unchanged receipt must not download/classify the PDF')

    monkeypatch.setattr(cli, 'select_pages', forbidden)
    client.reads.clear()
    assert cli.main(args) == 0
    result = json.loads((output / 'recovery-results.json').read_text())['filings'][0]
    assert result['reused_receipt'] is True
    assert len(client.reads) == 2 and '/recovery-receipts/' in client.reads[0]
    assert '/recovery/' in client.reads[1]
    assert client.writes == writes and calls == ['ocr']
    monkeypatch.setattr(cli, 'select_pages', selector)
    assert cli.main(args + ['--recheck-bytes']) == 0
    result = json.loads((output / 'recovery-results.json').read_text())['filings'][0]
    assert 'reused_receipt' not in result and result['pages'][0]['reused'] is True
    assert client.writes == writes and calls == ['ocr']
    # The failed later check remains visible and invalidates the old receipt.
    monkeypatch.setattr(ocr, 'check_ocr_annotations', lambda *_: {'status': 'failed', 'checks': []})
    assert cli.main(args + ['--recheck-bytes']) == 1
    result = json.loads((output / 'recovery-results.json').read_text())['filings'][0]
    assert result['status'] == 'failed'
    assert cli.main(args) == 1
