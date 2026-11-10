# 工科实验报告生成 · Engineering Lab Report

把一次真实的编程 / 数据库 / 软件开发实验，整理成可以直接提交的 Word 实验报告。

这个技能不做「一键生成报告」——它先确认你的实验环境跑得起来，再真实运行拿截图，配齐图表，最后按中文论文规范排版成 `.docx`。**每一步都有证据链**：每张结果图都对应一次真实执行日志，不能编造。

## 能产出什么

- **可提交的 Word 文档**：A4、宋体小四、1.5 倍行距、三线表、图下表上图注编号、封面与目录
- **真实运行截图**：命令行 / 数据库 CLI / Web 页面，自动截图并留存同名的 `.log.txt` 执行日志
- **自绘图表**：E-R 图、流程图、架构图、类图、柱状/折线统计图
- **环境体检表**：自动探测语言、数据库、框架版本，缺失项给出补全方案，结果直接写进「实验环境」一节

## 覆盖的四类实验

| 类型 | 典型题目 | 核心证据物 |
| --- | --- | --- |
| A 语言 / 算法 | 循环与函数、链表、排序、文件读写 | 代码 + 多组输入输出 + 复杂度 |
| B 软件开发 | Servlet / SSM / Spring Boot / Vue / 小程序 | 工程结构 + 接口 + 页面截图 + 部署 |
| C 数据库 | E-R 设计、建表、查询、触发器、范式 | E-R 图 + 表结构 + SQL + 查询结果 |
| D 软工 / 理论 | 需求分析、UML、测试、OS / 网络实验 | 模型图 + 用例 + 测试记录 |

**不适用**：硬件电路、化学、物理等需要仪器测量的实验；需要伪造实验数据的场景。

## 安装

把整个目录放到 WorkBuddy 的用户级技能目录：

```bash
git clone https://github.com/<your-name>/engineering-lab-report.git \
  ~/.workbuddy/skills/engineering-lab-report
```

重启会话后，说「写一份数据库实验报告」即可触发。

## 快速开始

```bash
# 0. 确定解释器并检查工具链（首次运行会自动装 python-docx / Pillow / matplotlib）
PY="$HOME/.workbuddy/binaries/python/envs/default/bin/python"
$PY scripts/setup_env.py

# 1. 环境体检（缺失项可加 --install 自动补全）
$PY scripts/check_env.py --preset db-sqlite --install --md-out env_table.md

# 2. 真实运行并截图（图和日志同名同目录）
$PY scripts/run_and_capture.py --cmd "python main.py" --out shots/run1.png --title "运行主程序"

# 3. 画图（flow / arch / er / class / bar / line）
$PY scripts/gen_diagram.py --spec figs/er.json --out figs/er.png

# 4. 组稿后先自检，再生成 Word
$PY scripts/preflight.py --spec content.json
$PY scripts/build_report.py --spec content.json --out 实验报告.docx
```

生成 `.docx` **不需要**安装 Word / WPS / Pages，`python-docx` 直接写 OOXML。打开后按 F9 更新目录域即可。

## 工作流

| 步骤 | 做什么 | 产出 |
| --- | --- | --- |
| 0 | 读题，判定实验类型 | 章节骨架 + 证据清单 |
| 1 | 工具链自检 | 可用的脚本环境 |
| 2 | 实验环境体检与补全 | `env_table.md` |
| 3 | 真实实验与取证 | `shots/*.png` + `*.log.txt` |
| 4 | 图表绘制 | `figs/*.png` |
| 5 | 组稿 | `content.json` |
| 6 | 交付前自检 | 零 `[ERR]` |
| 7 | 生成并交付 | `实验报告.docx` |

## 目录结构

```
engineering-lab-report/
├── SKILL.md                     技能定义与七步流程
├── references/
│   ├── report-structure.md      四类实验的章节骨架与证据要求
│   ├── writing-style.md         代码、正文、总结的写法约束
│   ├── diagrams.md              六种图的选择与描述格式
│   └── env-and-capture.md       环境探测与真实截图取证
├── scripts/
│   ├── setup_env.py             工具链自检与依赖安装
│   ├── check_env.py             实验环境体检（可输出 Markdown 表格）
│   ├── run_and_capture.py       真实执行 + 终端截图 + 日志
│   ├── shot_web.py              Web 页面截图
│   ├── gen_diagram.py           E-R / 流程 / 架构 / 类图 / 统计图
│   ├── preflight.py             交付前自检（代码注释、截图日志、套话）
│   ├── build_report.py          content.json → .docx（三线表、题注编号）
│   └── verify_docx.py           docx → PDF → 逐页预览，目视校验版面
└── assets/
    └── example_content.json     content.json 完整示例
```

## 设计原则

1. **先体检再动手**——缺什么补什么，补不上就走等价技术路线，并在报告里如实写明
2. **代码零注释**——靠命名和结构自解释，`preflight` 会强制拦截
3. **结果只贴真实截图**——每张图都要有同名 `.log.txt`，失败截图不能当成功结果
4. **不编造**——不编版本号、不编运行输出、不编报错、不编性能数字，没有就写没有
5. **总结按初学者写**——只讲 2~3 个具体卡点，200~450 字，第一人称，不写「综上所述」

## 依赖

- Python 3.9+
- `python-docx`、`Pillow`、`matplotlib`（`setup_env.py` 自动安装）
- 可选：Chrome / Edge / chromium（网页截图）、LibreOffice 或 Pages（版面预览）

支持 macOS / Linux / Windows，跨平台差异（终端字体、截图浏览器、包管理器）已在 `SKILL.md` 中列明。

## 常见问题

**生成后目录是空的？** 目录是 Word 域，右键「更新域」或按 F9 生成。

**需要装 Word 吗？** 不需要。只有想「看」的时候才需要一个能打开 docx 的软件。

**能用 Pages 导出 Word 吗？** 不能。页码、目录、页眉页脚、三线表边框都会走样，请直接用 `build_report.py` 生成的 `.docx`。

**学校有统一模板怎么办？** 不要用 `build_report.py` 硬套，改走模板填充，保住原版式。

## 使用许可

本仓库为作者个人作品，保留所有权利。未经许可不得用于商业售卖或二次分发；个人学习与自用不受限制。如需授权请联系作者。
