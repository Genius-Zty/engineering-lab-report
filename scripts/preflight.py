#!/usr/bin/env python3
"""交付前自检：在生成 Word 之前把不合规的内容拦住。

检查项：
    1. 章节完整性（目的 / 环境 / 内容 / 步骤 / 结果 / 总结）
    2. 代码块是否残留注释（按语言判断）
    3. 图片是否存在、是否够清晰
    4. 「实验结果」里的截图是否有真实执行日志或 captured 标记
    5. 实验总结字数与口吻（是否写成套话汇报）
    6. 占位符、重复编号、封面信息缺失

用法：
    python preflight.py --spec content.json
    python preflight.py --spec content.json --json check.json

退出码：0 通过（可能有警告）；1 存在必须修复的错误；2 文件读不到。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

REQUIRED_GROUPS = {
    "实验目的": ("目的", "目标", "要求"),
    "实验环境": ("环境", "设备", "工具"),
    "实验内容": ("内容", "原理", "方案", "设计", "需求"),
    "实验步骤": ("步骤", "过程", "实现", "操作"),
    "实验结果": ("结果", "运行", "测试", "验证"),
    "实验总结": ("总结", "体会", "心得", "反思"),
}

RESULT_KEYWORDS = ("结果", "运行", "测试", "验证")
SUMMARY_KEYWORDS = ("总结", "体会", "心得", "反思")

PLACEHOLDERS = ("TODO", "待补充", "待完善", "XXX", "xxx", "示例文本", "略", "???", "【填写")

CLICHE = (
    "综上所述",
    "通过本次实验",
    "使我受益匪浅",
    "深刻认识到",
    "为今后的学习打下了坚实的基础",
    "不仅巩固了",
    "进一步加深了对",
    "理论联系实际",
    "收获颇丰",
)

COMMENT_RULES = {
    "python": [("hash", r"#"), ("triple", r'(?s)^\s*("""|\'\'\')')],
    "py": [("hash", r"#"), ("triple", r'(?s)^\s*("""|\'\'\')')],
    "bash": [("hash", r"#")],
    "sh": [("hash", r"#")],
    "shell": [("hash", r"#")],
    "sql": [("dash", r"--"), ("block", r"/\*")],
    "mysql": [("dash", r"--"), ("block", r"/\*")],
    "java": [("slash", r"//"), ("block", r"/\*")],
    "javascript": [("slash", r"//"), ("block", r"/\*")],
    "js": [("slash", r"//"), ("block", r"/\*")],
    "ts": [("slash", r"//"), ("block", r"/\*")],
    "typescript": [("slash", r"//"), ("block", r"/\*")],
    "c": [("slash", r"//"), ("block", r"/\*")],
    "cpp": [("slash", r"//"), ("block", r"/\*")],
    "c++": [("slash", r"//"), ("block", r"/\*")],
    "csharp": [("slash", r"//"), ("block", r"/\*")],
    "cs": [("slash", r"//"), ("block", r"/\*")],
    "go": [("slash", r"//"), ("block", r"/\*")],
    "php": [("slash", r"//"), ("block", r"/\*")],
    "kotlin": [("slash", r"//"), ("block", r"/\*")],
    "swift": [("slash", r"//"), ("block", r"/\*")],
    "scala": [("slash", r"//"), ("block", r"/\*")],
    "css": [("block", r"/\*")],
    "html": [("html", r"<!--")],
    "xml": [("html", r"<!--")],
    "vue": [("slash", r"//"), ("block", r"/\*"), ("html", r"<!--")],
}

STRING_RE = re.compile(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')')


