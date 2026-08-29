# 公共数据契约与本地私有层

`data/progress.csv`、`data/questions.csv`、`data/errors.csv` 是**仅含表头**的公共模板，不保存任何人的成绩、用时、错题或掌握状态。字段契约位于 `data/schemas/v1/`，当前数据 Schema 版本为 `1.0.0`。

## 初始化本地数据

```bash
python scripts/init_local_data.py
```

命令会把三张公共模板复制到被 Git 忽略的 `data/local/`。已经存在的文件不会被覆盖；需要从旧版表头升级时使用迁移工具：

```bash
python scripts/migrate_local_data.py --source-dir path/to/old-data --output-dir data/local
python scripts/validate_local_data.py
python scripts/generate_local_reports.py
```

报告默认写入 `data/local/reports/`：

- `weak-nodes.md`：按掌握等级、错题和未关闭错因聚合薄弱节点；
- `retest-3-7-14.md`：列出逾期及未来 3/7/14 天复测；
- `weekly-review.md`：汇总最近 7 天题量、正确情况、用时、错因与下一周重点。

所有 `data/local/` 内容均被 `.gitignore` 排除，也不会被文档站、bundle、Release 或 PR 收集。公开模板新增字段只能追加在末尾；旧的九/十一字段表头仍可导入，再由迁移脚本补齐新字段。

日期统一使用 `YYYY-MM-DD`；多个节点和标签使用英文分号 `;` 分隔；错因标签建议使用 `C/T/M/A/R/S/E`。
