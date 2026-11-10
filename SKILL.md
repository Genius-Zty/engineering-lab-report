---
name: engineering-lab-report
display_name: "工科实验报告生成"
display_name_en: "Engineering Lab Report"
description: |
  生成工科软件类课程实验报告并导出 Word（.docx）。覆盖四类实验：编程语言/算法练习、软件开发与企业级应用、数据库设计与开发、软件工程与计算机理论。内置环境体检与补全、真实运行截图取证、图表绘制、中文实验报告排版（封面/目录/三线表/图注编号）。
  Use when the user asks for a lab report, experiment report, or course design report in computer science / software engineering, or wants an existing experiment turned into a Word document with screenshots and diagrams. Also use for 数据库实验、编程实验、课程设计报告.
  触发词：实验报告、课程实验、数据库实验报告、编程实验报告、课程设计报告、写实验报告、生成实验报告、lab report、experiment report
description_zh: "把编程、软件开发、数据库等课程实验整理成可直接提交的 Word 实验报告：环境体检与补全、真实运行截图取证、E-R 图与流程图绘制、中文排版自动成文。"
description_en: "Turn computer-science lab work into a submittable Word report: environment checks, real run screenshots, E-R and flow diagrams, and automatic Chinese academic formatting."
version: 1.0.0
visibility: "public"
agent_created: true
---

# 工科实验报告生成

把一次真实的编程 / 数据库 / 软件开发实验，整理成可以直接提交的 Word 实验报告：
先确认实验环境跑得起来，再真实运行拿截图，配齐图表，最后按中文论文规范排版。

**适用**：编程语言与算法练习、软件开发（含企业级 Web / 前后端 / 微服务）、数据库设计与开发、软件工程与计算机理论类实验。
**不适用**：硬件电路、化学、物理等需要仪器测量的实验；需要伪造实验数据的场景。

## 七条硬规则（任何一步都不能省）

1. **先体检再动手**：实验需要什么语言、数据库、框架，先检测，缺的补上；补不上就走等价技术路线，并在报告里如实写明。
2. **代码零注释**：贴进报告的代码不带任何 `//` `#` `/* */` `--` 注释，也不写文档字符串。靠命名和结构自解释。
3. **图表二选一**：要么用绘图脚本 / 外部软件出一张完整独立的图（PNG），要么在 Word 里用表格画（`flow_table`）。不要贴半截图、不要贴带界面边框的工具截图当图。
4. **结果只贴真实截图**：`实验结果` 里的每张图都必须来自真实运行，且留有 `.log.txt` 执行日志。程序报错就贴报错，但要在正文说明怎么改的，不能把失败截图当成功结果。
5. **总结按初学者写**：只讲 2~3 个具体卡点，200~450 字，第一人称，允许口语和不完美。不写"综上所述""通过本次实验我深刻认识到"。
6. **交付 Word**：A4、宋体小四、1.5 倍行距、三线表、图下表上题注。用 `build_report.py` 生成，不要手搓 docx。交付物只能是 `.docx`——不是 `.pages`、不是 `.pdf`；生成过程不需要安装 Word，`python-docx` 直接写 OOXML。
7. **不编造**：不编造版本号、运行输出、报错信息、性能数字、查表结果。没有就写没有。

## 工作目录约定

```
<实验目录>/
├── content.json          报告内容（唯一输入）
├── figs/                 自绘图：*.json 描述 + *.png 成品
├── shots/                真实截图：*.png + 同名 *.log.txt
└── 实验报告.docx          最终交付
```

所有脚本都在本技能的 `scripts/` 下。先确定解释器：

```bash
PY="$HOME/.workbuddy/binaries/python/envs/default/bin/python"
$PY scripts/setup_env.py      # 首次运行，缺 python-docx/Pillow/matplotlib 会自动装
```

Windows（PowerShell）等价写法：

```powershell
$PY = "$env:USERPROFILE\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
& $PY scripts\setup_env.py
```

没有托管环境时直接用系统 Python：`python scripts/setup_env.py`（要求 3.9+）。

### 跨平台说明

| 环节 | macOS | Linux | Windows |
| --- | --- | --- | --- |
| 生成 docx、自检 | ✅ | ✅ | ✅ 无差异 |
| 终端截图字体 | Menlo + 冬青黑 | DejaVu + 文泉驿 | Consolas + 微软雅黑/黑体 |
| 网页截图 | Chrome/Edge | chromium | Chrome/Edge（Program Files 与 `%LOCALAPPDATA%` 都会探测） |
| 文档预览 | LibreOffice / Pages | LibreOffice | LibreOffice，或 `--open` 交给 Word |
| 系统级装依赖 | brew | apt-get | 给出 winget 命令，不自动执行 |

