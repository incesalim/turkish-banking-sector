"""Render exact source pages for independent visual review; no text extraction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz


def render_review_pack(pdf_path: Path, source: dict, output_dir: Path, pages: list[int] | None) -> dict:
    body = pdf_path.read_bytes()
    if hashlib.sha256(body).hexdigest() != source['pdf_sha256'] or len(body) != source['byte_count']:
        raise ValueError('Visual review PDF differs from the source revision')
    with fitz.open(stream=body, filetype='pdf') as pdf:
        selected = list(range(1, len(pdf) + 1)) if pages is None else pages
        if not selected or selected != sorted(set(selected)) or any(type(n) is not int or not 1 <= n <= len(pdf) for n in selected):
            raise ValueError('Visual review pages must be distinct, ordered and within the original PDF')
        output_dir.mkdir(parents=True, exist_ok=True)
        report = {'schema_version': 'source-visual-review-pack-1', 'source': source,
                  'page_count': len(pdf), 'selected_pages': selected, 'pages': [],
                  'dpi': 150, 'pymupdf': fitz.VersionBind,
                  'implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'semantic_verification': 'not_performed'}
        for number in selected:
            try:
                page = pdf[number - 1]
                pixels = page.get_pixmap(dpi=150, colorspace=fitz.csRGB, alpha=False)
                png = pixels.tobytes('png')
                filename = f'p{number:04d}.png'
                (output_dir / filename).write_bytes(png)
                report['pages'].append({'page': number, 'status': 'rendered', 'file': filename,
                                        'png_sha256': hashlib.sha256(png).hexdigest(), 'png_bytes': len(png),
                                        'pixel_sha256': hashlib.sha256(pixels.samples).hexdigest(),
                                        'width': pixels.width, 'height': pixels.height,
                                        'display_rect': list(page.rect), 'rotation': page.rotation})
            except Exception as error:
                report['pages'].append({'page': number, 'status': 'failed', 'error': f'{type(error).__name__}: {error}'})
    report['status'] = 'failed' if any(p['status'] == 'failed' for p in report['pages']) else 'rendered'
    # Reads/rendering use the byte snapshot above. Also detect replacement of the
    # supplied file while preparing the pack so a run cannot claim current bytes.
    if pdf_path.read_bytes() != body:
        report.update(status='failed', error='Source file changed during visual review rendering')
    (output_dir / 'review-manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report
