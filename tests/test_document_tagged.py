import copy

import fitz

from src.audit_reports.document_corpus import Filing
from src.audit_reports.document_evidence import capture_source_evidence, page_evidence, verify_evidence_records
from src.audit_reports.document_tagged import verify_tagged_structure


def test_actualtext_outside_the_page_is_preserved_alongside_literal_glyphs():
    with fitz.open() as pdf:
        page = pdf.new_page(width=320, height=400)
        page.insert_text((280, 80), "X")
        pixel = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 2, 2), False)
        pixel.clear_with(255)
        page.insert_image(fitz.Rect(40, 150, 240, 160), stream=pixel.tobytes("png"))
        xref = page.get_contents()[-1]
        replacement = "Source footnote contains 1,000 and is not an approved zero. Complete ending."
        content = (b"/Span << /ActualText (" + replacement.encode() + b") >> BDC\n"
                   + pdf.xref_stream(xref) + b"\nEMC")
        pdf.update_stream(xref, content)
        assert "Complete ending." not in page.get_text()
        source = page_evidence(page)
        assert replacement in "".join(s["text"] for s in source["spans"])
        assert source["text_clip"] == "unbounded"
        assert source["actualtext_changes_word_view"]
        assert [w["text"] for w in source["literal_glyph_words"]] == ["X"]
        assert source["text_geometry_verified"] is False


def tagged_pdf(path):
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((40, 80), "Label")
        page.insert_text((240, 80), "1,000")
        refs = [pdf.get_new_xref() for _ in range(7)]
        root, document, table, row, first, second, parent_tree = refs
        objects = [
            f"<< /Type /StructTreeRoot /K {document} 0 R /ParentTree {parent_tree} 0 R /ParentTreeNextKey 1 >>",
            f"<< /Type /StructElem /S /Document /P {root} 0 R /K {table} 0 R >>",
            f"<< /Type /StructElem /S /Table /P {document} 0 R /K {row} 0 R >>",
            f"<< /Type /StructElem /S /TR /P {table} 0 R /K [{first} 0 R {second} 0 R] >>",
            f"<< /Type /StructElem /S /TD /P {row} 0 R /Pg {page.xref} 0 R /K 0 >>",
            f"<< /Type /StructElem /S /TD /P {row} 0 R /Pg {page.xref} 0 R /K 1 >>",
            f"<< /Nums [0 [{first} 0 R {second} 0 R]] >>",
        ]
        for ref, obj in zip(refs, objects, strict=True):
            pdf.update_object(ref, obj)
        pdf.xref_set_key(pdf.pdf_catalog(), "StructTreeRoot", f"{root} 0 R")
        pdf.xref_set_key(pdf.pdf_catalog(), "MarkInfo", "<< /Marked true >>")
        pdf.xref_set_key(page.xref, "StructParents", "0")
        for mcid, xref in enumerate(page.get_contents()):
            pdf.update_stream(xref, f"/P << /MCID {mcid} >> BDC\n".encode()
                              + pdf.xref_stream(xref) + b"\nEMC")
        pdf.save(path)


def test_pdf_declared_table_relationships_are_preserved_as_source_metadata(tmp_path):
    path = tmp_path / "TEST_2026Q1_consolidated.pdf"
    tagged_pdf(path)
    evidence = capture_source_evidence(path, Filing("TEST", "2026Q1", "consolidated"))
    source = evidence[1]
    tagged = source["native_structure"]
    assert tagged["role_counts"]["Table"] == 1
    assert tagged["role_counts"]["TR"] == 1
    assert tagged["role_counts"]["TD"] == 2
    assert [s["text"] for n in tagged["nodes"] if n["kind"] == "text"
            for line in n["lines"] for s in line["spans"]] == ["Label", "1,000"]
    assert all(s["source_span_id"] is not None for n in tagged["nodes"] if n["kind"] == "text"
               for line in n["lines"] for s in line["spans"])
    assert tagged["geometry_verified"] is False
    assert verify_tagged_structure(source) == []
    assert verify_evidence_records(evidence)["valid"]

    damaged = copy.deepcopy(source)
    text_node = next(n for n in damaged["native_structure"]["nodes"] if n["kind"] == "text")
    text_node["lines"][0]["spans"][0]["source_span_id"] = 1
    assert "native_source_span_mismatch" in verify_tagged_structure(damaged)
    damaged = copy.deepcopy(source)
    table = next(n for n in damaged["native_structure"]["nodes"] if n.get("role") == "Table")
    table["children"] = []
    assert "native_child_inventory_mismatch" in verify_tagged_structure(damaged)
