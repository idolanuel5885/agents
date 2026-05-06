"""RTL-aware python-docx helpers for Hebrew documents."""
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HEBREW_FONT = "Arial"
FONT_BODY = 12
FONT_HEADING2 = 13
FONT_HEADING1 = 14
FONT_TITLE = 16


def make_rtl_doc() -> Document:
    doc = Document()
    section = doc.sections[0]
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    _set_doc_rtl_defaults(doc)
    return doc


def _set_doc_rtl_defaults(doc: Document):
    """Set document-level RTL defaults so Word opens in RTL mode."""
    # Add bidi to normal style
    normal = doc.styles["Normal"]
    pPr = normal.element.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    pPr.append(bidi)
    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), "right")
    pPr.append(jc)

    # Font
    rPr = normal.element.get_or_add_rPr()
    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), HEBREW_FONT)
    rFonts.set(qn("w:hAnsi"), HEBREW_FONT)
    rFonts.set(qn("w:cs"), HEBREW_FONT)
    rPr.append(rFonts)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(FONT_BODY * 2))
    rPr.append(sz)
    szCs = OxmlElement("w:szCs")
    szCs.set(qn("w:val"), str(FONT_BODY * 2))
    rPr.append(szCs)


def _apply_rtl_para(p, align_right: bool = True):
    pPr = p._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    pPr.append(bidi)
    if align_right:
        jc = OxmlElement("w:jc")
        jc.set(qn("w:val"), "right")
        pPr.append(jc)


def _apply_rtl_run(run, font_size: int, bold: bool):
    run.bold = bold
    rPr = run._r.get_or_add_rPr()

    rtl = OxmlElement("w:rtl")
    rPr.append(rtl)

    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), HEBREW_FONT)
    rFonts.set(qn("w:hAnsi"), HEBREW_FONT)
    rFonts.set(qn("w:cs"), HEBREW_FONT)
    rPr.append(rFonts)

    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(font_size * 2))
    rPr.append(sz)
    szCs = OxmlElement("w:szCs")
    szCs.set(qn("w:val"), str(font_size * 2))
    rPr.append(szCs)

    if bold:
        b = OxmlElement("w:b")
        rPr.append(b)
        bCs = OxmlElement("w:bCs")
        rPr.append(bCs)


def add_para(container, text: str, bold: bool = False,
             font_size: int = FONT_BODY,
             space_before: float = 0, space_after: float = 6) -> any:
    """Add an RTL paragraph to a document or cell."""
    p = container.add_paragraph()
    _apply_rtl_para(p)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    if text:
        run = p.add_run(text)
        _apply_rtl_run(run, font_size, bold)
    return p


def add_heading(doc, text: str, level: int = 1) -> any:
    size = FONT_HEADING1 if level == 1 else FONT_HEADING2
    return add_para(doc, text, bold=True, font_size=size, space_before=10, space_after=6)


def add_bullet(doc, text: str, font_size: int = FONT_BODY) -> any:
    p = doc.add_paragraph()
    _apply_rtl_para(p)
    p.paragraph_format.space_after = Pt(4)

    run_dot = p.add_run("• ")
    _apply_rtl_run(run_dot, font_size, False)

    run = p.add_run(text)
    _apply_rtl_run(run, font_size, False)
    return p


def set_cell(cell, text: str, bold: bool = False, font_size: int = FONT_BODY):
    """Write RTL text into a table cell (clears existing content)."""
    tc = cell._tc
    # Remove all existing paragraphs
    for p_el in tc.findall(qn("w:p")):
        tc.remove(p_el)

    p_el = OxmlElement("w:p")
    tc.append(p_el)

    pPr = OxmlElement("w:pPr")
    p_el.insert(0, pPr)
    bidi_el = OxmlElement("w:bidi")
    bidi_el.set(qn("w:val"), "1")
    pPr.append(bidi_el)
    jc_el = OxmlElement("w:jc")
    jc_el.set(qn("w:val"), "right")
    pPr.append(jc_el)

    r_el = OxmlElement("w:r")
    p_el.append(r_el)

    rPr = OxmlElement("w:rPr")
    r_el.insert(0, rPr)

    rtl_el = OxmlElement("w:rtl")
    rPr.append(rtl_el)

    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), HEBREW_FONT)
    rFonts.set(qn("w:hAnsi"), HEBREW_FONT)
    rFonts.set(qn("w:cs"), HEBREW_FONT)
    rPr.append(rFonts)

    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(font_size * 2))
    rPr.append(sz)
    szCs = OxmlElement("w:szCs")
    szCs.set(qn("w:val"), str(font_size * 2))
    rPr.append(szCs)

    if bold:
        b_el = OxmlElement("w:b")
        rPr.append(b_el)
        bCs = OxmlElement("w:bCs")
        rPr.append(bCs)

    t_el = OxmlElement("w:t")
    t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t_el.text = text
    r_el.append(t_el)


def make_table(doc, num_rows: int, num_cols: int,
               col_widths_cm: list = None):
    table = doc.add_table(rows=num_rows, cols=num_cols)
    table.style = "Table Grid"
    if col_widths_cm:
        for row in table.rows:
            for i, cell in enumerate(row.cells):
                if i < len(col_widths_cm):
                    cell.width = Cm(col_widths_cm[i])
    return table
