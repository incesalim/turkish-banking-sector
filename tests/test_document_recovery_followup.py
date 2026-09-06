import copy
import json

import pytest

from src.audit_reports.document_corpus import Filing
from src.audit_reports.document_recovery_followup import build_manifest, main, validate_manifest


def row(bank='TEST', *, published=True, status='structured_candidates'):
    filing = Filing(bank, '2026Q1', 'consolidated').as_dict()
    return {**filing, 'published': published, 'status': status, 'source': {**filing, 'pdf_sha256': 'a' * 64}}


def report(directory, rows, group='0'):
    folder = directory / f'audit-document-corpus-report-{group}'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'capture-results.json').write_text(json.dumps({'filings': rows}), encoding='utf-8')


def test_only_published_sources_are_selected_with_failures_and_read_only_excluded(tmp_path):
    report(tmp_path, [row(), row('READONLY', published=False), row('FAILED', status='failed')])
    value = build_manifest(tmp_path, 123, 'b' * 40)
    assert validate_manifest(value) == {Filing('TEST', '2026Q1', 'consolidated'): 'a' * 64}
    assert [r['bank_ticker'] for r in value['exclusions']] == ['READONLY', 'FAILED']
    assert value['semantically_verified'] is False


def test_quality_only_or_absent_capture_report_cannot_trigger_recovery(tmp_path):
    folder = tmp_path / 'audit-document-corpus-report'
    folder.mkdir()
    (folder / 'quality-results.json').write_text('{}')
    assert build_manifest(tmp_path, 123, 'b' * 40)['filings'] == []


def test_duplicate_outcomes_or_source_filing_mismatch_fail_closed(tmp_path):
    report(tmp_path, [row()])
    report(tmp_path, [row()], '1')
    with pytest.raises(ValueError, match='duplicate'):
        build_manifest(tmp_path, 123, 'b' * 40)
    changed = row('OTHER')
    changed['source']['period'] = '2025Q1'
    report(tmp_path, [changed], '1')
    with pytest.raises(ValueError, match='differs'):
        build_manifest(tmp_path, 123, 'b' * 40)


@pytest.mark.parametrize('change', ['run', 'commit', 'hash', 'duplicate', 'approve'])
def test_changed_or_invalid_manifest_fields_cannot_expand_scope(tmp_path, change):
    report(tmp_path, [row()])
    value = build_manifest(tmp_path, 123, 'b' * 40)
    if change == 'run':
        value['source_run_id'] = True
    elif change == 'commit':
        value['source_head_sha'] = 'master'
    elif change == 'hash':
        value['filings'][0]['pdf_sha256'] = '../unrelated'
    elif change == 'duplicate':
        value['filings'].append(copy.deepcopy(value['filings'][0]))
    else:
        value['semantically_verified'] = True
    with pytest.raises(ValueError):
        validate_manifest(value)


def test_workflow_scope_output_is_bounded_by_the_selected_report(tmp_path):
    report(tmp_path, [row()])
    output, github = tmp_path / 'manifest.json', tmp_path / 'outputs'
    main(['--reports-dir', str(tmp_path), '--run-id', '123', '--head-sha', 'b' * 40,
          '--output', str(output), '--github-output', str(github)])
    assert github.read_text() == 'has_sources=true\nshards=[0]\n'
    assert len(validate_manifest(json.loads(output.read_text()))) == 1