class Checker:
    def __init__(self, spec, base):
        self.spec = spec
        self.base = base
        self.errors = []
        self.warnings = []
        self.info = []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def ok(self, msg):
        self.info.append(msg)

    def run(self):
        sections = self.spec.get("sections", [])
        if not sections:
            self.err("spec 里没有任何章节（sections 为空）")
            return self.report()

        heads = [str(s.get("heading") or s.get("title") or "") for s in sections]
        joined = " ".join(heads)
        for group, keys in REQUIRED_GROUPS.items():
            if not any(k in joined for k in keys):
                self.err(f"缺少「{group}」相关章节（标题中应包含 {' / '.join(keys)} 之一）")

        self.check_meta()
        self.check_blocks(sections)
        self.check_summary(sections)
        self.check_captions(sections)
        return self.report()

    def check_meta(self):
        meta = self.spec.get("meta", {})
        for key, label in (
            ("course", "课程名称"),
            ("title", "实验名称"),
            ("student", "学生姓名"),
            ("student_id", "学号"),
        ):
            if not str(meta.get(key, "")).strip():
                self.warn(f"封面信息缺少{label}（meta.{key}）")
        if meta.get("title") and "实验" not in meta["title"]:
            self.warn("实验名称里没有「实验」二字，确认是否写成课程名或章节名")

    def strip_strings(self, line):
        return STRING_RE.sub('""', line)

    def check_code(self, text, lang, where):
        lang = (lang or "").lower().strip()
        rules = COMMENT_RULES.get(lang)
        if not lang:
            self.warn(f"{where}：代码块未标注 lang，无法自动检查注释")
            return
        if rules is None:
            return
        lines = text.split("\n")
        hits = []
        for i, raw in enumerate(lines, 1):
            line = self.strip_strings(raw)
            for kind, pat in rules:
                if kind == "html" and pat in line:
                    hits.append((i, raw.strip()[:50]))
                    break
                if kind in ("slash", "dash", "block") and re.search(pat, line):
                    hits.append((i, raw.strip()[:50]))
                    break
                if kind == "hash":
                    idx = line.find("#")
                    if idx == 0 and i == 1 and line.startswith("#!"):
                        continue
                    if idx >= 0:
                        hits.append((i, raw.strip()[:50]))
                        break
        if hits:
            detail = "；".join(f"第 {n} 行「{s}」" for n, s in hits[:4])
            self.err(f"{where}：代码含注释（要求代码部分不带注释）→ {detail}")
        if re.search(r'("""|\'\'\')', text) and lang in ("python", "py"):
            self.warn(f"{where}：出现三引号块，确认不是文档字符串注释")

    def check_blocks(self, sections):
        lang_missing = 0
        result_images = 0
        total_images = 0
        for sec in sections:
            head = str(sec.get("heading") or sec.get("title") or "")
            is_result = any(k in head for k in RESULT_KEYWORDS)
            for block in sec.get("blocks", []):
                if not isinstance(block, dict):
                    self.check_placeholders(str(block), head)
                    continue
                btype = block.get("type", "para")
                if btype == "code":
                    lang = block.get("lang", "")
                    if not lang:
                        lang_missing += 1
                    self.check_code(block.get("text", ""), lang, f"「{head}」的代码块")
                    if not block.get("caption"):
                        self.warn(f"「{head}」有一段代码没有 caption（代码清单标题）")
                elif btype == "image":
                    total_images += 1
                    if is_result:
                        result_images += 1
                    self.check_image(block, head, is_result)
                elif btype == "table":
                    cols = block.get("columns", [])
                    rows = block.get("rows", [])
                    if not cols:
                        self.err(f"「{head}」有一张表缺少 columns")
                    for r in rows:
                        if len(r) != len(cols):
                            self.warn(f"「{head}」表格「{block.get('caption', '')}」行列数不一致：{len(r)} vs {len(cols)}")
                    if not block.get("caption"):
                        self.warn(f"「{head}」有一张表没有 caption")
                elif btype == "flow_table":
                    if len(block.get("steps", [])) > 5:
                        self.warn(f"「{head}」Word 内流程表超过 5 个方框，建议改用 gen_diagram 画图")
                elif btype in ("para", "lead", "step", "note", "list"):
                    texts = [block.get("text", "")] + list(block.get("items", []))
                    for t in texts:
                        self.check_placeholders(str(t), head)
        if lang_missing > 1:
            self.warn(f"有 {lang_missing} 段代码没写 lang 字段，注释检查与展示都会受影响")
        if result_images == 0:
            self.err("「实验结果」章节一张截图都没有，必须有真实运行截图作为证据")
        if total_images < 2:
            self.warn(f"全文只有 {total_images} 张图，工科实验报告一般需要 3 张以上（含设计图）")

    def check_placeholders(self, text, head):
        for p in PLACEHOLDERS:
            if p in text:
                self.err(f"「{head}」出现占位内容「{p}」，必须替换为实际内容")
                return

    def check_image(self, block, head, is_result):
        path = block.get("path", "")
        full = path if os.path.isabs(path) else os.path.join(self.base, path)
        cap = block.get("caption", "")
        if not path:
            self.err(f"「{head}」有一张图没有 path")
            return
        if not os.path.exists(full):
            self.err(f"图片不存在：{path}")
            return
        try:
            from PIL import Image

            with Image.open(full) as im:
                w, h = im.size
            if w < 600:
                self.warn(f"图片偏小（{w}px 宽），打印后可能发虚：{path}")
            if h > 0 and w / h > 5:
                self.warn(f"图片高宽比异常（{w}x{h}），检查是否只截到一条：{path}")
        except Exception:
            self.warn(f"无法读取图片尺寸：{path}")

        if is_result:
            log = os.path.splitext(full)[0] + ".log.txt"
            if not os.path.exists(log) and not block.get("captured"):
                self.err(
                    f"「{head}」的截图 {path} 没有对应的真实执行日志 {os.path.basename(log)}，"
                    f"也没有 captured: true 标记。截图必须来自真实运行。"
                )
        if not cap:
            self.warn(f"「{head}」有一张图没有 caption")

    def check_summary(self, sections):
        for sec in sections:
            head = str(sec.get("heading") or sec.get("title") or "")
            if not any(k in head for k in SUMMARY_KEYWORDS):
                continue
            texts = []
            for b in sec.get("blocks", []):
                if isinstance(b, dict) and b.get("type") in ("para", "lead", None):
                    texts.append(str(b.get("text", "")))
                elif isinstance(b, str):
                    texts.append(b)
            body = "".join(texts)
            n = len(re.sub(r"\s", "", body))
            if n < 120:
                self.warn(f"实验总结只有 {n} 字，偏短（建议 200~500 字，讲清 2~3 个具体问题）")
            elif n > 1000:
                self.warn(f"实验总结 {n} 字，过长；初学者总结不需要面面俱到")
            for c in CLICHE:
                if c in body:
                    self.warn(f"实验总结出现套话「{c}」，改成自己的具体经历更真实")
            if not re.search(r"我|本人|自己|第一版|一开始|当时|后来|试着|发现", body):
                self.warn("实验总结没有第一人称叙述，读起来像百度百科，建议写「我遇到…」")
            return
        self.err("没有找到实验总结章节，无法检查总结口吻")

    def check_captions(self, sections):
        fig_seen, tab_seen = {}, {}
        chapter = 0
        for sec in sections:
            if int(sec.get("level", 1)) == 1:
                chapter += 1
            for b in sec.get("blocks", []):
                if not isinstance(b, dict):
                    continue
                cap = str(b.get("caption", ""))
                m = re.match(r"^图\s*(\d+)-(\d+)", cap)
                if m:
                    key = (m.group(1), m.group(2))
                    fig_seen[key] = fig_seen.get(key, 0) + 1
                m = re.match(r"^表\s*(\d+)-(\d+)", cap)
                if m:
                    key = (m.group(1), m.group(2))
                    tab_seen[key] = tab_seen.get(key, 0) + 1
        for kind, seen in (("图", fig_seen), ("表", tab_seen)):
            dup = [f"{k[0]}-{k[1]}" for k, v in seen.items() if v > 1]
            if dup:
                self.warn(f"{kind}编号重复：{', '.join(dup)}（建议交给脚本自动编号，caption 不写编号）")

    def report(self):
        print("实验报告交付前自检")
        print("-" * 72)
        for m in self.info:
            print(f"[OK]   {m}")
        for m in self.warnings:
            print(f"[WARN] {m}")
        for m in self.errors:
            print(f"[ERR]  {m}")
        print("-" * 72)
        print(f"错误 {len(self.errors)} 条，警告 {len(self.warnings)} 条")
        if self.errors:
            print("必须修复以上错误后重新生成，否则会被判定为不合格报告。")
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "ok": not self.errors,
        }


def main():
    ap = argparse.ArgumentParser(description="实验报告内容自检")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    try:
        with open(args.spec, encoding="utf-8") as f:
            spec = json.load(f)
    except Exception as e:
        print(f"读取 spec 失败：{e}")
        sys.exit(2)
    base = os.path.dirname(os.path.abspath(args.spec))
    result = Checker(spec, base).run()
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"结果写入 {args.json}")
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
