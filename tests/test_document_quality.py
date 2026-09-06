import pytest

from src.audit_reports.document_corpus import Filing
from src.audit_reports.document_quality import bank_patterns, source_identity_review, text_legibility_signals


def page(*texts, number=1):
    return {'page': number, 'spans': [{'id': i, 'text': t} for i, t in enumerate(texts)],
            'words': [{'id': i, 'text': t} for i, t in enumerate(' '.join(texts).split())]}


PATTERNS = bank_patterns({'ALPHA': {'name': 'Alpha Bank A.Ş.'}, 'BETA': {'name': 'Beta Bank A.Ş.'}})
FILING = Filing('ALPHA', '2026Q1', 'unconsolidated')


@pytest.mark.parametrize('date', ['31 MART 2026', 'March 31, 2026', '31 March 2026', '31.03.2026', '2026-03-31'])
@pytest.mark.parametrize('basis', ['KONSOLİDE OLMAYAN', 'Unconsolidated', 'Non-consolidated'])
def test_cover_claims_preserve_source_references_across_languages_and_date_formats(date, basis):
    result = source_identity_review(FILING, [page('Alpha Bank Anonim Şirketi', basis, date)], PATTERNS)
    assert result['status'] == 'supported_by_source_text'
    witness = result['observations'][0]
    assert witness['banks'][0]['source_span_ids'] == [0]
    assert witness['bases'][0]['source_span_ids'] == [1]
    assert witness['quarter_end_dates'][0]['source_span_ids'] == [2]
    assert result['semantic_verification'] == 'not_performed'


@pytest.mark.parametrize('bank,basis,date,issue', [
    ('Beta Bank', 'Unconsolidated', '31 March 2026', 'bank_conflicts_with_source_text'),
    ('Alpha Bank', 'Consolidated', '31 March 2026', 'basis_conflicts_with_source_text'),
    ('Alpha Bank', 'Unconsolidated', '30 June 2026', 'period_conflicts_with_source_text'),
    ('Alpha Bank', 'Unconsolidated', '31 March 2025', 'period_conflicts_with_source_text'),
])
def test_wrong_bank_basis_and_quarter_fail_even_when_the_year_matches(bank, basis, date, issue):
    result = source_identity_review(FILING, [page(bank, basis, date)], PATTERNS)
    assert result['status'] == 'source_text_conflict' and issue in result['issues']


def test_prior_period_competing_basis_and_separate_pages_are_not_silent_matches():
    both = source_identity_review(FILING, [page('Alpha Bank', 'Unconsolidated and consolidated',
                                               '31 March 2026', '31 December 2025')], PATTERNS)
    assert both['status'] == 'ambiguous'
    assert set(both['issues']) == {'period_has_competing_source_claims', 'basis_has_competing_source_claims'}
    separate = source_identity_review(FILING, [page('Alpha Bank', 'Unconsolidated'),
                                               page('31 March 2026', number=2)], PATTERNS)
    assert separate['status'] == 'unresolved'


def test_no_text_invalid_date_or_missing_bank_cannot_borrow_identity_from_filename():
    for source in [page(''), page('Alpha Bank', 'Unconsolidated', '31 June 2026'),
                   page('Unconsolidated', '31 March 2026')]:
        assert source_identity_review(FILING, [source], PATTERNS)['status'] == 'unresolved'


def test_opening_opinion_can_supply_identity_after_an_image_only_cover():
    result = source_identity_review(FILING, [page(''), page('Alpha Bank', 'Unconsolidated', '31 March 2026', number=2)], PATTERNS)
    assert result['status'] == 'supported_by_source_text' and result['claim_page'] == 2


def test_normal_names_do_not_match_suffixes_or_a_different_participation_bank():
    patterns = bank_patterns({'ING': {'name': 'ING Bank A.Ş.'},
                              'ZIRAAT': {'name': 'T.C. Ziraat Bankası A.Ş.'},
                              'ZIRAATK': {'name': 'Ziraat Katılım Bankası A.Ş.'},
                              'TOMK': {'name': 'T.O.M. Katılım Bankası A.Ş.'},
                              'QNBFB': {'name': 'QNB Bank A.Ş. (formerly QNB Finansbank)'}})
    from src.audit_reports.document_quality import page_identity_claims
    assert not page_identity_claims(page('Investment banking bank'), patterns)['banks']
    assert {x['bank_ticker'] for x in page_identity_claims(page('Ziraat Katılım Bankası'), patterns)['banks']} == {'ZIRAATK'}
    assert {x['bank_ticker'] for x in page_identity_claims(page('TOM Katılım Bankası Anonim Şirketi'), patterns)['banks']} == {'TOMK'}
    assert {x['bank_ticker'] for x in page_identity_claims(page('QNB Finansbank Anonim Şirketi'), patterns)['banks']} == {'QNBFB'}


def test_legibility_flags_repeated_suspicious_font_output_without_approving_clean_text():
    suspicious = page(' '.join([')ø1$16$/ 9$5/,./$5'] * 6))
    result = text_legibility_signals(suspicious)
    assert result['needs_text_review'] and 'possible_font_character_mapping_problem' in result['signals']
    assert len(result['suspect_word_ids']) == 12
    normal = page('Finansal varlıklar Total assets $1,000 1.000,00 (2.000) %12,50 - (1) (***) 0')
    result = text_legibility_signals(normal)
    assert not result['needs_text_review'] and result['readability_verified'] is False
    normal['replacement_character_count'] = 1
    assert text_legibility_signals(normal)['signals'] == ['replacement_characters']
