#!/usr/bin/env python3
"""报告工具链自检：确认 python-docx / Pillow / matplotlib 与中文字体可用。

只需在开始一份报告前跑一次。缺依赖时会自动装到当前解释器所在环境
（推荐使用管理版虚拟环境 ~/.workbuddy/binaries/python/envs/default）。

用法：
    ~/.workbuddy/binaries/python/envs/default/bin/python setup_env.py
    python setup_env.py --no-install     # 只检查不安装
"""
from __future__ import annotations

import argparse
import importlib
import os
import platform
import subprocess
import sys

DEPS = [("docx", "python-docx"), ("PIL", "pillow"), ("matplotlib", "matplotlib")]
FONTS = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/consola.ttf",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-install", action="store_true")
    args = ap.parse_args()

    print(f"解释器：{sys.executable}")
    print(f"系统：{platform.platform()}")
    missing = []

    for mod, pkg in DEPS:
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", "")
            print(f"[OK]   {pkg:<12} {ver}")
        except ImportError:
            print(f"[MISS] {pkg}")
            missing.append(pkg)

    found_fonts = [p for p in FONTS if os.path.exists(p)]
    print(f"[{'OK' if found_fonts else 'WARN'}]   中文字体：{'、'.join(os.path.basename(p) for p in found_fonts) or '未找到，图表中文会变方块'}")

    if missing and not args.no_install:
        print(f"\n正在安装：{' '.join(missing)}")
        rc = subprocess.call([sys.executable, "-m", "pip", "install", "--quiet"] + missing)
        print("安装完成" if rc == 0 else "安装失败，请手动执行 pip install " + " ".join(missing))

    if missing and args.no_install:
        print("\n缺少依赖，请执行： pip install " + " ".join(missing))

    print("\n后续脚本请统一使用这个解释器：")
    print(sys.executable)
    sys.exit(0 if (not missing and found_fonts) else 1)


if __name__ == "__main__":
    main()