Windows 上还有两点要注意：命令里的路径用双引号包住中文目录；`run_and_capture.py --cmd` 走的是 `cmd.exe`，多条命令用 `&&` 连接，不要用单引号。

## 流程

### 第 0 步 · 读题，判定实验类型

从用户给的要求里提取：实验名称、课程、要求的章节、要求的图表、要求的截图数量、提交格式。
按类型读 `references/report-structure.md` 对应小节，确定章节骨架和"必须有的证据物"：

| 类型 | 典型题目 | 核心证据 |
| --- | --- | --- |
| A 语言/算法 | 循环与函数、链表、排序、文件读写 | 代码 + 多组输入输出 + 复杂度 |
| B 软件开发 | Servlet/SSM/Spring Boot/Vue/小程序 | 工程结构 + 接口 + 页面截图 + 部署 |
| C 数据库 | E-R 设计、建表、查询、触发器、范式 | E-R 图 + 表结构 + SQL + 查询结果 |
| D 软工/理论 | 需求分析、UML、测试、OS/网络实验 | 模型图 + 用例 + 测试记录 |

题目没写清章节时，用该类型的默认骨架；用户给了模板就按模板章节来。

### 第 1 步 · 工具链自检

```bash
$PY scripts/setup_env.py
```

缺依赖会尝试安装。若报错，先解决再继续，不要带着坏工具链往下走。

### 第 2 步 · 实验环境体检与补全

按实验实际需要列出检测项，跑：

```bash
$PY scripts/check_env.py --preset db-sqlite --install
$PY scripts/check_env.py --need "python>=3.9" --need py:flask --need cmd:sqlite3 --md-out env_table.md
$PY scripts/check_env.py --preset java-web --install --allow-system   # 需要装 JDK/Maven 时才加
```

- 状态 `MISS` 必须处理：项目级依赖（pip / npm）直接装；系统级（brew / apt）先在回复里说明要装什么、为什么要装，用户同意后再 `--allow-system`。
- 实在装不上（无网络、无权限、版本冲突），改用等价路线：MySQL→SQLite、Spring Boot→纯 Servlet、Vue→原生 HTML+JS，并在报告的「实验环境」里写清实际用了什么、为什么替换。
- `--md-out` 生成的表格直接用作报告「实验环境」一节，不要手写版本号。

细节与替代方案见 `references/env-and-capture.md`。

### 第 3 步 · 真实实验与取证

在实验目录里写代码 / 建库 / 起服务，**用脚本记录每一次真实运行**：

```bash
# 命令行程序、脚本、数据库 CLI 都走这条
$PY scripts/run_and_capture.py --cmd "python main.py" --out shots/run1.png --title "运行主程序"
$PY scripts/run_and_capture.py --cmd "sqlite3 shop.db '.schema'" --out shots/schema.png --title "查看表结构"

# Web 项目：先真实启动服务，再截页面
$PY scripts/run_and_capture.py --cmd "python -m http.server 8080" --out shots/server.png --timeout 5
$PY scripts/shot_web.py --url http://127.0.0.1:8080/list --out shots/list.png --full-page
```

要点：

- 一张图对应一次真实执行，图和 `.log.txt` 必须同名同目录，`preflight` 会校验。
- 命令没跑成功（退出码非 0）不要当成功结果贴；先修好，或把它作为调试过程并配文字说明。
- IDE 内界面（断点、工程树）无法自动截时，让用户手动截图放到 `shots/`，并在 `content.json` 里给该图加 `"captured": true`。
- 同一实验准备 3~6 张结果图：主流程成功、边界/异常、关键中间状态。

### 第 4 步 · 图表

```bash
$PY scripts/gen_diagram.py --spec figs/er.json --out figs/er.png
```

支持 `flow`（流程图）、`arch`（架构图）、`er`（E-R 图）、`class`（类图）、`bar` / `line`（统计图）。
图里不要写大标题——报告的图注负责编号和命名；只有图要单独交时才加 `title`。
结构和示例见 `references/diagrams.md`。

简单层次 / 线性流程（3~5 个方框）也可以直接在 Word 里画：`content.json` 用 `flow_table` 块，交给 `build_report.py` 生成带边框的表格流程图。

