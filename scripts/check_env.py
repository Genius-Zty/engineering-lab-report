#!/usr/bin/env python3
"""实验环境体检与补全。

用法示例：
    python check_env.py --preset python-web
    python check_env.py --need "python>=3.9" --need cmd:mysql --need py:flask --install
    python check_env.py --preset db-sqlite --md-out env_table.md --json env_report.json

状态含义：
    OK      已满足
    FIXED   缺失，已自动补全并复检通过
    MISS    缺失，需人工处理（系统级安装命令已给出）
    WARN    存在但不满足版本/端口等附加要求
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys

PRESETS = {
    "python": ["python>=3.9", "cmd:pip"],
    "python-web": ["python>=3.9", "cmd:pip", "py:flask", "py:requests"],
    "python-data": ["python>=3.9", "py:numpy", "py:pandas", "py:matplotlib"],
    "java-web": ["cmd:java>=8", "cmd:javac", "cmd:mvn"],
    "c-cpp": ["cmd:gcc", "cmd:g++", "cmd:make"],
    "web-frontend": ["cmd:node>=16", "cmd:npm"],
    "db-sqlite": ["cmd:sqlite3", "py:sqlite3"],
    "db-mysql": ["cmd:mysql", "port:3306"],
    "db-postgres": ["cmd:psql", "port:5432"],
    "db-mongo": ["cmd:mongod", "port:27017"],
    "git": ["cmd:git"],
    "docker": ["cmd:docker"],
}

# 系统级包名映射（macOS 走 brew，Linux 走 apt）
PKG_ALIAS = {
    "mysql": "mysql",
    "psql": "postgresql@16",
    "mongod": "mongodb-community",
    "redis-server": "redis",
    "mvn": "maven",
    "gradle": "gradle",
    "gcc": "gcc",
    "g++": "gcc",
    "make": "make",
    "node": "node",
    "python3": "python@3.12",
}

VERSION_ARGS = {
    "java": ["-version"],
    "javac": ["-version"],
    "python3": ["--version"],
    "python": ["--version"],
    "node": ["-v"],
    "npm": ["-v"],
    "docker": ["--version"],
    "sqlite3": ["--version"],
    "dotnet": ["--version"],
    "go": ["version"],
    "mysql": ["--version"],
    "psql": ["--version"],
}


def run(cmd, timeout=60, env=None):
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            env=env,
            text=True,
        )
        return p.returncode, (p.stdout or "").strip()
    except FileNotFoundError:
        return 127, "command not found"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def parse_ver(text):
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    if not m:
        return None
    return tuple(int(x) if x else 0 for x in m.groups())


def cmp_ver(a, b):
    return (a > b) - (a < b)


def split_need(need):
    """'cmd:mysql>=8.0' -> ('cmd', 'mysql', '>=8.0')"""
    if ":" in need:
        kind, rest = need.split(":", 1)
    else:
        kind, rest = "cmd", need
    op = ""
    for o in (">=", "<=", "==", ">"):
        if o in rest:
            rest, ver = rest.split(o, 1)
            op = o
            break
    else:
        ver = ""
    return kind.strip(), rest.strip(), (op + ver).strip()


def check_cmd(name, opspec):
    path = shutil.which(name)
    if not path:
        return "MISS", "", f"未找到可执行文件 {name}", path
    args = VERSION_ARGS.get(name, ["--version"])
    _, out = run([path] + args, timeout=25)
    ver = parse_ver(out)
    ver_s = ".".join(str(x) for x in ver) if ver else (out.splitlines()[0][:60] if out else "")
    if opspec and ver:
        op = re.match(r"(>=|<=|==|>)(\d+(?:\.\d+)*)", opspec)
        if op:
            need = tuple(int(x) for x in op.group(2).split("."))
            need = need + (0,) * (3 - len(need))
            if cmp_ver(ver, need) < 0 and op.group(1) in (">=", ">"):
                return "WARN", ver_s, f"版本低于要求 {opspec}", path
            if cmp_ver(ver, need) > 0 and op.group(1) in ("<=",):
                return "WARN", ver_s, f"版本高于要求 {opspec}", path
    return "OK", ver_s, path, path


def check_py(pkg, py):
    code = (
        "import importlib,sys;m=importlib.import_module(%r);"
        "print(getattr(m,'__version__','ok'))" % pkg
    )
    rc, out = run([py, "-c", code], timeout=40)
    if rc == 0:
        return "OK", out.splitlines()[-1][:40] if out else "ok", "已安装", None
    return "MISS", "", f"Python 模块 {pkg} 不可导入", None


def check_npm(pkg, cwd):
    rc, out = run(["node", "-e", f"require.resolve('{pkg}')"], timeout=30)
    if rc == 0:
        return "OK", "", "本地已安装", None
    rc2, out2 = run(["npm", "ls", "-g", "--depth=0", pkg], timeout=40)
    if pkg in out2:
        return "OK", "", "全局已安装", None
    return "MISS", "", f"Node 包 {pkg} 未安装", None


def check_port(port_s):
    try:
        port = int(port_s)
    except ValueError:
        return "WARN", "", f"端口写法不合法：{port_s}", None
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", port))
        return "OK", str(port), "端口已监听（服务在运行）", None
    except OSError:
        return "WARN", "", f"端口 {port} 未监听（服务可能未启动）", None
    finally:
        s.close()


def install_system(pkg, allow):
    name = PKG_ALIAS.get(pkg, pkg)
    if platform.system() == "Darwin":
        cmd = ["brew", "install", name]
    elif platform.system() == "Windows":
        hint = f"winget install {name}"
        if not allow:
            return False, hint, "Windows 不自动执行系统级安装，请手动运行 winget 或到官网下载安装包"
        if shutil.which("winget"):
            rc, out = run(["winget", "install", "--accept-source-agreements", name], timeout=900)
            return rc == 0, hint, out[-400:] if out else ""
        return False, hint, "未找到 winget，请手动安装或使用 choco"
    else:
        cmd = ["sudo", "apt-get", "install", "-y", name]
    text = " ".join(cmd)
    if not shutil.which(cmd[0]):
        return False, text, f"未找到 {cmd[0]}，请手动安装 {name}"
    if not allow:
        return False, text, "系统级安装未执行（需要用户确认后加 --allow-system）"
    rc, out = run(cmd, timeout=900)
    return rc == 0, text, out[-400:] if out else ""


def install_py(pkg, py):
    rc, out = run([py, "-m", "pip", "install", "--quiet", pkg], timeout=600)
    return rc == 0, f"{py} -m pip install {pkg}", out[-300:]


def install_npm(pkg, cwd):
    if not os.path.exists(os.path.join(cwd, "package.json")):
        run(["npm", "init", "-y"], timeout=120, env=os.environ.copy())
    rc, out = run(["npm", "install", "--no-audit", "--no-fund", pkg], timeout=600)
    return rc == 0, f"npm install {pkg}", out[-300:]


def main():
    ap = argparse.ArgumentParser(description="实验环境体检与补全")
    ap.add_argument("--preset", action="append", default=[], help=f"预设：{', '.join(PRESETS)}")
    ap.add_argument("--need", action="append", default=[], help="形如 cmd:mysql>=8.0 / py:flask / npm:express / port:8080 / file:app.py / env:JAVA_HOME")
    ap.add_argument("--install", action="store_true", help="自动补装项目级依赖（pip / npm）")
    ap.add_argument("--allow-system", action="store_true", help="允许执行系统级安装（brew / apt）")
    ap.add_argument("--python", default=sys.executable, help="用于检测与安装 Python 模块的解释器")
    ap.add_argument("--npm-dir", default=os.getcwd(), help="npm 安装目录")
    ap.add_argument("--json", default="", help="结果写入 JSON 文件")
    ap.add_argument("--md-out", default="", help="输出可直接贴进实验报告的 Markdown 环境表")
    args = ap.parse_args()

    needs = list(args.need)
    for p in args.preset:
        if p not in PRESETS:
            print(f"未知预设 {p}，可选：{', '.join(PRESETS)}")
            sys.exit(2)
        needs.extend(PRESETS[p])
    if not needs:
        needs = PRESETS["python-web"]
        print("未指定检测项，默认按 python-web 预设执行。\n")

    rows = []
    for need in needs:
        kind, name, opspec = split_need(need)
        action = ""
        if kind == "cmd":
            status, version, detail, _ = check_cmd(name, opspec)
            if status == "MISS" and args.install:
                ok, cmdtext, out = install_system(name, args.allow_system)
                action = cmdtext
                if ok:
                    status, version, detail, _ = check_cmd(name, opspec)
                    status = "FIXED" if status == "OK" else status
                else:
                    detail = out
        elif kind in ("py", "pip"):
            status, version, detail, _ = check_py(name, args.python)
            if status == "MISS" and args.install:
                ok, cmdtext, out = install_py(name, args.python)
                action = cmdtext
                if ok:
                    status, version, detail, _ = check_py(name, args.python)
                    status = "FIXED" if status == "OK" else status
                else:
                    detail = out
        elif kind == "npm":
            status, version, detail, _ = check_npm(name, args.npm_dir)
            if status == "MISS" and args.install:
                ok, cmdtext, out = install_npm(name, args.npm_dir)
                action = cmdtext
                if ok:
                    status, version, detail, _ = check_npm(name, args.npm_dir)
                    status = "FIXED" if status == "OK" else status
                else:
                    detail = out
        elif kind == "port":
            status, version, detail, _ = check_port(name)
        elif kind == "file":
            p = os.path.abspath(os.path.expanduser(name))
            status = "OK" if os.path.exists(p) else "MISS"
            version = ""
            detail = p if status == "OK" else f"文件不存在：{p}"
        elif kind == "env":
            v = os.environ.get(name)
            status = "OK" if v else "MISS"
            version = v or ""
            detail = "已设置" if v else f"环境变量 {name} 未设置"
        else:
            status, version, detail = "WARN", "", f"未知检测类型：{kind}"
            action = ""

        rows.append(
            {
                "need": need,
                "kind": kind,
                "name": name,
                "status": status,
                "version": version,
                "detail": detail,
                "action": action,
            }
        )

    icon = {"OK": "[OK]   ", "FIXED": "[FIXED]", "MISS": "[MISS] ", "WARN": "[WARN] "}
    print("实验环境体检结果")
    print("-" * 78)
    for r in rows:
        print(f"{icon.get(r['status'], '[????] ')} {r['name']:<14} {r['version']:<18} {r['detail'][:34]}")
        if r["action"]:
            print(f"           └─ 处理：{r['action'][:70]}")
    print("-" * 78)

    bad = [r for r in rows if r["status"] in ("MISS",)]
    warn = [r for r in rows if r["status"] == "WARN"]
    print(f"合计 {len(rows)} 项：通过 {sum(1 for r in rows if r['status'] in ('OK','FIXED'))}，缺失 {len(bad)}，待确认 {len(warn)}")
    if bad:
        print("\n未解决项（必须处理后再开始实验，或改用等价技术路线并在报告中写明）：")
        for r in bad:
            print(f"  - {r['name']}：{r['detail']}")
    if warn:
        print("\n提示项：")
        for r in warn:
            print(f"  - {r['name']}：{r['detail']}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"platform": platform.platform(), "rows": rows}, f, ensure_ascii=False, indent=2)
        print(f"\nJSON 已写入 {args.json}")

    if args.md_out:
        lines = ["| 环境项 | 版本 / 状态 | 说明 |", "| --- | --- | --- |"]
        for r in rows:
            lines.append(f"| {r['name']} | {r['version'] or '—'} | {r['detail'][:60]} |")
        with open(args.md_out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"环境表已写入 {args.md_out}（可直接作为报告「实验环境」表格）")

    sys.exit(2 if bad else 0)


if __name__ == "__main__":
    main()
