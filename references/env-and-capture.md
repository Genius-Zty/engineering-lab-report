# 环境体检与真实截图取证

实验报告的可信度来自两件事：环境是真的，截图是真的。这份文档规定这两件事怎么做。

## 一、工具链自检（报告脚本本身）

```bash
PY="$HOME/.workbuddy/binaries/python/envs/default/bin/python"
$PY scripts/setup_env.py
```

依赖：`python-docx`（写 docx）、`Pillow`（画图/截终端）、`matplotlib`（统计图）。
中文字体检测失败时图表会出现方块，必须先解决：macOS 用 Hiragino/宋体，Linux 装 `fonts-wqy-zenhei` 或 Noto CJK。

## 二、实验环境体检

### 常用检测项

| 需求写法 | 含义 | 示例 |
| --- | --- | --- |
| `python>=3.9` | 命令 + 版本下限 | 解释器是否可用 |
| `cmd:mysql` | 可执行文件存在 | 数据库客户端 |
| `py:flask` | Python 模块可导入 | 框架依赖 |
| `npm:express` | Node 包可解析 | 前端依赖 |
| `port:3306` | 本机端口是否在监听 | 数据库服务是否启动 |
| `file:./app.py` | 文件存在 | 工程完整性 |
| `env:JAVA_HOME` | 环境变量 | Java 环境 |

### 预设

`python`、`python-web`、`python-data`、`java-web`、`c-cpp`、`web-frontend`、`db-sqlite`、`db-mysql`、`db-postgres`、`db-mongo`、`git`、`docker`。

```bash
$PY scripts/check_env.py --preset db-mysql --install
$PY scripts/check_env.py --need "python>=3.9" --need cmd:gcc --need py:numpy --md-out env_table.md
```

### 补全的优先级

1. **项目级依赖，直接装**：`pip install` 到当前 venv、`npm install` 到工程目录。不需要问用户。
2. **系统级安装，先说再做**：brew / apt 装数据库、JDK、编译器等，先把"要装什么、多大、为什么"讲清楚，得到同意再加 `--allow-system`。
3. **装不上就换等价路线**，并在报告里写明：

| 课程要求 | 可替代 | 报告里怎么写 |
| --- | --- | --- |
| MySQL 8.0 | SQLite 3 / MariaDB | 说明 DDL 兼容，标注方言差异 |
| Redis | 内存字典 / 文件缓存 | 说明仅验证逻辑，未验证并发性能 |
| Spring Boot | 纯 Servlet / Flask | 说明框架差异，接口设计保持一致 |
| Oracle | PostgreSQL | 说明序列、分页语法差异 |
| Tomcat | 内置 HTTP 服务器 | 说明部署方式变化 |

4. **绝对不能做**：编造版本号、假装装好了、把未运行的代码写成"运行成功"。

### 体检结果直接进报告

`--md-out env_table.md` 产出三线表内容，复制到 `content.json` 的「实验环境」表里。状态 `WARN`（如端口未监听）要在正文说明，不要藏起来。

## 三、真实截图取证

### 三类实验，三种取法

| 场景 | 工具 | 命令 |
| --- | --- | --- |
| 命令行程序、脚本、编译运行 | `run_and_capture.py` | 真实执行 + 终端截图 + 日志 |
| 数据库（SQL、表结构、执行计划） | `run_and_capture.py` | 同上，命令用 `sqlite3`/`mysql` |
| Web 前端页面 | `shot_web.py` | 无头 Chrome 截真实页面 |
| IDE 界面（断点、工程树） | 手动截图 + `captured: true` | 无法自动化时 |

```bash
$PY scripts/run_and_capture.py --cmd "python main.py" --out shots/run1.png --title "运行主程序"
$PY scripts/run_and_capture.py --cmd "sqlite3 shop.db < q1.sql" --out shots/q1.png --title "统计查询"
$PY scripts/run_and_capture.py --cmd "python -m venv .venv" --out shots/x.png --style light
```