### 第 5 步 · 组稿 content.json

按 `assets/example_content.json` 的结构写。章节顺序、每个块怎么写，见 `references/report-structure.md`；语言风格与总结写法见 `references/writing-style.md`。

块类型速查：

| type | 作用 | 关键字段 |
| --- | --- | --- |
| `para` | 正文段落（自动首行缩进） | `text`，支持 `**加粗**` |
| `lead` | 不缩进的引导句 | `text` |
| `list` | 有序/无序列表 | `items`、`ordered` |
| `step` | 步骤标题 + 说明 | `title`、`text` |
| `code` | 代码块（等宽 + 灰底） | `text`、`lang`、`caption` |
| `image` | 图片 + 图注自动编号 | `path`、`caption`、`width_cm` |
| `table` | 三线表 + 表注自动编号 | `columns`、`rows`、`caption`、`widths` |
| `flow_table` | Word 内流程框图 | `steps`、`caption` |
| `pagebreak` | 强制分页 | — |

写内容时的三条底线：代码段先自己跑通再贴；每个数字都要能对上截图；图注、表注不要手写编号（脚本会自动排 `图3-1`）。

### 第 6 步 · 交付前自检

```bash
$PY scripts/preflight.py --spec content.json
```

`[ERR]` 必须清零；`[WARN]` 逐条判断，属于内容问题的要改，属于版式的可放行。
常见拦截：代码带注释、截图缺日志、总结写成套话、占位符没替换、章节缺失。

### 第 7 步 · 生成 Word 并交付

```bash
$PY scripts/build_report.py --spec content.json --out 实验报告.docx
```

生成后用 `present_files` 把 `.docx` 交给用户，并说明：目录是 Word 域，右键「更新域」或按 F9 生成（脚本已设为打开时提示更新）。

**可选：目视校验版面**（本机没有 Word 时也能做）

```bash
$PY scripts/verify_docx.py --docx 实验报告.docx            # 自动转 PDF 并逐页出图
$PY scripts/verify_docx.py --docx 实验报告.docx --open     # 直接在 Pages / Word 里打开
```

通道优先级：LibreOffice（全自动）→ Pages（macOS 需在「系统设置 → 隐私与安全性 → 自动化」里授权，否则报 -10004）→ `--open` 人工目视。校验产出 `_preview/page-01.png` 等，逐页确认封面居中、三线表、图注编号、代码不溢出版心。

**不要**用 Pages「文件 → 导出到 → Word」来生成最终文件：域（页码、目录）、页眉页脚、单元格边框都会走样。Pages 只用来查看。

用户如果提供的是**学校统一模板**（有固定封面和章节），不要用 `build_report.py` 硬套，改走模板填充：加载 `workbuddy-office-routing`，用本地 editor_sdk 把内容写进模板空位，保住原版式。

## 交付清单

- [ ] 环境体检有结论，缺失项已补或已说明替代方案
- [ ] 代码块零注释，且是最终跑通的那一版
- [ ] 每个结果图都有同名 `.log.txt`
- [ ] 图表完整、无工具界面边框、图注表注连续
- [ ] 总结 200~450 字、第一人称、有具体卡点
- [ ] `preflight.py` 零 ERR
- [ ] `.docx` 能正常打开（Pages / Word / WPS 任选其一目视过一遍）
- [ ] 交付格式是 `.docx`，不是 `.pages` / `.pdf`

## 常见坑

- **只看退出码不看输出**：命令成功但输出为空，截图会是一张空窗口。确认有内容再截。
- **代码从 IDE 复制带注释**：`preflight` 会拦，别试图绕过，直接删注释。
- **把课程要求原文抄成"实验目的"**：目的要写成"能做什么"，不是"要求做什么"。
- **总结写成了技术综述**：初学者总结是"我卡在哪、怎么绕过去、还剩什么没搞懂"，不是知识点罗列。
- **图片过大**：宽度默认 14cm 内、高度 18cm 内会自动缩，超过正文宽度的图会挤出版心。
- **中文路径**：脚本支持，但命令里记得加引号。
- **以为要装 Word**：生成 `.docx` 不需要 Word/WPS/Pages 任何一个；只有想"看"的时候才需要。本机没装 Word 就用 Pages 打开，但别用 Pages 另存为 Word。
- **用 Pages 转存后交付**：页码、目录、页眉、三线表边框会丢，一律不采纳。
