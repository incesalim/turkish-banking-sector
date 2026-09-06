import hashlib
import json

import fitz
import pytest

from src.audit_reports.document_corpus import Filing, source_identity
from src.audit_reports.document_review_pack import render_review_pack


@pytest.fixture
def source_pdf(tmp_path):
    path = tmp_path / 'original.pdf'
    with fitz.open() as pdf:
        for number in range(3):
            page = pdf.new_page(width=200, height=120)
            page.insert_text((20, 40), f'Original page {number + 1}')
        pdf[1].set_rotation(90)
        pdf.save(path)
    source = source_identity(path, Filing('TEST', '2026Q1', 'unconsolidated'))
    return path, source, tmp_path / 'review'


def test_pack_has_every_original_page_and_exact_display_pixels(source_pdf):
    path, source, output = source_pdf
    result = render_review_pack(path, source, output, None)
    assert result['status'] == 'rendered' and result['semantic_verification'] == 'not_performed'
    assert result['selected_pages'] == [1, 2, 3]
    assert [p['page'] for p in result['pages']] == [1, 2, 3]
    assert json.loads((output / 'review-manifest.json').read_text(encoding='utf-8')) == result
    with fitz.open(path) as pdf:
        for recorded in result['pages']:
            png = (output / recorded['file']).read_bytes()
            assert hashlib.sha256(png).hexdigest() == recorded['png_sha256']
            assert len(png) == recorded['png_bytes']
            original = pdf[recorded['page'] - 1].get_pixmap(dpi=150, colorspace=fitz.csRGB, alpha=False)
            assert fitz.Pixmap(png).samples == original.samples
            assert recorded['pixel_sha256'] == hashlib.sha256(original.samples).hexdigest()
    assert result['pages'][1]['rotation'] == 90


def test_a_failed_page_is_named_and_does_not_hide_later_pages(source_pdf, monkeypatch):
    original = fitz.Page.get_pixmap

    def fail_second(page, **kwargs):
        if page.number == 1:
            raise RuntimeError('Source page rendering failed')
        return original(page, **kwargs)

    monkeypatch.setattr(fitz.Page, 'get_pixmap', fail_second)
    result = render_review_pack(*source_pdf, None)
    assert result['status'] == 'failed'
    assert [p['status'] for p in result['pages']] == ['rendered', 'failed', 'rendered']
    assert result['pages'][1]['page'] == 2 and 'rendering failed' in result['pages'][1]['error']


@pytest.mark.parametrize('pages', [[], [0], [4], [1, 1], [2, 1], [True]])
def test_invalid_selection_cannot_create_a_complete_pack(source_pdf, pages):
    with pytest.raises(ValueError, match='Visual review pages'):
        render_review_pack(*source_pdf, pages)


def test_another_pdf_cannot_borrow_the_source_identity(source_pdf):
    path, source, output = source_pdf
    path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='differs'):
        render_review_pack(path, source, output, None)
    assert not output.exists()