参数要点：

- `--title` 写这一步在干什么（"插入测试数据""验证外键约束"），会显示在窗口标题栏。
- `--style dark|light`：全篇统一，别一张深一张浅。
- `--max-lines`：输出太长时截断，避免一张图占满整页。
- `--no-prompt`：不想暴露命令时用；一般保留 `$ 命令` 更有说服力。

脚本会同时写 `shots/xxx.log.txt`（时间、目录、命令、退出码、完整输出），这是截图的"出生证明"，`preflight.py` 会检查。

### Web 页面

```bash
# 1. 真实启动服务（另开后台任务，或短暂 timeout 记录启动日志）
$PY scripts/run_and_capture.py --cmd "npm run dev" --out shots/start.png --timeout 20

# 2. 截页面
$PY scripts/shot_web.py --url http://127.0.0.1:5173/login --out shots/login.png
$PY scripts/shot_web.py --url http://127.0.0.1:5173/list --out shots/list.png --full-page
$PY scripts/shot_web.py --url http://127.0.0.1:5173 --out shots/detail.png --script "document.querySelector('.row').click()"
```

- 默认 1280×800、2 倍像素（输出 2560px 宽），14cm 排版下约 460dpi。
- Chrome 通道只截窗口范围：长页面加大 `--height`，或装 `playwright` 后用 `--full-page`。
- 需要登录态时，先用 `--script` 填表单，或改用带 cookie 的页面。
- 截不到就检查：服务是否真的在跑、端口对不对、页面是否需要登录。

### 数据库截图建议顺序

1. `.tables` / `SHOW TABLES` —— 证明库建好了
2. `.schema` / `DESC 表名` —— 证明约束生效
3. 数据插入后的 `SELECT *` —— 证明数据进去了
4. 关键查询结果 —— 报告的核心证据
5. 违规插入的报错 —— 证明约束真的在起作用（很有说服力）

### IDE / 桌面 GUI

自动化截 IDE 需要屏幕录制权限，不稳定。做法：

1. 让用户自己截图（Cmd+Shift+4），存到 `shots/`。
2. `content.json` 里该图加 `"captured": true`，`preflight` 才不会报错。
3. 正文里注明"图为在 IntelliJ IDEA 中调试第 42 行的截图"。

## 四、截图规范

- 一张图只表达一个结论。别把终端、浏览器、IDE 拼在一张图里。
- 图里要能看到关键信息：命令、参数、输出、退出状态。
- 不要把无关的长输出贴进来（日志刷屏），用 `--max-lines` 或先 `tail` / `head` 过滤。
- 尺寸：宽度 ≥ 900px，避免发虚；同一篇报告里风格统一。
- 文件名有意义：`shots/er-check.png` 好过 `shots/1.png`。

## 五、失败截图也是证据

程序跑不通时，不要伪造成功：

1. 截图保留报错原文（这是最有价值的信息）。
2. 正文写清楚：报什么错 → 怎么定位 → 怎么改 → 改完的结果。
3. 改完后再截一张成功的图。两张图构成完整的调试过程，比一张假成功更有说服力。

## 六、常见环境问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `ModuleNotFoundError` | 依赖没装或装错解释器 | 用同一个 `$PY` 装和跑 |
| `command not found: mysql` | 客户端未安装 | brew install mysql-client |
| `Can't connect to MySQL server` | 服务没启动 | `brew services start mysql` |
| 端口占用 `EADDRINUSE` | 上次进程没退 | 换端口或 kill 旧进程 |
| 终端输出中文乱码 | 编码不是 UTF-8 | 设 `PYTHONIOENCODING=utf-8` |
| 图表中文变方块 | 缺中文字体 | 装字体或换 `draw_chart` 的字体候选 |
| 截图是空白页 | 服务没起来 / 页面异步未加载 | 加 `--wait`，先看启动日志 |
