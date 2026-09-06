"""Bound recovery to successfully published sources in a capture run's reports.

These reports select work; they do not authorize text or financial approval.
Failed/read-only rows remain named exclusions. The worker rechecks PDF bytes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from .document_corpus import Filing


def validate_manifest(value: dict) -> dict[Filing, str]:
    if (value.get('schema_version') != 'document-recovery-followup-1'
            or type(value.get('source_run_id')) is not int or value['source_run_id'] < 1
            or not re.fullmatch(r'[0-9a-f]{40}', value.get('source_head_sha', ''))
            or value.get('semantically_verified') is not False):
        raise ValueError('Invalid recovery follow-up identity')
    result = {}
    for row in value['filings']:
        filing = Filing(row['bank_ticker'], row['period'], row['kind'])
        digest = row.get('pdf_sha256')
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Invalid follow-up PDF hash')
        if filing in result:
            raise ValueError('Duplicate filing in recovery follow-up')
        result[filing] = digest
    return result


def build_manifest(directory: Path, run_id: int, head_sha: str) -> dict:
    filings, exclusions, seen = [], [], set()
    reports = sorted(directory.glob('audit-document-corpus-report*/capture-results.json'))
    # A quality-only run has no capture report and must not trigger a corpus run.
    for path in reports:
        report = json.loads(path.read_text(encoding='utf-8'))
        for row in report['filings']:
            filing = Filing(row['bank_ticker'], row['period'], row['kind'])
            if filing in seen:
                raise ValueError('Capture reports contain duplicate filing outcomes')
            seen.add(filing)
            if row.get('published') is not True or row.get('status') not in ('source_preserved', 'structured_candidates'):
                exclusions.append({**filing.as_dict(), 'status': row.get('status'),
                                   'reason': 'not_successfully_published'})
                continue
            source = row['source']
            if {k: source[k] for k in filing.as_dict()} != filing.as_dict():
                raise ValueError('Capture report source differs from its filing')
            filings.append({**filing.as_dict(), 'pdf_sha256': source['pdf_sha256']})
    value = {'schema_version': 'document-recovery-followup-1', 'source_run_id': run_id,
             'source_head_sha': head_sha, 'reports': [p.relative_to(directory).as_posix() for p in reports],
             'filings': sorted(filings, key=lambda f: (f['bank_ticker'], f['period'], f['kind'])),
             'exclusions': exclusions, 'semantically_verified': False}
    validate_manifest(value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports-dir', type=Path, required=True)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--head-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--github-output', type=Path)
    args = parser.parse_args(argv)
    value = build_manifest(args.reports_dir, args.run_id, args.head_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    if args.github_output:
        with args.github_output.open('a', encoding='utf-8') as stream:
            stream.write(f"has_sources={'true' if value['filings'] else 'false'}\n")
            stream.write(f"shards={'[0,1,2,3]' if len(value['filings']) > 4 else '[0]'}\n")
    print(f"Recovery follow-up: {len(value['filings'])} published sources; {len(value['exclusions'])} named exclusions")


if __name__ == '__main__':
    main()
