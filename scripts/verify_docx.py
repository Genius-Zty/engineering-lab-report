#!/usr/bin/env python3
"""把生成的 docx 转成 PDF 并逐页出图，用来目视校验版面。

三条通道，自动降级：
    1. LibreOffice（soffice）—— 全自动，无需授权，最稳
    2. Pages（macOS）—— 需要系统设置里授予「自动化」权限，否则报 -10004
    3. --open —— 直接在本机 Word / Pages 里打开给用户看，不做转换

只用于自检。最终交付物永远是 .docx，不是 PDF，也不是 .pages。

用法：
    $PY scripts/verify_docx.py --docx 实验报告.docx
    $PY scripts/verify_docx.py --docx 实验报告.docx --open
    $PY scripts/verify_docx.py --docx 实验报告.docx --pages --dpi 120
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile

SOFFICE_CANDIDATES = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/local/bin/soffice",
    "/opt/homebrew/bin/soffice",
    "C:/Program Files/LibreOffice/program/soffice.exe",
    "C:/Program Files (x86)/LibreOffice/program/soffice.exe",
]
OFFICE_APPS = [
    "/Applications/Microsoft Word.app",
    "/Applications/Pages.app",
    "/Applications/WPS Office.app",
]


def run(cmd, timeout=240):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip()
    except FileNotFoundError:
        return 127, "command not found"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def convert_soffice(docx, outdir):
    exe = shutil.which("soffice") or next((p for p in SOFFICE_CANDIDATES if os.path.exists(p)), None)
    if not exe:
        return None, "未安装 LibreOffice"
    rc, out = run([exe, "--headless", "--norestore", "--convert-to", "pdf", "--outdir", outdir, docx])
    pdf = os.path.join(outdir, os.path.splitext(os.path.basename(docx))[0] + ".pdf")
    if os.path.exists(pdf):
        return pdf, exe
    return None, out[-300:]


def convert_pages(docx, outdir):
    exe = next((p for p in OFFICE_APPS if p.endswith("Pages.app") and os.path.exists(p)), None)
    if not exe:
        return None, "未安装 Pages"
    pdf = os.path.join(outdir, os.path.splitext(os.path.basename(docx))[0] + ".pdf")
    script = f'''tell application "Pages"
activate
set d to open POSIX file "{docx}"
delay 3
export d to POSIX file "{pdf}" as PDF
close d saving no
end tell'''
    rc, out = run(["osascript", "-e", script], timeout=180)
    if os.path.exists(pdf):
        return pdf, "Pages"
    if "-10004" in out or "权限" in out:
        return None, (
            "Pages 已安装，但 macOS 未授予「自动化」权限（-10004）。\n"
            "  授权方式：系统设置 → 隐私与安全性 → 自动化 → 勾选当前应用对 Pages 的控制。\n"
            "  或者直接手动打开：open -a Pages <文件>，在 Pages 里「文件 → 导出到 → PDF」。"
        )
    return None, out[-300:]


def render_pages(pdf, outdir, dpi=110):
    try:
        import fitz
    except ImportError:
        return [], "缺少 PyMuPDF（pip install pymupdf），无法逐页出图"
    paths = []
    doc = fitz.open(pdf)
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(dpi=dpi)
        path = os.path.join(outdir, f"page-{i:02d}.png")
        pix.save(path)
        paths.append(path)
    w_cm = doc[0].rect.width / 72 * 2.54 if doc.page_count else 0
    h_cm = doc[0].rect.height / 72 * 2.54 if doc.page_count else 0
    return paths, (doc.page_count, round(w_cm, 1), round(h_cm, 1))


def open_doc(docx):
    if platform.system() == "Windows" and hasattr(os, "startfile"):
        os.startfile(docx)
        return "系统默认程序"
    if platform.system() == "Darwin":
        for app in OFFICE_APPS:
            if app.endswith("Microsoft Word.app") and os.path.exists(app):
                run(["open", "-a", app, docx], timeout=30)
                return "Microsoft Word"
        if os.path.exists("/Applications/Pages.app"):
            run(["open", "-a", "/Applications/Pages.app", docx], timeout=30)
            return "Pages"
    rc, _ = run(["open", docx] if platform.system() == "Darwin" else ["xdg-open", docx], timeout=30)
    return "系统默认应用"


def main():
    ap = argparse.ArgumentParser(description="docx 版面校验：转 PDF 并逐页出图")
    ap.add_argument("--docx", required=True)
    ap.add_argument("--outdir", default="", help="PDF 与页面图输出目录，默认 ./_preview")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--pages", action="store_true", help="强制走 Pages 通道")
    ap.add_argument("--open", action="store_true", help="直接在本机办公软件里打开，不转换")
    args = ap.parse_args()

    docx = os.path.abspath(args.docx)
    if not os.path.exists(docx):
        print(f"文件不存在：{docx}")
        sys.exit(2)

    if args.open:
        app = open_doc(docx)
        print(f"已用 {app} 打开：{docx}")
        print("检查要点：封面是否居中、目录是否提示更新域、表格是否三线、图片是否清晰、代码是否溢出。")
        return

    outdir = os.path.abspath(args.outdir or "_preview")
    os.makedirs(outdir, exist_ok=True)

    pdf, info = (None, None)
    if args.pages:
        pdf, info = convert_pages(docx, outdir)
    else:
        pdf, info = convert_soffice(docx, outdir)
        if not pdf:
            print(f"LibreOffice 通道不可用：{info}")
            print("改用 Pages 通道……")
            pdf, info = convert_pages(docx, outdir)

    if not pdf:
        print(f"\n无法自动转换：{info}")
        print("\n可用的替代方案：")
        print("  1) 现在就用 Pages/Word 打开看一眼：python verify_docx.py --docx <文件> --open")
        print("  2) 安装 LibreOffice 后可全自动校验：brew install --cask libreoffice")
        print("  3) 不装任何软件也可以交付，docx 本身不需要 Word 才能生成")
        sys.exit(1)

    paths, meta = render_pages(pdf, outdir, args.dpi)
    print(f"PDF：{pdf}")
    if isinstance(meta, tuple):
        pages, w, h = meta
        print(f"页数：{pages}，页面：{w}×{h} cm" + ("（A4 正确）" if abs(w - 21) < 0.4 else "（不是 A4，检查页面设置）"))
    for p in paths:
        print("页面图：", p)


if __name__ == "__main__":
    main()
