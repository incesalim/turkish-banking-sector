import fitz

from src.audit_reports.document_evidence import page_evidence
from src.audit_reports.document_rule_tables import underline_candidates
from src.audit_reports.document_structure import _ruled_candidates


def test_one_row_table_from_cell_underlines_preserves_zero_dash_and_repeated_values():
    with fitz.open() as doc:
        page = doc.new_page()
        page.draw_rect((40, 100, 450, 100.5), fill=(0, 0, 0))
        columns = (40, 190, 280, 365, 450)
        for left, right in zip(columns, columns[1:]):
            page.draw_rect((left, 120, right, 120.5), fill=(0, 0, 0))
        for x, value in ((45, "Shareholder"), (200, "Paid"), (290, "Unpaid"), (375, "Other")):
            page.insert_text((x, 95), value)
        for x, value in ((45, "Example Bank"), (200, "1,000"), (290, "0"), (375, "-")):
            page.insert_text((x, 116), value)
        source = page_evidence(page)
        tables = underline_candidates(source, [])
        assert len(tables) == 1
        table = tables[0]
        assert [[cell["text"] for cell in row["cells"]] for row in table["rows"]] == [
            ["Shareholder", "Paid", "Unpaid", "Other"], ["Example Bank", "1,000", "0", "-"]]
        assert table["header_association_verified"] is False
        assert len(table["source_drawing_ids"]) == 5
        assert underline_candidates(source, [table]) == []


def test_separate_underlined_phrases_do_not_become_a_table():
    with fitz.open() as doc:
        page = doc.new_page()
        page.draw_line((40, 100), (450, 100))
        for left, right in ((40, 140), (190, 270), (350, 450)):
            page.draw_line((left, 120), (right, 120))
            page.insert_text((left, 115), "100")
        assert underline_candidates(page_evidence(page), []) == []


def test_logo_paths_cannot_pull_the_table_border_through_its_words():
    with fitz.open() as doc:
        page = doc.new_page()
        # A dense ornamental outline above the table, similar to outlined logo
        # lettering. Its x coordinates must not join the grid's snap clusters.
        points = [fitz.Point(x, 30 if i % 2 else 60) for i, x in enumerate(range(40, 102, 2))]
        page.draw_polyline(points)
        for x in (40, 250, 480):
            page.draw_rect((x, 140, x + .5, 240), fill=(0, 0, 0))
        for y in (140, 170, 240):
            page.draw_rect((40, y, 480, y + .5), fill=(0, 0, 0))
        for x, y, value in ((44, 160, "Pension Fund Obligations"), (254, 160, "Audit response"),
                            (44, 190, "The full opening words must remain."), (254, 190, "Independent review.")):
            page.insert_text((x, y), value)
        tables = _ruled_candidates(page, page_evidence(page))
        assert len(tables) == 1
        assert tables[0]["rows"][0]["cells"][0]["text"] == "Pension Fund Obligations"
        assert tables[0]["rows"][1]["cells"][0]["text"].startswith("The full opening")
        assert all(c["source_text_matches"] for r in tables[0]["rows"] for c in r["cells"])
