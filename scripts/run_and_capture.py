#!/usr/bin/env python3
"""真实执行命令，并把真实输出渲染成实验报告可用的终端截图。

同时落盘一份同名 .log.txt（含命令、工作目录、时间、退出码、原始输出），
用于证明截图来自真实运行；报告排版脚本会校验这份日志是否存在。

用法：
    python run_and_capture.py --cmd "python main.py" --out shots/fig5-1.png --title "运行 main.py"
    python run_and_capture.py --cmd "sqlite3 shop.db < q.sql" --out shots/q1.png --style light
    python run_and_capture.py --cmd "npm run dev" --out shots/dev.png --timeout 25 --no-prompt
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ASCII_FONT_CANDIDATES = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/SFNSMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/lucon.ttf",
]
CJK_FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
]

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\r")


def pick_font(cands, size):
    for p in cands:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def is_cjk(ch):
    o = ord(ch)
    return (
        0x2E80 <= o <= 0x9FFF
        or 0xF900 <= o <= 0xFAFF
        or 0xFF00 <= o <= 0xFF60
        or 0x3000 <= o <= 0x303F
    )


def split_runs(line):
    runs, buf, cur = [], "", None
    for ch in line:
        c = is_cjk(ch)
        if cur is None or c == cur:
            buf += ch
            cur = c
        else:
            runs.append((buf, cur))
            buf, cur = ch, c
    if buf:
        runs.append((buf, cur))
    return runs


def measure(text, fa, fc):
    w = 0.0
    for run, cjk in split_runs(text):
        w += (fc if cjk else fa).getlength(run)
    return w


def draw_runs(draw, x, y, text, fa, fc, color):
    for run, cjk in split_runs(text):
        f = fc if cjk else fa
        draw.text((x, y), run, font=f, fill=color)
        x += f.getlength(run)
    return x


def wrap_line(text, fa, fc, max_w, indent="  "):
    if measure(text, fa, fc) <= max_w:
        return [text]
    out, cur = [], ""
    for ch in text:
        if measure(cur + ch, fa, fc) > max_w:
            out.append(cur)
            cur = indent + ch
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def render_terminal(lines, out_path, title="", style="dark", show_prompt=True, font_size=26):
    theme = {
        "dark": {
            "bg": (29, 31, 33),
            "bar": (50, 50, 51),
            "border": (60, 64, 68),
            "text": (216, 222, 233),
            "dim": (140, 148, 158),
            "ok": (126, 214, 143),
            "err": (242, 119, 122),
            "dots": [(255, 95, 86), (255, 189, 46), (39, 201, 63)],
        },
        "light": {
            "bg": (253, 253, 253),
            "bar": (232, 232, 232),
            "border": (208, 215, 222),
            "text": (36, 41, 46),
            "dim": (110, 118, 129),
            "ok": (22, 138, 63),
            "err": (197, 40, 61),
            "dots": [(255, 95, 86), (255, 189, 46), (39, 201, 63)],
        },
    }[style]

    fa = pick_font(ASCII_FONT_CANDIDATES, font_size)
    fc = pick_font(CJK_FONT_CANDIDATES, font_size)
    fb = pick_font(ASCII_FONT_CANDIDATES, int(font_size * 0.86))
    fcb = pick_font(CJK_FONT_CANDIDATES, int(font_size * 0.86))

    pad_x, pad_top, pad_bottom = 30, 22, 26
    line_h = int(font_size * 1.68)
    bar_h = 54
    max_text_w = 1420
    char_w = fa.getlength("M")

    wrapped = []
    for ln in lines:
        wrapped.extend(wrap_line(ln, fa, fc, max_text_w))

    text_w = max([measure(ln, fa, fc) for ln in wrapped] + [520])
    width = int(min(max_text_w + pad_x * 2, max(980, text_w + pad_x * 2)))
    height = bar_h + pad_top + line_h * max(1, len(wrapped)) + pad_bottom

    img = Image.new("RGB", (width, height), theme["bg"])
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, width, bar_h], fill=theme["bar"])
    d.line([0, bar_h, width, bar_h], fill=theme["border"], width=2)
    for i, c in enumerate(theme["dots"]):
        cx = 26 + i * 26
        d.ellipse([cx - 8, bar_h // 2 - 8, cx + 8, bar_h // 2 + 8], fill=c)
    if title:
        tw = fcb.getlength(title)
        d.text(((width - tw) / 2, (bar_h - int(font_size * 0.86) * 1.25) / 2), title, font=fcb, fill=theme["dim"])

    y = bar_h + pad_top
    for ln in wrapped:
        if ln.startswith("__ERR__"):
            color, ln = theme["err"], ln[7:]
        elif ln.startswith("__DIM__"):
            color, ln = theme["dim"], ln[7:]
        else:
            color = theme["text"]
        x = pad_x
        if show_prompt and ln.startswith("$ "):
            d.text((x, y), "$", font=fa, fill=theme["ok"])
            x += char_w * 1.6
            ln = ln[2:]
        draw_runs(d, x, y, ln, fa, fc, color)
        y += line_h

    img.save(out_path, dpi=(200, 200))
    return out_path


def main():
    ap = argparse.ArgumentParser(description="执行命令并生成真实终端截图")
    ap.add_argument("--cmd", required=True)
    ap.add_argument("--out", required=True, help="PNG 输出路径")
    ap.add_argument("--title", default="", help="窗口标题，建议写实验步骤名")
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--style", choices=["dark", "light"], default="dark")
    ap.add_argument("--max-lines", type=int, default=40, help="超出后截断，避免截图过长")
    ap.add_argument("--no-prompt", action="store_true", help="不显示 $ 命令提示行")
    ap.add_argument("--keep-color-code", action="store_true", help="输出中保留非零退出码标记")
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["TERM"] = "xterm-256color"

    started = dt.datetime.now()
    try:
        p = subprocess.run(
            args.cmd,
            shell=True,
            cwd=args.cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=args.timeout,
            text=True,
            errors="replace",
        )
        raw, rc, timed_out = p.stdout or "", p.returncode, False
    except subprocess.TimeoutExpired as e:
        raw = (e.stdout or "") if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")
        rc, timed_out = 124, True

    raw = ANSI_RE.sub("", raw).replace("\t", "    ")
    body = [ln.rstrip() for ln in raw.splitlines()]
    if len(body) > args.max_lines:
        body = body[: args.max_lines] + [f"__DIM__...（输出过长，已截断，完整内容见日志）"]

    lines = []
    if not args.no_prompt:
        lines.append("$ " + args.cmd)
    lines.extend(body)
    if rc != 0:
        lines.append(f"__ERR__[进程退出码 {rc}{'，执行超时' if timed_out else ''}]")

    log_path = os.path.splitext(out)[0] + ".log.txt"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"time: {started.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"cwd: {args.cwd}\n")
        f.write(f"cmd: {args.cmd}\n")
        f.write(f"exit: {rc}\n")
        f.write("-" * 60 + "\n")
        f.write(raw)

    render_terminal(lines, out, args.title, args.style, not args.no_prompt)

    print(f"截图：{out}")
    print(f"日志：{log_path}")
    print(f"退出码：{rc}")
    if rc != 0:
        print("注意：命令未成功执行，不要用这张截图充当成功结果。")
    sys.exit(0 if rc == 0 else 1)


if __name__ == "__main__":
    main()
