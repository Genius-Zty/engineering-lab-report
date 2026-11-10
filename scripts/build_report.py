#!/usr/bin/env python3
"""把结构化内容渲染成符合中文高校规范的实验报告 .docx。

设计约定（已按工科实验报告惯例固化，不建议逐次改动）：
    纸张 A4，上下 2.54cm，左 3.0cm（装订），右 2.6cm
    正文 宋体 / Times New Roman 小四（12pt），1.5 倍行距，首行缩进 2 字符
    一级标题 黑体 四号，二级标题 黑体 小四
    代码 Consolas 9pt + 浅灰底 + 细边框，单倍行距
    图注在图下、表注在表上，宋体五号居中，自动编号「图X-Y / 表X-Y」
    表格为三线表，表头加粗

用法：
    python build_report.py --spec content.json --out 实验报告.docx
    python build_report.py --spec content.json --out out.docx --no-toc
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

CN_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
          "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十"]
SKIP_NUMBER = ("参考文献", "附录", "致谢", "谢辞")
CODE_BG = "F6F8FA"
CODE_BORDER = "D0D7DE"
TABLE_LINE = "000000"


def set_run_font(run, ea="宋体", latin="Times New Roman", size=12, bold=False, color=None, italic=False):
    run.font.name = latin
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)
    rfonts.set(qn("w:eastAsia"), ea)
    rfonts.set(qn("w:cs"), latin)


def add_text(paragraph, text, ea="宋体", latin="Times New Roman", size=12, bold=False, color=None):
    run = paragraph.add_run(text)
    set_run_font(run, ea, latin, size, bold, color)
    t = run._element.find(qn("w:t"))
    if t is not None:
        t.set(qn("xml:space"), "preserve")
    return run


def add_rich(paragraph, text, size=12, ea="宋体", color=None):
    for i, seg in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        if not seg:
            continue
        add_text(paragraph, seg, ea=ea, size=size, bold=(i % 2 == 1), color=color)


PPR_AFTER_PBDR = (
    "w:shd", "w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap", "w:overflowPunct",
    "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN", "w:bidi", "w:adjustRightInd",
    "w:snapToGrid", "w:spacing", "w:ind", "w:contextualSpacing", "w:mirrorIndents",
    "w:suppressOverlap", "w:jc", "w:textDirection", "w:textAlignment", "w:textboxTightWrap",
    "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange",
)
TCPR_AFTER_BORDERS = (
    "w:shd", "w:noWrap", "w:tcMar", "w:textDirection", "w:tcFitText", "w:vAlign", "w:hideMark",
    "w:headers", "w:cellIns", "w:cellDel", "w:cellMerge", "w:tcPrChange",
)
SETTINGS_AFTER_UPDATE = (
    "w:hdrShapeDefaults", "w:footnotePr", "w:endnotePr", "w:compat", "w:docVars", "w:rsids",
    "w:mathPr", "w:themeFontLang", "w:clrSchemeMapping", "w:shapeDefaults", "w:decimalSymbol",
    "w:listSeparator", "w:smartTagType",
)


def shade_paragraph(p, fill):
    ppr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    ppr.insert_element_before(shd, *PPR_AFTER_PBDR[1:])


def border_paragraph(p, color=CODE_BORDER, sz=4, space=4):
    ppr = p._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), str(space))
        el.set(qn("w:color"), color)
        pbdr.append(el)
    ppr.insert_element_before(pbdr, *PPR_AFTER_PBDR)


def border_bottom(p, color="808080", sz=6, space=1):
    ppr = p._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    el = OxmlElement("w:bottom")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(sz))
    el.set(qn("w:space"), str(space))
    el.set(qn("w:color"), color)
    pbdr.append(el)
    ppr.insert_element_before(pbdr, *PPR_AFTER_PBDR)


def cell_borders(cell, **edges):
    tcpr = cell._tc.get_or_add_tcPr()
    borders = tcpr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tcpr.insert_element_before(borders, *TCPR_AFTER_BORDERS)
    for edge, spec in edges.items():
        el = OxmlElement(f"w:{edge}")
        if spec is None:
            el.set(qn("w:val"), "nil")
        else:
            sz, color = spec
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(sz))
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), color)
        borders.append(el)


def cell_shade(cell, fill):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcpr.insert_element_before(shd, *TCPR_AFTER_BORDERS[1:])


def add_field(paragraph, instr, placeholder="1", size=9, ea="宋体", latin="Times New Roman"):
    run = paragraph.add_run()
    set_run_font(run, ea, latin, size)
    r = run._r
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr_el = OxmlElement("w:instrText")
    instr_el.set(qn("xml:space"), "preserve")
    instr_el.text = f" {instr} "
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    t = OxmlElement("w:t")
    t.text = placeholder
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    for el in (fld_begin, instr_el, fld_sep, t, fld_end):
        r.append(el)


class ReportBuilder:
    def __init__(self, spec, base_dir):
        self.spec = spec
        self.base = base_dir
        self.meta = spec.get("meta", {})
        self.options = spec.get("options", {})
        self.fig_no = {}
        self.tab_no = {}
        self.code_no = {}
        self.warnings = []
        self.stats = {"figures": 0, "tables": 0, "codes": 0, "images": 0}

    # ---------- 基础构件 ----------
    def p(self, text="", size=12, ea="宋体", bold=False, align=None, indent=True,
          line=1.5, before=0, after=0, color=None):
        para = self.doc.add_paragraph()
        pf = para.paragraph_format
        pf.line_spacing = line
        pf.space_before = Pt(before)
        pf.space_after = Pt(after)
        if align is not None:
            pf.alignment = align
        if indent and text:
            pf.first_line_indent = Pt(size * 2)
        if text:
            add_rich(para, text, size=size, ea=ea, color=color)
        return para

    def heading(self, text, level=1):
        para = self.doc.add_paragraph()
        pf = para.paragraph_format
        if level == 1 and getattr(self, "pending_break", False):
            pf.page_break_before = True
            self.pending_break = False
        pf.keep_with_next = True
        pf.line_spacing = 1.5
        if level == 1:
            pf.space_before = Pt(14)
            pf.space_after = Pt(8)
            add_text(para, text, ea="黑体", latin="Times New Roman", size=14, bold=False)
        elif level == 2:
            pf.space_before = Pt(10)
            pf.space_after = Pt(4)
            add_text(para, text, ea="黑体", latin="Times New Roman", size=12, bold=False)
        else:
            pf.space_before = Pt(8)
            pf.space_after = Pt(2)
            add_text(para, text, ea="宋体", latin="Times New Roman", size=12, bold=True)
        return para

    def caption(self, text, above=False):
        para = self.doc.add_paragraph()
        pf = para.paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.line_spacing = 1.0
        pf.space_before = Pt(3 if above else 4)
        pf.space_after = Pt(6 if above else 12)
        if not above:
            pf.keep_with_previous = True
        add_text(para, text, size=10.5)
        return para

    def next_caption(self, kind, chapter, text):
        counter = self.fig_no if kind == "图" else self.tab_no
        counter[chapter] = counter.get(chapter, 0) + 1
        if re.match(r"^(图|表|代码)\s*\d", text or ""):
            return text
        body = text or ""
        prefix = f"{kind}{chapter}-{counter[chapter]}"
        return f"{prefix}　{body}" if body else prefix

    def image(self, path, caption="", width_cm=None, chapter=1):
        full = path if os.path.isabs(path) else os.path.join(self.base, path)
        if not os.path.exists(full):
            self.warnings.append(f"图片缺失：{path}")
            para = self.p(f"[缺少图片：{path}]", color=(192, 0, 0))
            return para
        with Image.open(full) as im:
            px_w, px_h = im.size
            dpi = im.info.get("dpi", (96, 96))[0] or 96
        nat_cm = px_w / float(dpi) * 2.54
        w = width_cm if width_cm else min(14.5, max(7.5, nat_cm))
        h = w * px_h / px_w
        if h > 18.0:
            w = w * 18.0 / h
        para = self.doc.add_paragraph()
        pf = para.paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.space_before = Pt(6)
        pf.space_after = Pt(2)
        pf.line_spacing = 1.0
        pf.keep_with_next = True
        para.add_run().add_picture(full, width=Cm(w))
        self.stats["images"] += 1
        self.fig_no[chapter] = self.fig_no.get(chapter, 0) + 1
        if re.match(r"^图\s*\d", caption or ""):
            cap = caption
        elif caption:
            cap = f"图{chapter}-{self.fig_no[chapter]}　{caption}"
        else:
            cap = f"图{chapter}-{self.fig_no[chapter]}"
        self.caption(cap, above=False)
        self.stats["figures"] += 1
        return para

    def code(self, text, caption="", chapter=1):
        text = (text or "").replace("\t", "    ").rstrip("\n")
        if caption:
            para = self.doc.add_paragraph()
            pf = para.paragraph_format
            pf.space_before = Pt(6)
            pf.space_after = Pt(2)
            pf.keep_with_next = True
            self.code_no[chapter] = self.code_no.get(chapter, 0) + 1
            cap = caption if re.match(r"^代码\s*\d", caption) else f"代码{chapter}-{self.code_no[chapter]}　{caption}"
            add_text(para, cap, size=10.5)
        para = self.doc.add_paragraph()
        pf = para.paragraph_format
        pf.line_spacing = 1.0
        pf.space_before = Pt(3)
        pf.space_after = Pt(10)
        pf.left_indent = Cm(0.5)
        pf.right_indent = Cm(0.2)
        pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
        shade_paragraph(para, CODE_BG)
        border_paragraph(para)
        lines = text.split("\n") if text else [""]
        for i, line in enumerate(lines):
            run = add_text(para, line, ea="宋体", latin="Consolas", size=9)
            if i < len(lines) - 1:
                run.add_break()
        self.stats["codes"] += 1
        return para

    def table(self, columns, rows, caption="", chapter=1, widths=None, first_col_left=False):
        ncol = len(columns)
        if caption:
            cap = caption if re.match(r"^表\s*\d", caption) else self.next_caption("表", chapter, caption)
            self.caption(cap, above=True)
        tbl = self.doc.add_table(rows=1 + len(rows), cols=ncol)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.autofit = widths is None
        tblpr = tbl._tbl.tblPr
        tblw = tblpr.find(qn("w:tblW"))
        if tblw is None:
            tblw = OxmlElement("w:tblW")
            tblpr.insert_element_before(
                tblw, "w:jc", "w:tblCellSpacing", "w:tblInd", "w:tblBorders", "w:shd",
                "w:tblLayout", "w:tblCellMar", "w:tblLook",
            )
        tblw.set(qn("w:type"), "pct")
        tblw.set(qn("w:w"), "5000")
        layout = tblpr.find(qn("w:tblLayout"))
        if layout is None:
            layout = OxmlElement("w:tblLayout")
            tblpr.insert_element_before(layout, "w:tblCellMar", "w:tblLook", "w:tblCaption")
        layout.set(qn("w:type"), "fixed" if widths else "autofit")

        data = [columns] + [list(r) for r in rows]
        for ri, row in enumerate(data):
            trpr = tbl.rows[ri]._tr.get_or_add_trPr()
            cant = OxmlElement("w:cantSplit")
            trpr.append(cant)
            if ri == 0:
                hdr = OxmlElement("w:tblHeader")
                trpr.append(hdr)
            for ci in range(ncol):
                cell = tbl.rows[ri].cells[ci]
                if widths:
                    cell.width = Cm(widths[ci])
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                para = cell.paragraphs[0]
                pf = para.paragraph_format
                pf.line_spacing = 1.15
                pf.space_before = Pt(2)
                pf.space_after = Pt(2)
                pf.alignment = (
                    WD_ALIGN_PARAGRAPH.LEFT
                    if (first_col_left and ci == 0 and ri > 0)
                    else WD_ALIGN_PARAGRAPH.CENTER
                )
                val = row[ci] if ci < len(row) else ""
                add_text(para, str(val), ea="宋体", size=10.5, bold=(ri == 0))
                if ri == 0:
                    cell_shade(cell, "F2F2F2")
                cell_borders(
                    cell,
                    top=(12, TABLE_LINE) if ri == 0 else None,
                    bottom=(6, TABLE_LINE) if ri == 0 else ((12, TABLE_LINE) if ri == len(data) - 1 else None),
                    left=None,
                    right=None,
                )
        self.stats["tables"] += 1
        spacer = self.doc.add_paragraph()
        spacer.paragraph_format.space_after = Pt(6)
        spacer.paragraph_format.line_spacing = 1.0
        return tbl

    def flow_table(self, steps, caption="", chapter=1, box_width=None, shade="F2F6FC"):
        n = len(steps)
        ncol = n * 2 - 1
        arrow_w = 0.9 if n <= 4 else 0.7
        bw = box_width or min(4.5, (15.4 - (n - 1) * arrow_w) / n)
        tbl = self.doc.add_table(rows=1, cols=ncol)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tblpr = tbl._tbl.tblPr
        tblw = tblpr.find(qn("w:tblW"))
        if tblw is None:
            tblw = OxmlElement("w:tblW")
            tblpr.insert_element_before(
                tblw, "w:jc", "w:tblCellSpacing", "w:tblInd", "w:tblBorders", "w:shd",
                "w:tblLayout", "w:tblCellMar", "w:tblLook",
            )
        tblw.set(qn("w:type"), "pct")
        tblw.set(qn("w:w"), "5000")
        layout = tblpr.find(qn("w:tblLayout"))
        if layout is None:
            layout = OxmlElement("w:tblLayout")
            tblpr.insert_element_before(layout, "w:tblCellMar", "w:tblLook", "w:tblCaption")
        layout.set(qn("w:type"), "fixed")
        trpr = tbl.rows[0]._tr.get_or_add_trPr()
        trpr.append(OxmlElement("w:cantSplit"))
        for i, step in enumerate(steps):
            cell = tbl.rows[0].cells[i * 2]
            cell.width = Cm(bw)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            cell_shade(cell, shade)
            cell_borders(cell, top=(8, "8FA8C8"), bottom=(8, "8FA8C8"), left=(8, "8FA8C8"), right=(8, "8FA8C8"))
            para = cell.paragraphs[0]
            para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            para.paragraph_format.space_before = Pt(11)
            para.paragraph_format.space_after = Pt(11)
            para.paragraph_format.line_spacing = 1.0
            add_text(para, step, size=10.5)
            if i < n - 1:
                acell = tbl.rows[0].cells[i * 2 + 1]
                acell.width = Cm(arrow_w)
                acell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                cell_borders(acell, top=None, bottom=None, left=None, right=None)
                apara = acell.paragraphs[0]
                apara.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                apara.paragraph_format.space_before = Pt(0)
                apara.paragraph_format.space_after = Pt(0)
                add_text(apara, "→", size=10.5)
        if caption:
            self.fig_no[chapter] = self.fig_no.get(chapter, 0) + 1
            cap = caption if re.match(r"^图\s*\d", caption) else f"图{chapter}-{self.fig_no[chapter]}　{caption}"
            self.caption(cap, above=False)
            self.stats["figures"] += 1
        return tbl

    # ---------- 页面 ----------
    def setup_document(self):
        doc = Document()
        normal = doc.styles["Normal"]
        normal.font.name = "Times New Roman"
        normal.font.size = Pt(12)
        normal.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
        normal.paragraph_format.line_spacing = 1.5
        normal.paragraph_format.space_before = Pt(0)
        normal.paragraph_format.space_after = Pt(0)

        sec = doc.sections[0]
        sec.page_width = Cm(21.0)
        sec.page_height = Cm(29.7)
        sec.top_margin = Cm(2.54)
        sec.bottom_margin = Cm(2.54)
        sec.left_margin = Cm(3.0)
        sec.right_margin = Cm(2.6)
        sec.header_distance = Cm(1.5)
        sec.footer_distance = Cm(1.75)
        sec.different_first_page_header_footer = True

        settings = doc.settings.element
        update = doc.settings.element.find(qn("w:updateFields"))
        if update is None:
            update = OxmlElement("w:updateFields")
            doc.settings.element.insert_element_before(update, *SETTINGS_AFTER_UPDATE)
        update.set(qn("w:val"), "true")
        self.doc = doc

    def add_header_footer(self):
        sec = self.doc.sections[0]
        header_text = self.options.get("header_text", "")
        if header_text:
            hp = sec.header.paragraphs[0]
            hp.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_text(hp, header_text, size=9, color=(89, 89, 89))
            border_bottom(hp, color="BFBFBF", sz=6, space=2)

        fp = sec.footer.paragraphs[0]
        fp.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_text(fp, "第 ", size=9)
        add_field(fp, "PAGE", "1", size=9)
        add_text(fp, " 页　共 ", size=9)
        add_field(fp, "NUMPAGES", "1", size=9)
        add_text(fp, " 页", size=9)

    # ---------- 封面 / 目录 ----------
    def cover(self):
        meta = self.meta
        for _ in range(2):
            self.p("", size=12, indent=False)

        if meta.get("school"):
            self.p(meta["school"], size=16, ea="黑体", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=6)
        for _ in range(2):
            self.p("", size=12, indent=False)

        self.p("实　验　报　告", size=36, ea="黑体", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=10)

        if meta.get("title"):
            line = self.doc.add_paragraph()
            line.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            line.paragraph_format.space_before = Pt(6)
            line.paragraph_format.space_after = Pt(4)
            add_text(line, meta["title"], size=16, ea="黑体")

        for _ in range(3):
            self.p("", size=12, indent=False)

        fields = [
            ("课程名称", meta.get("course", "")),
            ("实验名称", meta.get("title", "")),
            ("学　　院", meta.get("college", "")),
            ("专业班级", meta.get("class_name", "")),
            ("学生姓名", meta.get("student", "")),
            ("学　　号", meta.get("student_id", "")),
            ("指导教师", meta.get("teacher", "")),
            ("实验日期", meta.get("date", "")),
        ]
        fields = [f for f in fields if f[1] or f[0] in ("课程名称", "实验名称", "学生姓名", "学　　号")]
        tbl = self.doc.add_table(rows=len(fields), cols=2)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, (label, value) in enumerate(fields):
            lc, vc = tbl.rows[i].cells
            lc.width = Cm(3.6)
            vc.width = Cm(8.4)
            lp = lc.paragraphs[0]
            lp.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            lp.paragraph_format.space_before = Pt(6)
            lp.paragraph_format.space_after = Pt(6)
            add_text(lp, f"{label}：", size=12)
            vp = vc.paragraphs[0]
            vp.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            vp.paragraph_format.space_before = Pt(6)
            vp.paragraph_format.space_after = Pt(6)
            add_text(vp, value or "", size=12)
            cell_borders(lc, top=None, bottom=None, left=None, right=None)
            cell_borders(vc, top=None, left=None, right=None, bottom=(6, "595959"))

        for _ in range(2):
            self.p("", size=12, indent=False)
        if meta.get("date"):
            self.p(meta["date"], size=12, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
        self.pending_break = True

    def toc(self):
        para = self.doc.add_paragraph()
        para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_before = Pt(6)
        para.paragraph_format.space_after = Pt(16)
        if getattr(self, "pending_break", False):
            para.paragraph_format.page_break_before = True
            self.pending_break = False
        add_text(para, "目　　录", size=16, ea="黑体")

        p = self.doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        add_field(p, r'TOC \o "1-2" \h \z \u', "（打开文档后按 F9 或右键“更新域”生成目录）", size=10.5)
        self.pending_break = True

    # ---------- 正文 ----------
    def body(self):
        numbering = self.options.get("numbering", True)
        idx = 0
        for sec in self.spec.get("sections", []):
            title = str(sec.get("heading") or sec.get("title") or "").strip()
            level = int(sec.get("level", 1))
            if level == 1:
                if not any(k in title for k in SKIP_NUMBER) and numbering:
                    if not re.match(r"^([一二三四五六七八九十]+、|\d+[\.、])", title):
                        title = f"{CN_NUM[idx] if idx < len(CN_NUM) else idx + 1}、{title}"
                idx += 1
            self.heading(title, level)
            chapter = idx if level == 1 else max(idx, 1)
            for block in sec.get("blocks", []):
                self.render_block(block, chapter)

    def render_block(self, block, chapter):
        if isinstance(block, str):
            self.p(block)
            return
        btype = block.get("type", "para")
        if btype == "para":
            self.p(block.get("text", ""), indent=block.get("indent", True))
        elif btype == "lead":
            self.p(block.get("text", ""), indent=False)
        elif btype == "list":
            ordered = block.get("ordered", False)
            for i, item in enumerate(block.get("items", []), 1):
                mark = f"{i}. " if ordered else "· "
                para = self.doc.add_paragraph()
                pf = para.paragraph_format
                pf.line_spacing = 1.5
                pf.left_indent = Pt(24)
                pf.first_line_indent = Pt(0)
                add_text(para, mark, size=12)
                add_rich(para, str(item))
        elif btype == "code":
            self.code(block.get("text", ""), block.get("caption", ""), chapter)
        elif btype == "image":
            self.image(block.get("path", ""), block.get("caption", ""), block.get("width_cm"), chapter)
        elif btype == "table":
            self.table(
                block.get("columns", []),
                block.get("rows", []),
                block.get("caption", ""),
                chapter,
                widths=block.get("widths"),
                first_col_left=block.get("first_col_left", False),
            )
        elif btype == "flow_table":
            self.flow_table(block.get("steps", []), block.get("caption", ""), chapter, block.get("box_width", 3.6))
        elif btype == "step":
            para = self.doc.add_paragraph()
            pf = para.paragraph_format
            pf.line_spacing = 1.5
            pf.space_before = Pt(4)
            pf.first_line_indent = Pt(24)
            if block.get("title"):
                add_text(para, block["title"] + ("　" if block.get("text") else ""), size=12, bold=True)
            add_rich(para, block.get("text", ""))
        elif btype == "note":
            para = self.doc.add_paragraph()
            pf = para.paragraph_format
            pf.line_spacing = 1.4
            pf.left_indent = Pt(24)
            add_text(para, block.get("text", ""), size=10.5, color=(89, 89, 89))
        elif btype == "pagebreak":
            self.doc.add_page_break()
        elif btype == "blank":
            self.p("", indent=False)
        else:
            self.warnings.append(f"未知内容块类型：{btype}")

    def build(self, out_path):
        self.setup_document()
        self.add_header_footer()
        if self.options.get("cover", True):
            self.cover()
        if self.options.get("toc", True):
            self.toc()
        self.body()
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        self.doc.save(out_path)
        return out_path


def main():
    ap = argparse.ArgumentParser(description="渲染实验报告 Word 文档")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-cover", action="store_true")
    ap.add_argument("--no-toc", action="store_true")
    args = ap.parse_args()

    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)
    if args.no_cover:
        spec.setdefault("options", {})["cover"] = False
    if args.no_toc:
        spec.setdefault("options", {})["toc"] = False

    spec.setdefault("meta", {})
    if not spec["meta"].get("date"):
        today = dt.date.today()
        spec["meta"]["date"] = f"{today.year} 年 {today.month} 月 {today.day} 日"

    base_dir = os.path.dirname(os.path.abspath(args.spec))
    builder = ReportBuilder(spec, base_dir)
    out = builder.build(args.out)

    print(f"已生成：{out}")
    print(
        f"统计：{len(spec.get('sections', []))} 个章节，"
        f"{builder.stats['codes']} 段代码，{builder.stats['images']} 张图片，"
        f"{builder.stats['tables']} 张表格"
    )
    if builder.warnings:
        print("警告：")
        for w in builder.warnings:
            print("  -", w)
        sys.exit(1)


if __name__ == "__main__":
    main()
