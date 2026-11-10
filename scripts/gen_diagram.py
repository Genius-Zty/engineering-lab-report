#!/usr/bin/env python3
"""绘制实验报告用的规范图表（PNG，2 倍分辨率，适合 A4 打印）。

支持类型：
    flow   流程图 / 程序流程      纵向节点链，支持判断节点
    arch   系统架构图 / 分层图
    er     E-R 图（实体 + 字段 + 关系 + 基数）
    class  类图（类名 / 属性 / 方法）
    bar    柱状图（可分组）
    line   折线图

用法：
    python gen_diagram.py --spec figs/er.json --out figs/er.png

spec 示例见 references/diagrams.md，最短形式：
    {"type": "flow", "title": "登录流程", "nodes": [{"text": "开始", "kind": "start"}, {"text": "输入账号密码"}]}
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

CJK_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
]
SANS_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
]

THEME = {
    "process": ((238, 243, 251), (74, 111, 165)),
    "start": ((231, 244, 236), (63, 125, 88)),
    "end": ((231, 244, 236), (63, 125, 88)),
    "decision": ((255, 244, 229), (183, 121, 31)),
    "db": ((239, 234, 247), (107, 78, 155)),
    "io": ((236, 246, 248), (45, 122, 138)),
    "layer": ((248, 250, 252), (203, 213, 225)),
    "item": ((255, 255, 255), (148, 163, 184)),
    "text": (31, 41, 55),
    "sub": (71, 85, 105),
    "line": (68, 84, 106),
    "white": (255, 255, 255),
    "note": (100, 116, 139),
}


def is_cjk(ch):
    o = ord(ch)
    return 0x2E80 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF or 0xFF00 <= o <= 0xFF60 or 0x3000 <= o <= 0x303F


class MonoFonts:
    def __init__(self, size, bold=False):
        self.size = size
        self.bold = bold
        cjk_index = 2 if bold else 0
        self.cjk = self._load(CJK_CANDIDATES, size, index=cjk_index)
        self.latin = self._load(SANS_CANDIDATES, size, index=1 if bold else 0)

    @staticmethod
    def _load(cands, size, index=0):
        for p in cands:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size, index=index)
                except OSError:
                    try:
                        return ImageFont.truetype(p, size, index=0)
                    except OSError:
                        continue
        return ImageFont.load_default()

    def width(self, s):
        w = 0.0
        for ch in s:
            w += (self.cjk if is_cjk(ch) else self.latin).getlength(ch)
        return w

    def draw(self, d, x, y, s, fill):
        for ch in s:
            f = self.cjk if is_cjk(ch) else self.latin
            d.text((x, y), ch, font=f, fill=fill)
            x += f.getlength(ch)
        return x

    def wrap(self, s, max_w):
        lines, cur = [], ""
        for ch in s:
            if ch == "\n":
                lines.append(cur)
                cur = ""
                continue
            if self.width(cur + ch) > max_w and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines or [""]


class Canvas:
    def __init__(self, width, height, scale=2, bg=(255, 255, 255)):
        self.scale = scale
        self.W, self.H = width, height
        self.img = Image.new("RGB", (width, height), bg)
        self.d = ImageDraw.Draw(self.img)
        self.fonts = {}

    def font(self, size, bold=False):
        key = (size, bold)
        if key not in self.fonts:
            self.fonts[key] = MonoFonts(size, bold)
        return self.fonts[key]

    def text(self, x, y, s, size=30, fill=THEME["text"], anchor="la", bold=False):
        f = self.font(size, bold)
        if anchor[0] == "m":
            x -= f.width(s) / 2
        elif anchor[0] == "r":
            x -= f.width(s)
        if anchor[1] == "m":
            y -= size * 0.72
        elif anchor[1] == "b":
            y -= size * 1.4
        f.draw(self.d, x, y, s, fill)
        return y

    def text_center(self, cx, cy, s, size=30, fill=THEME["text"], bold=False):
        self.text(cx, cy - size * 0.02, s, size, fill, anchor="mm", bold=bold)

    def box(self, x0, y0, x1, y1, kind="process", radius=14, width=3, fill=None):
        f, o = THEME.get(kind, THEME["process"])
        self.d.rounded_rectangle(
            [x0, y0, x1, y1], radius=radius, fill=fill or f, outline=o, width=width
        )

    def diamond(self, cx, cy, w, h, kind="decision"):
        f, o = THEME["decision"]
        pts = [(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)]
        self.d.polygon(pts, fill=f, outline=o, width=3)

    def cylinder(self, x0, y0, x1, y1, kind="db"):
        f, o = THEME["db"]
        eh = 18
        self.d.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=f, outline=o, width=3)
        self.d.arc([x0, y0, x1, y0 + eh * 2], 0, 180, fill=o, width=3)

    def arrow(self, pts, color=THEME["line"], width=3, head=14, label=None, label_size=24,
              label_pos=0.5, label_dx=0, label_dy=0, dashed=False):
        if dashed:
            for i in range(len(pts) - 1):
                (x0, y0), (x1, y1) = pts[i], pts[i + 1]
                self.d.line([x0, y0, x1, y1], fill=color, width=width)
        else:
            self.d.line(pts, fill=color, width=width, joint="curve")
        (x0, y0), (x1, y1) = pts[-2], pts[-1]
        ang = math.atan2(y1 - y0, x1 - x0)
        p1 = (x1, y1)
        p2 = (x1 - head * math.cos(ang - 0.42), y1 - head * math.sin(ang - 0.42))
        p3 = (x1 - head * math.cos(ang + 0.42), y1 - head * math.sin(ang + 0.42))
        self.d.polygon([p1, p2, p3], fill=color)
        if label:
            seg = (pts[0], pts[1])
            lx = seg[0][0] + (seg[1][0] - seg[0][0]) * label_pos + label_dx
            ly = seg[0][1] + (seg[1][1] - seg[0][1]) * label_pos + label_dy
            f = self.font(label_size)
            tw = f.width(label)
            self.d.rectangle([lx - tw / 2 - 6, ly - label_size * 0.9, lx + tw / 2 + 6, ly + label_size * 0.5],
                             fill=(255, 255, 255))
            self.text(lx, ly, label, label_size, THEME["sub"], anchor="mm")

    def save(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        img = self.img
        bg = Image.new("RGB", img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg).convert("L").point(lambda v: 255 if v > 10 else 0)
        bbox = diff.getbbox()
        if bbox:
            pad = 26
            box = (
                max(0, bbox[0] - pad),
                max(0, bbox[1] - pad),
                min(img.size[0], bbox[2] + pad),
                min(img.size[1], bbox[3] + pad),
            )
            img = img.crop(box)
        img.save(path, dpi=(220, 220))
        return path


def title_block(c, text, size=40):
    if not text:
        return 0
    c.text(c.W / 2, 34, text, size, THEME["text"], anchor="ma", bold=True)
    return 60


def draw_flow(c, spec):
    nodes = spec.get("nodes", [])
    fs = spec.get("font_size", 30)
    pad_x, gap = 70, 58
    body_w = 600
    y = 30 + title_block(c, spec.get("title", ""))
    positions = []
    for n in nodes:
        text = str(n.get("text", ""))
        kind = n.get("kind", "process")
        f = c.font(fs)
        max_w = 300 if kind == "decision" else body_w - 40
        lines = f.wrap(text, max_w)
        h = max(76, len(lines) * fs * 1.5 + 36)
        w = body_w if kind != "decision" else max(body_w * 0.82, f.width(text) + 180)
        positions.append((y, h, w, lines, kind))
        y += h + gap

    total_h = y - gap + 34
    c.H = int(total_h)
    c.img = Image.new("RGB", (c.W, c.H), (255, 255, 255))
    c.d = ImageDraw.Draw(c.img)
    y0 = 30 + title_block(c, spec.get("title", ""))
    cx = c.W / 2
    centers = []
    for i, (_, h, w, lines, kind) in enumerate(positions):
        cy = y0 + h / 2
        if kind == "decision":
            c.diamond(cx, cy, w, h)
        elif kind == "db":
            c.cylinder(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        else:
            c.box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, kind)
        start_y = cy - (len(lines) - 1) * fs * 0.75
        for j, ln in enumerate(lines):
            c.text_center(cx, start_y + j * fs * 1.5, ln, fs, THEME["text"], bold=(kind in ("start", "end")))
        centers.append((cy, h, w))
        y0 += h + gap

    for i in range(len(centers) - 1):
        cy, h, w = centers[i]
        ncy, nh, nw = centers[i + 1]
        label = nodes[i].get("to_next", "")
        c.arrow([(cx, cy + h / 2), (cx, ncy - nh / 2)], label=label or None, label_dx=34, label_dy=0)

    return c


def draw_arch(c, spec):
    layers = spec.get("layers", [])
    fs = spec.get("font_size", 28)
    margin = 60
    band_w = spec.get("band_width", 1180)
    x0 = (c.W - band_w) / 2 if c.W else margin
    y = 30 + title_block(c, spec.get("title", ""))
    plans = []
    for layer in layers:
        items = layer.get("items", [])
        f = c.font(fs)
        h_items = 76
        band_h = 56 + h_items + 34
        plans.append((layer, band_h, items))
        y += band_h + 34
    c.H = int(y + 10)
    c.img = Image.new("RGB", (c.W, c.H), (255, 255, 255))
    c.d = ImageDraw.Draw(c.img)
    y = 30 + title_block(c, spec.get("title", ""))
    for layer, band_h, items in plans:
        label = layer.get("name", "")
        kind = layer.get("kind", "layer")
        c.box(x0, y, x0 + band_w, y + band_h, kind, radius=16, width=3)
        c.text(x0 + 24, y + 16, label, fs - 2, THEME["sub"], bold=True)
        n = max(1, len(items))
        inner_w = (band_w - 48 - (n - 1) * 22) / n
        for i, it in enumerate(items):
            ix = x0 + 24 + i * (inner_w + 22)
            iy = y + 52
            c.box(ix, iy, ix + inner_w, iy + 76, "item", radius=10, width=2)
            txt = it if isinstance(it, str) else it.get("text", "")
            sub = "" if isinstance(it, str) else it.get("sub", "")
            if sub:
                c.text_center(ix + inner_w / 2, iy + 30, txt, fs - 2, THEME["text"], bold=True)
                c.text_center(ix + inner_w / 2, iy + 60, sub, fs - 8, THEME["sub"])
            else:
                c.text_center(ix + inner_w / 2, iy + 38, txt, fs - 2, THEME["text"])
        y += band_h + 34
    return c


def _grid(n, cols, box_w, box_h, gap_x, gap_y, top):
    rows = math.ceil(n / cols)
    total_w = cols * box_w + (cols - 1) * gap_x
    total_h = rows * box_h + (rows - 1) * gap_y
    return total_w, total_h


def _relation_points(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    acx, acy = ax + aw / 2, ay + ah / 2
    bcx, bcy = bx + bw / 2, by + bh / 2
    if abs(bcx - acx) > abs(bcy - acy):
        if bcx > acx:
            p0, p1 = (ax + aw, acy), (bx, bcy)
        else:
            p0, p1 = (ax, acy), (bx + bw, bcy)
        if abs(p0[1] - p1[1]) < 1:
            return [p0, p1]
        mx = (p0[0] + p1[0]) / 2
        return [p0, (mx, p0[1]), (mx, p1[1]), p1]
    if bcy > acy:
        p0, p1 = (acx, ay + ah), (bcx, by)
    else:
        p0, p1 = (acx, ay), (bcx, by + bh)
    if abs(p0[0] - p1[0]) < 1:
        return [p0, p1]
    my = (p0[1] + p1[1]) / 2
    return [p0, (p0[0], my), (p1[0], my), p1]


def draw_relation(c, a, b, rel, fs, head=16):
    pts = _relation_points(a, b)
    c.arrow(pts, head=head)

    segs = list(zip(pts[:-1], pts[1:]))
    (x0, y0), (x1, y1) = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    vertical = abs(y1 - y0) > abs(x1 - x0)
    label = rel.get("label", "")
    if label:
        if vertical:
            c.text(mx + 14, my, label, fs - 4, THEME["sub"], anchor="lm")
        else:
            c.text(mx, my - 12, label, fs - 4, THEME["sub"], anchor="mb")

    def place_card(txt, pt, box):
        if not txt:
            return
        bx, by, bw, bh = box
        ccx, ccy = bx + bw / 2, by + bh / 2
        dx, dy = pt[0] - ccx, pt[1] - ccy
        n = math.hypot(dx, dy) or 1
        ux, uy = dx / n, dy / n
        px, py = -uy, ux
        if abs(py) >= abs(px):
            if py > 0:
                px, py = -px, -py
        elif px < 0:
            px, py = -px, -py
        c.text(pt[0] + ux * 6 + px * 24, pt[1] + uy * 6 + py * 24, txt, fs - 4, THEME["note"], anchor="mm")

    place_card(rel.get("card_from", ""), pts[0], a)
    place_card(rel.get("card_to", ""), pts[-1], b)


def draw_er(c, spec):
    ents = spec.get("entities", [])
    rels = spec.get("relations", [])
    fs = spec.get("font_size", 26)
    box_w = spec.get("box_width", 430)
    head_h = 74
    row_h = 46
    gap_x, gap_y = 210, 200
    cols = spec.get("columns", 2 if len(ents) > 2 else 1)

    heights = [head_h + len(e.get("fields", [])) * row_h + 20 for e in ents]
    rows = math.ceil(len(ents) / cols)
    row_hs = []
    for r in range(rows):
        hs = heights[r * cols:(r + 1) * cols]
        row_hs.append(max(hs) if hs else head_h)

    total_w = cols * box_w + (cols - 1) * gap_x + 160
    total_h = sum(row_hs) + (rows - 1) * gap_y + 130 + (70 if spec.get("title") else 0)
    c.H = int(max(total_h, 500))
    c.img = Image.new("RGB", (c.W, c.H), (255, 255, 255))
    c.d = ImageDraw.Draw(c.img)
    top = 30 + title_block(c, spec.get("title", ""))
    left = (c.W - (cols * box_w + (cols - 1) * gap_x)) / 2

    pos = {}
    y = top
    idx = 0
    for r in range(rows):
        x = left
        for col in range(cols):
            if idx >= len(ents):
                break
            e = ents[idx]
            h = heights[idx]
            c.box(x, y, x + box_w, y + h, "process", radius=0, width=3)
            c.d.rectangle([x + 2, y + 2, x + box_w - 2, y + head_h * 0.62], fill=THEME["process"][0])
            c.d.rectangle([x, y, x + box_w, y + h], outline=THEME["process"][1], width=3)
            c.d.line([x, y + head_h * 0.72, x + box_w, y + head_h * 0.72], fill=THEME["process"][1], width=2)
            c.text_center(x + box_w / 2, y + head_h * 0.36, e.get("name", ""), fs + 2, THEME["text"], bold=True)
            fy = y + head_h * 0.72 + 12
            for fld in e.get("fields", []):
                name = fld.get("name", "")
                typ = fld.get("type", "")
                mark = "PK" if fld.get("pk") else ("FK" if fld.get("fk") else "")
                tx = x + 22
                if mark:
                    c.d.rounded_rectangle([tx, fy + 6, tx + 40, fy + 32], radius=6,
                                          fill=(219, 234, 254) if mark == "PK" else (254, 226, 226))
                    c.text_center(tx + 20, fy + 19, mark, fs - 10, THEME["sub"], bold=True)
                    tx += 50
                c.text(tx, fy + 4, name, fs, THEME["text"])
                if typ:
                    c.text(x + box_w - 18, fy + 4, typ, fs - 4, THEME["note"], anchor="ra")
                fy += row_h
            pos[e.get("name", "")] = (x, y, box_w, h)
            idx += 1
            x += box_w + gap_x
        y += row_hs[r] + gap_y

    for rel in rels:
        a, b = pos.get(rel.get("from")), pos.get(rel.get("to"))
        if not a or not b:
            continue
        draw_relation(c, a, b, rel, fs)
    return c


def draw_class(c, spec):
    classes = spec.get("classes", [])
    rels = spec.get("relations", [])
    fs = spec.get("font_size", 25)
    box_w = spec.get("box_width", 440)
    gap_x, gap_y = 220, 180
    cols = spec.get("columns", 2 if len(classes) > 2 else 1)
    head_h, pad = 62, 14

    heights = []
    for cl in classes:
        attrs = cl.get("attributes", [])
        meths = cl.get("methods", [])
        heights.append(head_h + pad + len(attrs) * (fs + 12) + pad + 18 + len(meths) * (fs + 12) + pad)

    rows = math.ceil(len(classes) / cols)
    row_hs = [max(heights[r * cols:(r + 1) * cols]) if heights[r * cols:(r + 1) * cols] else head_h for r in range(rows)]
    total_w = cols * box_w + (cols - 1) * gap_x + 140
    total_h = sum(row_hs) + (rows - 1) * gap_y + 120 + (70 if spec.get("title") else 0)
    c.H = int(max(total_h, 460))
    c.img = Image.new("RGB", (c.W, c.H), (255, 255, 255))
    c.d = ImageDraw.Draw(c.img)
    top = 30 + title_block(c, spec.get("title", ""))
    left = (c.W - (cols * box_w + (cols - 1) * gap_x)) / 2

    pos, y, idx = {}, top, 0
    for r in range(rows):
        x = left
        for _ in range(cols):
            if idx >= len(classes):
                break
            cl = classes[idx]
            h = row_hs[r]
            attrs = cl.get("attributes", [])
            meths = cl.get("methods", [])
            c.box(x, y, x + box_w, y + h, "process", radius=0, width=3)
            c.d.rectangle([x + 2, y + 2, x + box_w - 2, y + head_h], fill=THEME["process"][0])
            c.d.rectangle([x, y, x + box_w, y + h], outline=THEME["process"][1], width=3)
            c.d.line([x, y + head_h, x + box_w, y + head_h], fill=THEME["process"][1], width=2)
            c.text_center(x + box_w / 2, y + head_h / 2, cl.get("name", ""), fs + 3, THEME["text"], bold=True)
            cy = y + head_h + pad
            for a in attrs:
                c.text(x + 18, cy, a, fs, THEME["text"])
                cy += fs + 12
            cy += 6
            c.d.line([x, cy, x + box_w, cy], fill=(203, 213, 225), width=2)
            cy += 10
            for m in meths:
                c.text(x + 18, cy, m, fs, THEME["sub"])
                cy += fs + 12
            pos[cl.get("name", "")] = (x, y, box_w, h)
            idx += 1
            x += box_w + gap_x
        y += row_hs[r] + gap_y

    for rel in rels:
        a, b = pos.get(rel.get("from")), pos.get(rel.get("to"))
        if not a or not b:
            continue
        draw_relation(c, a, b, rel, fs, head=15)
    return c


def draw_chart(spec, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    avail = {f.name for f in font_manager.fontManager.ttflist}
    for cand in ("Hiragino Sans GB", "Songti SC", "Arial Unicode MS", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC"):
        if cand in avail:
            plt.rcParams["font.family"] = cand
            break
    plt.rcParams["axes.unicode_minus"] = False

    ctype = spec.get("type")
    labels = [str(x) for x in spec.get("labels", [])]
    series = spec.get("series", [])
    fig, ax = plt.subplots(figsize=spec.get("figsize", [8.2, 4.6]), dpi=220)
    colors = ["#4A6FA5", "#B7791F", "#3F7D58", "#6B4E9B", "#2D7A8A"]

    if ctype == "bar":
        n = len(series)
        w = 0.72 / max(1, n)
        for i, s in enumerate(series):
            xs = [j + (i - (n - 1) / 2) * w for j in range(len(labels))]
            bars = ax.bar(xs, s.get("data", []), width=w * 0.92, label=s.get("name", f"系列{i+1}"),
                          color=colors[i % len(colors)], edgecolor="white", linewidth=0.6)
            if spec.get("value_labels", True):
                for b in bars:
                    ax.annotate(f"{b.get_height():g}", (b.get_x() + b.get_width() / 2, b.get_height()),
                                textcoords="offset points", xytext=(0, 3), ha="center", fontsize=9, color="#475569")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels)
    elif ctype == "line":
        for i, s in enumerate(series):
            ax.plot(labels, s.get("data", []), marker="o", markersize=6, linewidth=2.2,
                    color=colors[i % len(colors)], label=s.get("name", f"系列{i+1}"))
        ax.grid(True, axis="y", linestyle="--", alpha=0.35)
    else:
        raise SystemExit(f"未知图表类型：{ctype}")

    ax.set_title(spec.get("title", ""), fontsize=15, pad=14)
    ax.set_xlabel(spec.get("xlabel", ""), fontsize=11)
    ax.set_ylabel(spec.get("ylabel", ""), fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=10)
    if len(series) > 1 or spec.get("legend"):
        ax.legend(frameon=False, fontsize=10, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    fig.savefig(out, dpi=220, bbox_inches="tight", facecolor="white")
    return out


def main():
    ap = argparse.ArgumentParser(description="绘制实验报告图表")
    ap.add_argument("--spec", required=True, help="图表 JSON 描述文件")
    ap.add_argument("--out", required=True, help="输出 PNG 路径")
    ap.add_argument("--width", type=int, default=1500, help="画布宽度（px）")
    args = ap.parse_args()

    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)

    t = spec.get("type")
    if t in ("bar", "line", "chart"):
        if t == "chart":
            spec["type"] = spec.get("chart_type", "bar")
        path = draw_chart(spec, args.out)
        print(f"图表：{path}")
        return

    width = spec.get("width", args.width)
    c = Canvas(width, 2000)
    if t == "flow":
        draw_flow(c, spec)
    elif t == "arch":
        draw_arch(c, spec)
    elif t == "er":
        draw_er(c, spec)
    elif t == "class":
        draw_class(c, spec)
    else:
        raise SystemExit(f"未知类型：{t}（可选 flow / arch / er / class / bar / line）")

    path = c.save(args.out)
    print(f"图表：{path}  尺寸：{c.img.size[0]}x{c.img.size[1]}")


if __name__ == "__main__":
    main()
