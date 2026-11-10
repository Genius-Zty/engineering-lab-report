# 图表绘制规范

实验报告的图分两类：**设计图**（E-R、架构、流程、类图）和**数据图**（柱状、折线）。
两份来源：`gen_diagram.py` 脚本生成，或在 Word 里用表格画。

## 一、选哪种图

| 要表达的内容 | 图类型 | 生成方式 |
| --- | --- | --- |
| 实体、字段、联系 | `er` | gen_diagram.py |
| 类与类的关系 | `class` | gen_diagram.py |
| 算法/业务流程、判断分支 | `flow` | gen_diagram.py |
| 系统分层、模块划分 | `arch` | gen_diagram.py |
| 数值对比、趋势 | `bar` / `line` | gen_diagram.py |
| 3~5 步的线性流程、层次 | 表格框图 | Word 内 `flow_table` |
| 手绘草图、Visio/draw.io 导出 | 直接插入 PNG | `image` 块 |

## 二、命令

```bash
$PY scripts/gen_diagram.py --spec figs/er.json --out figs/er.png
```

输出 2 倍分辨率 PNG（220 dpi），自动裁掉白边，A4 下宽度 12~14cm 清晰可读。

## 三、各类图的结构

### E-R 图

```json
{
  "type": "er",
  "entities": [
    {"name": "学生 student",
     "fields": [
       {"name": "sno", "type": "char(10)", "pk": true},
       {"name": "sname", "type": "varchar(20)"},
       {"name": "dept", "type": "varchar(30)"}
     ]},
    {"name": "成绩 sc",
     "fields": [
       {"name": "sno", "type": "char(10)", "fk": true},
       {"name": "cno", "type": "char(8)", "fk": true},
       {"name": "grade", "type": "decimal(5,1)"}
     ]}
  ],
  "relations": [
    {"from": "学生 student", "to": "成绩 sc", "label": "选修", "card_from": "1", "card_to": "n"}
  ]
}
```

- `pk` 标主键（蓝色 PK 标签），`fk` 标外键（红色 FK 标签）。
- `columns` 控制每行几个实体，2 个实体用 1，3~4 个用 2。
- 实体名建议"中文 英文表名"，与后文 SQL 对得上。

### 类图

```json
{
  "type": "class",
  "classes": [
    {"name": "StudentService",
     "attributes": ["-studentDao: StudentDao"],
     "methods": ["+findAll(): List", "+insert(Student): int"]}
  ],
  "relations": [{"from": "StudentController", "to": "StudentService", "label": "调用"}]
}
```

### 流程图

```json
{
  "type": "flow",
  "nodes": [
    {"text": "开始", "kind": "start"},
    {"text": "读取学生信息"},
    {"text": "学号是否已存在？", "kind": "decision", "to_next": "否"},
    {"text": "写入数据库"},
    {"text": "结束", "kind": "end"}
  ]
}
```

`kind` 可选：`start` / `end`（绿色）、`process`（默认蓝）、`decision`（菱形黄）、`db`（圆柱紫）。
`to_next` 会画在箭头旁，用于写"是/否"。

### 架构图

```json
{
  "type": "arch",
  "layers": [
    {"name": "表现层", "items": ["登录页", "学生管理", "成绩查询"]},
    {"name": "业务层", "items": [{"text": "Controller", "sub": "路由"}, {"text": "Service", "sub": "业务"}]},
    {"name": "数据层", "items": [{"text": "MySQL 8.0", "sub": "业务库"}]}
  ]
}
```

### 统计图

```json
{
  "type": "bar",
  "labels": ["数据库", "数据结构"],
  "ylabel": "平均分",
  "series": [{"name": "2023级", "data": [82.4, 78.1]}]
}
```

`line` 换成折线。`legend: true` 强制显示图例。

## 四、在 Word 里画图

`content.json` 用 `flow_table` 块，`build_report.py` 会生成带边框的横向流程表：

```json
{"type": "flow_table", "caption": "数据库设计流程", "steps": ["需求分析", "概念设计", "逻辑设计", "物理实现"]}
```

适用：3~5 个方框、单向线性关系、层次结构。
不适用：有分支判断、跨层连线、超过 5 个节点 —— 这些用 `gen_diagram.py`。

好处是可以在 Word 里直接双击改文字，老师要求"在文档中绘制"时用它。

## 五、图片插入规则

```json
{"type": "image", "path": "figs/er.png", "caption": "选课系统 E-R 图", "width_cm": 14.0}
```

- `caption` 不写编号，脚本按章节自动排 `图3-1`。
- `width_cm` 省略时按图片 dpi 自动算，上限 14.5cm；高度超过 18cm 会等比缩。
- 图注在图下方（表格题注在表上方），五号宋体居中，前后留 6pt。
- 图片路径相对于 `content.json` 所在目录。

## 六、图内不要写大标题

报告的图注已经承担"编号 + 名称"，图里再写一遍"图 3-1 选课系统 E-R 图"就是重复。
`gen_diagram.py` 的 `title` 字段只在图要单独交（比如随堂提交图片）时才用。

同理：图里不要留绘图工具的界面边框、水印、坐标轴外的灰色画布。

## 七、常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 中文变方块 | 缺中文字体 | 装 Hiragino/宋体/文泉驿，或改字体候选 |
| 图挤出版心 | 宽高比太竖 | 缩短节点文字，或分两张图 |
| 箭头穿过文字 | 节点太密 | 加大 `gap`/节点间留白，简化措辞 |
| 关系线打结 | 实体排列不合理 | 调整 `columns`，把有关系的实体放相邻位 |
| 图太糊 | 原图分辨率低 | 用脚本重画，或截图时放大到 2 倍 |
