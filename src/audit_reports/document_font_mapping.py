"""Candidate text from embedded font maps where PDF Unicode maps are empty.

This keeps raw characters and all alternatives. It only joins a missing Unicode
trace glyph to a native character at the same font/origin whose fallback code is
that glyph ID. OCR and original source text remain independent observations.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
from pathlib import Path
import re

import fitz

from .document_corpus import Filing, source_identity


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _trace_names(name):
    # MuPDF text extraction caps the font name at 31 bytes, before removing
    # the subset prefix. Resource names themselves have no such limit.
    return sorted({re.sub(r'^[A-Z]{6}\+', '', n) for n in
                   (name, name.encode('utf-8')[:31].decode('utf-8', errors='ignore'))})


def _font_maps(pdf, page):
    fonts = []
    for row in page.get_fonts(full=True):
        if row[2] != 'Type0' or row[5] != 'Identity-H':
            continue
        kind, value = pdf.xref_get_key(row[0], 'ToUnicode')
        if kind != 'xref':
            continue
        cmap_xref = int(value.split()[0])
        cmap = pdf.xref_stream(cmap_xref)
        if (not cmap or any(op in cmap for op in (b'beginbfchar', b'beginbfrange', b'usecmap'))
                or pdf.xref_get_key(cmap_xref, 'UseCMap')[0] != 'null'):
            continue
        _name, extension, _type, body = pdf.extract_font(row[0])
        if extension != 'ttf' or not body:
            continue
        font = fitz.Font(fontbuffer=body)
        inverse = defaultdict(list)
        for code in font.valid_codepoints():
            glyph = font.has_glyph(code, fallback=False)
            if glyph:
                inverse[glyph].append(code)
        if not inverse:
            continue
        fonts.append({'xref': row[0], 'resource': row[4], 'base_font': re.sub(r'^[A-Z]{6}\+', '', row[3]),
                      'resource_font_name': row[3], 'trace_font_names': _trace_names(row[3]),
                      'program_sha256': _sha(body), 'program_bytes': len(body),
                      'to_unicode_xref': cmap_xref, 'to_unicode_sha256': _sha(cmap),
                      'glyph_to_codepoints': dict(inverse)})
    return fonts


def _font_resources(pdf, page):
    """Include ineligible fonts when ruling out a same-name resource collision."""
    resources = []
    for row in page.get_fonts(full=True):
        _name, _extension, _type, body = pdf.extract_font(row[0])
        count = None
        if body:
            try:
                count = fitz.Font(fontbuffer=body).glyph_count
            except (RuntimeError, ValueError):
                pass  # An unreadable program cannot rule out this resource.
        resources.append({'xref': row[0], 'resource': row[4], 'type': row[2],
                          'trace_font_names': _trace_names(row[3]), 'glyph_count': count,
                          'program_sha256': _sha(body) if body else None})
    return resources


def _origin(point):
    return tuple(round(v, 4) for v in point)


def _bbox(box, matrix):
    return [round(v, 4) for v in fitz.Rect(box) * matrix]


def _choice(codepoints):
    if len(codepoints) == 1:
        return chr(codepoints[0]), 'unique_font_codepoint'
    if codepoints and all(chr(c).isspace() for c in codepoints):
        return ' ', 'whitespace_equivalence'
    return None, 'ambiguous_font_codepoints'


def font_mapping_page(original: Path, filing: Filing, number: int) -> dict:
    if type(number) is not int or number < 1:
        raise ValueError('A positive PDF page number is required')
    source = source_identity(original, filing)
    with fitz.open(original) as pdf:
        if number > len(pdf):
            raise ValueError('Font mapping page is outside the source PDF')
        page = pdf[number - 1]
        matrix = page.rotation_matrix
        fonts = _font_maps(pdf, page)
        resources = _font_resources(pdf, page)
        missing = defaultdict(list)
        missing_origins = set()
        traces = page.get_texttrace()
        trace_missing = sum(c[0] == 65533 for trace in traces for c in trace['chars'])
        for i, trace in enumerate(traces):
            missing_origins.update((trace['font'], _origin(c[2])) for c in trace['chars'] if c[0] == 65533)
            # A partially decoded span needs a different binding proof. Do not
            # apply an unrelated font with the same family name to known text.
            if not trace['chars'] or not all(c[0] == 65533 for c in trace['chars']):
                continue
            options = [f for f in fonts if trace['font'] in f['trace_font_names']
                       and all(c[1] in f['glyph_to_codepoints'] for c in trace['chars'])]
            if len(options) != 1:
                continue
            font = options[0]
            possible = {r['xref'] for r in resources if trace['font'] in r['trace_font_names']
                        and (r['glyph_count'] is None or all(0 <= c[1] < r['glyph_count'] for c in trace['chars']))}
            if possible != {font['xref']}:
                continue
            for j, char in enumerate(trace['chars']):
                choices = font['glyph_to_codepoints'][char[1]]
                candidate, method = _choice(choices)
                missing[trace['font'], _origin(char[2])].append({
                    'trace_id': i, 'trace_char': j, 'glyph_id': char[1], 'font_xref': font['xref'],
                    'font_codepoints': choices, 'candidate_text': candidate, 'method': method})
        raw = page.get_text('rawdict', flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES,
                            clip=fitz.INFINITE_RECT())
        origins = defaultdict(int)
        for block in raw['blocks']:
            if block['type'] == 0:
                for line in block['lines']:
                    for span in line['spans']:
                        for char in span['chars']:
                            origins[span['font'], _origin(char['origin'])] += 1
        spans, replacements, words = [], [], []
        for block_index, block in enumerate(raw['blocks']):
            if block['type'] != 0:
                continue
            for line_index, line in enumerate(block['lines']):
                line_chars = []
                for raw_span in line['spans']:
                    sid = len(spans)
                    characters = []
                    for j, char in enumerate(raw_span['chars']):
                        key = raw_span['font'], _origin(char['origin'])
                        options = missing.get(key, [])
                        # Dict extraction can expose the CID as a Unicode value
                        # while texttrace correctly says the Unicode is missing.
                        match = options[0] if (len(options) == origins[key] == 1 and len(char['c']) == 1
                                               and ord(char['c']) == options[0]['glyph_id']) else None
                        value = match['candidate_text'] if match else None if key in missing_origins else char['c']
                        item = {'source_span_id': sid, 'source_char': j, 'native_text': char['c'],
                                'candidate_text': value, 'bbox': _bbox(char['bbox'], matrix)}
                        characters.append(item)
                        line_chars.append(item)
                        if match:
                            replacements.append({**item, **match, 'source_origin': list(_origin(char['origin'])),
                                                 'origin': list(_origin(fitz.Point(char['origin']) * matrix))})
                    spans.append({'id': sid, 'block': block_index, 'line': line_index,
                                  'font': raw_span['font'], 'bbox': _bbox(raw_span['bbox'], matrix),
                                  'native_text': ''.join(c['native_text'] for c in characters),
                                  'candidate_text': ''.join(c['candidate_text'] if c['candidate_text'] is not None else '\ufffd' for c in characters),
                                  'characters': characters})
                groups = []
                current = []
                for char in line_chars:
                    if char['candidate_text'] is not None and char['candidate_text'].isspace():
                        if current:
                            groups.append(current)
                            current = []
                    else:
                        current.append(char)
                if current:
                    groups.append(current)
                for word_number, chars in enumerate(groups):
                    boxes = [c['bbox'] for c in chars]
                    words.append({'id': len(words), 'block': block_index, 'line': line_index, 'word': word_number,
                                  'text': ''.join(c['candidate_text'] if c['candidate_text'] is not None else '\ufffd' for c in chars),
                                  'source_characters': [[c['source_span_id'], c['source_char']] for c in chars],
                                  'bbox': [min(b[0] for b in boxes), min(b[1] for b in boxes),
                                           max(b[2] for b in boxes), max(b[3] for b in boxes)],
                                  'has_unresolved_characters': any(c['candidate_text'] is None for c in chars)})
        # JSON keys must be stable before and after transport.
        for font in fonts:
            font['glyph_to_codepoints'] = {str(k): v for k, v in font['glyph_to_codepoints'].items()}
        blocks = []
        for block in sorted({s['block'] for s in spans}):
            members = [s for s in spans if s['block'] == block]
            lines = {}
            for span in members:
                lines.setdefault(span['line'], []).append(span)
            blocks.append({'id': f'p{number}:font_block{block}', 'source_block': block,
                           'source_span_ids': [s['id'] for s in members],
                           'font_word_ids': [w['id'] for w in words if w['block'] == block],
                           'text': '\n'.join(''.join(s['candidate_text'] for s in line) for line in lines.values()),
                           'bbox': [min(s['bbox'][0] for s in members), min(s['bbox'][1] for s in members),
                                    max(s['bbox'][2] for s in members), max(s['bbox'][3] for s in members)],
                           'paragraph_boundaries_verified': False, 'reading_order_verified': False,
                           'recognition_verified': False})
        mapped = sum(c['candidate_text'] is not None for c in replacements)
        return {'schema_version': 'embedded-font-mapping-page-1', 'source': source, 'page': number,
                'width': page.rect.width, 'height': page.rect.height, 'rotation': page.rotation,
                'coordinate_space': 'display', 'fonts': fonts, 'source_font_resources': resources,
                'spans': spans, 'words': words, 'blocks': blocks,
                'replacements': replacements, 'bound_characters': len(replacements), 'mapped_characters': mapped,
                'missing_unicode_trace_characters': trace_missing,
                'unbound_missing_trace_characters': trace_missing - len(replacements),
                'unresolved_characters': trace_missing - mapped,
                'source_span_namespace': 'font_mapping_native_rawdict',
                'engine': {'pymupdf': fitz.VersionBind, 'implementation_sha256': _sha(Path(__file__).read_bytes())},
                'recognition_verified': False, 'reading_order_verified': False}
