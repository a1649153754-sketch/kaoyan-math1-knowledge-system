# 本地掌握图谱与自动复盘

本页只说明工作流。个人成绩、用时、错题和掌握状态不属于公开知识库内容，必须保存在被 Git 忽略的 `data/local/` 或其他私有存储中。

## 一、初始化

```bash
python scripts/init_local_data.py
```

命令从公共空白模板创建 `progress.csv`、`questions.csv` 和 `errors.csv`。已有文件默认不会被覆盖。

## 二、字段契约

- `progress.csv`：节点等级、优先级、证据、最近/下次复测；
- `questions.csv`：题源、年份、题号、母题、正式节点、结果、用时与错因；
- `errors.csv`：错因 ID、节点、修复动作、严重度、状态与下次复测。

当前 Schema 版本为 `1.0.0`。日期使用 `YYYY-MM-DD`；多个节点和标签用英文分号分隔。正式节点必须来自 253 个稳定节点，`mother_id` 必须是已有 `Q-` 母题。

## 三、兼容导入与迁移

v1.2.1 的九/十一字段 CSV 仍可读取。升级时指定旧数据目录和本地输出目录：

```bash
python scripts/migrate_local_data.py --source-dir path/to/old-data --output-dir data/local
```

迁移会保持旧字段和值，在末尾补入复测次数、3/7/14 天间隔、难度或严重度及 Schema 版本；自定义追加字段也会保留。目标文件已存在时需要显式使用 `--force`，避免误覆盖。

## 四、校验与报告

```bash
python scripts/validate_local_data.py
python scripts/generate_local_reports.py
```

校验覆盖表头顺序、必填项、日期、枚举、正式节点、母题和身份字段。报告写入 `data/local/reports/`：

1. 薄弱节点榜：综合掌握等级、优先级、错/半错题、难度和未关闭错因；
2. 3/7/14 天复测表：逾期记录进入 3 天窗口；
3. 周复盘：最近七天题量、正确情况、用时、错因标签与下一周重点。

需要复现历史周报时可固定基准日：

```bash
python scripts/generate_local_reports.py --as-of 2026-08-29
```

## 五、隐私边界

- `data/local/` 中除占位文件外的任何内容都不得被 Git 跟踪；
- 公共三张 CSV 必须保持仅含表头；
- Pages 只构建 `docs/`，bundle 只合并教学正文；
- PR、Release 和问题反馈不得附带个人数据文件或本地生成报告。

项目校验器和负例测试会阻止公共模板数据行、身份字段及被误跟踪的本地私有文件进入主分支。
