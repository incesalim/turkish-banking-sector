"""Candidate positions for replacement text explicitly paired with PDF images.

Some PDFs emit ActualText at the preceding text cursor. A unique image/text pair
inside one declared Span provides a separate position candidate, without moving
or deleting the source span. No proportional word boxes are invented for it.
"""
from __future__ import annotations

from collections import Counter


def positioned_text(source: dict) -> dict:
    literal = source.get('literal_glyph_words')
    use_literal = source.get('actualtext_changes_word_view') is True and literal is not None
    words = literal if use_literal else source['words']
    pieces = [{'id': i, 'text': w['text'], 'bbox': list(w['bbox']),
               'method': 'literal_glyph_word' if use_literal else 'source_word',
               'source_word_id': w['id'],
               'source_word_view': 'literal_glyph_words' if use_literal else 'words'}
              for i, w in enumerate(words)]
    issues, candidates = [], []
    spans = {s['id']: s for s in source['spans']}
    images = {im['id']: im for im in source['images']}
    nodes = {n['id']: n for n in (source.get('native_structure') or {}).get('nodes', [])}
    if use_literal:
        for parent in nodes.values():
            if parent.get('role') != 'Span':
                continue
            children = [nodes[i] for i in parent.get('children', [])]
            image_nodes = [n for n in children if n['kind'] == 'image']
            text_nodes = [n for n in children if n['kind'] == 'text']
            if not image_nodes or not text_nodes:
                continue
            if len(children) != 2 or len(image_nodes) != 1 or len(text_nodes) != 1:
                issues.append({'kind': 'ambiguous_native_pair', 'native_parent_id': parent['id']})
                continue
            image, text = image_nodes[0], text_nodes[0]
            links = [s for line in text['lines'] for s in line['spans'] if s['text'].strip()]
            ids = image.get('source_image_candidates', [])
            if len(links) != 1 or len(ids) != 1 or links[0].get('source_span_id') not in spans or ids[0] not in images:
                issues.append({'kind': 'ambiguous_source_link', 'native_parent_id': parent['id']})
                continue
            span, observed_image = spans[links[0]['source_span_id']], images[ids[0]]
            outer, bbox = observed_image['bbox'], image.get('bbox')
            # Native structure may describe the clipped painted image region;
            # the image inventory retains its full placement rectangle.
            if (span['text'] != links[0]['text'] or bbox is None
                    or bbox[0] < outer[0] - .01 or bbox[1] < outer[1] - .01
                    or bbox[2] > outer[2] + .01 or bbox[3] > outer[3] + .01
                    or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]):
                issues.append({'kind': 'native_pair_source_mismatch', 'native_parent_id': parent['id']})
                continue
            candidates.append({'text': span['text'], 'bbox': list(bbox), 'method': 'native_image_replacement_pair',
                               'source_span_id': span['id'], 'source_image_id': observed_image['id'],
                               'native_parent_id': parent['id'], 'native_image_id': image['id'],
                               'native_text_id': text['id'], 'association_verified': False})
        span_uses = Counter(c['source_span_id'] for c in candidates)
        image_uses = Counter(c['source_image_id'] for c in candidates)
        for candidate in candidates:
            if span_uses[candidate['source_span_id']] != 1 or image_uses[candidate['source_image_id']] != 1:
                issues.append({'kind': 'nonunique_source_pair', 'native_parent_id': candidate['native_parent_id']})
                continue
            pieces.append({'id': len(pieces), **candidate})
    paired = {p['source_span_id'] for p in pieces if p['method'] == 'native_image_replacement_pair'}
    return {'method': 'native_image_replacement_layout', 'page': source['page'],
            'coordinate_space': 'display', 'pieces': pieces, 'issues': issues,
            'paired_source_span_ids': sorted(paired),
            'replacement_pair_count': len(paired),
            'source_text_preserved_separately': True, 'coverage_verified': False,
            'reading_order_verified': False, 'semantic_verification': 'not_performed'}


def verify_positioned_text(view: dict, source: dict) -> dict:
    """Recompute source links; this tests retention/association rules, not visibility."""
    valid = view == positioned_text(source)
    return {'valid': valid, 'errors': [] if valid else ['positioned_text_source_mismatch'],
            'geometry_verified': False, 'semantic_verification': 'not_performed'}
