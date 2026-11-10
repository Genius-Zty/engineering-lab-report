#!/usr/bin/env python3
"""对真实运行中的网页/前端项目截图，供实验报告「实验结果」使用。

优先调用本机 Chrome / Edge / Chromium 的无头模式（零依赖）；
若已安装 playwright，也可自动降级使用。

用法：
    python shot_web.py --url http://127.0.0.1:5173 --out shots/page1.png --title "登录页"
    python shot_web.py --url http://127.0.0.1:8080/list --out shots/list.png --full-page
    python shot_web.py --url http://127.0.0.1:8080 --out shots/form.png --script "document.querySelector('#submit').click()"

截图前请确认服务已真实启动（用 run_and_capture.py 记录启动日志）。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "%LOCALAPPDATA%/Google/Chrome/Application/chrome.exe",
]


def find_chrome():
    for p in CHROME_CANDIDATES:
        p = os.path.expandvars(p)
        if os.path.exists(p):
            return p
    for name in ("google-chrome", "chromium", "chrome", "chrome.exe", "msedge", "msedge.exe"):
        p = shutil.which(name)
        if p:
            return p
    return None


def shot_with_chrome(chrome, url, out, width, height, full_page, wait_ms, script):
    profile = tempfile.mkdtemp(prefix="labreport-chrome-")
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--hide-scrollbars",
        "--force-device-scale-factor=2",
        f"--user-data-dir={profile}",
        f"--window-size={width},{height}",
        f"--virtual-time-budget={max(wait_ms, 1200)}",
        f"--screenshot={out}",
    ]
    if script:
        cmd.extend([f"--evaluate-on-new-document={script}"])
    cmd.append(url)
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
    ok = os.path.exists(out) and os.path.getsize(out) > 2000
    if ok and full_page:
        msg = "Chrome 通道只截取窗口范围；需要整页请加大 --height，或安装 playwright 后重试"
    else:
        msg = (p.stdout or "")[-500:]
    return ok, msg, "chrome-headless"


def shot_with_playwright(url, out, width, height, full_page, wait_ms, script):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "playwright 未安装（pip install playwright && playwright install chromium）", "none"
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": width, "height": height}, device_scale_factor=2)
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(wait_ms)
        if script:
            page.evaluate(script)
            page.wait_for_timeout(600)
        page.screenshot(path=out, full_page=full_page)
        b.close()
    return True, "", "playwright"


def main():
    ap = argparse.ArgumentParser(description="网页真实截图")
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="", help="仅用于提示，不写入图片")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=800)
    ap.add_argument("--full-page", action="store_true")
    ap.add_argument("--wait", type=int, default=1500, help="等待毫秒数（前端渲染/接口返回）")
    ap.add_argument("--script", default="", help="截图前在页面执行的 JS，例如展开菜单")
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    chrome = find_chrome()
    if chrome:
        ok, msg, engine = shot_with_chrome(
            chrome, args.url, out, args.width, args.height, args.full_page, args.wait, args.script
        )
    else:
        ok, msg, engine = shot_with_playwright(
            args.url, out, args.width, args.height, args.full_page, args.wait, args.script
        )

    if not ok and engine != "playwright":
        ok, msg2, engine = shot_with_playwright(
            args.url, out, args.width, args.height, args.full_page, args.wait, args.script
        )
        msg = f"{msg}\n{msg2}".strip()

    if not ok:
        print("截图失败：", msg[:600])
        print("排查：① 服务是否真的在运行 ② URL 与端口是否正确 ③ 是否需要登录态（缺少登录态时先模拟登录再截图）")
        sys.exit(1)

    log = os.path.splitext(out)[0] + ".log.txt"
    with open(log, "w", encoding="utf-8") as f:
        f.write(f"url: {args.url}\nengine: {engine}\nviewport: {args.width}x{args.height}\nfull_page: {args.full_page}\n")
    print(f"截图：{out}（{engine}）")
    print(f"日志：{log}")
    if args.full_page and engine == "chrome-headless":
        print("提示：Chrome 通道只截窗口范围；整页请加大 --height，或安装 playwright")


if __name__ == "__main__":
    main()
