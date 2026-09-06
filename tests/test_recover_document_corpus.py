import copy
import json

import pytest

from test_document_ocr import retained_observation  # noqa: F401


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
