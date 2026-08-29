# 项目维护与迭代指南

这一页说明怎样把知识框架长期维护下去，而不是更新两次后又散成一堆笔记。

## 一、单一事实来源

日常编辑以 `docs/` 内的分章节文件为准；`releases/` 是已经发布的不可变快照。不要直接修改旧版本快照。

## 二、新增内容的最小标准

每个新节点至少回答四件事：

1. **触发信号**：什么题目或表达式会想到它？
2. **适用条件**：定理、公式和方法合法的条件是什么？
3. **执行动作**：第一步做什么，后续怎样推进？
4. **失效边界**：哪类相似外观不能机械套用？

有条件时再补：典型题、最小反例、掌握证据和回测日期。

## 三、编号规则

- 正式正文节点：只取 `docs/01—04`“知识节点”列表中的 `H/L/P/M数字.数字`。
- 三级清单项：完整 ID 形如 `H1.5-a`，属于独立命名空间；它的数字前缀不自动成为正式节点。
- 公式卡：`F-模块-序号`，例如 `F-H1-03`。
- 母题：`Q-H / Q-L / Q-P`。
- 反例：`B-H / B-L / B-P`。
- 个人高频疑问：`J-01` 起连续编号。

资源关联必须解析到正式节点或合法章节。已发布 ID 由 `data/released-identities.v1.json` 冻结，不复用、不重排；废弃时注明 `deprecated/replacedBy`，不能静默删除。

## 四、个人数据层

`data/` 中提供三张仅含表头的公共模板：

- `progress.csv`：知识节点掌握等级与回测日期。
- `questions.csv`：真题/练习题与母题、节点的挂接。
- `errors.csv`：错因、修复动作和复测状态。

不得直接在公共模板中填数据。运行 `python scripts/init_local_data.py` 后，在被 Git 忽略的 `data/local/` 中记录个人成绩、用时、错题和掌握状态。Schema 位于 `data/schemas/v1/`；旧版数据先运行迁移脚本，再进行本地校验和报告生成。完整流程见[本地掌握图谱与自动复盘](15-local-data.md)。

## 五、发布一个新版本

```bash
# 1. 编辑 docs/ 与公共空白数据契约
python -m unittest discover -s tests -p "test_*.py"
python scripts/validate_project.py
python scripts/build_released_identities.py --check
python scripts/check_bundle_deterministic.py

# 2. 修改 VERSION，例如 1.3.0
python scripts/check_bundle_deterministic.py

# 3. 更新 CHANGELOG.md
# 4. 提交、合并并创建 v1.3.0 标签
```

`build_bundle.py` 会读取 `VERSION`，把分章节正文合并到 `dist/`。确认内容无误后，将单文件 Markdown、Word、PDF 或压缩包作为 GitHub Release 资产发布；`releases/vX.Y/` 只保留版本说明与必要元数据。

只有在正式发布新增 ID 时，才运行 `python scripts/build_released_identities.py --snapshot-version <版本>` 更新稳定身份基线；普通内容修订不得改写该文件。

## 六、推荐的分支和提交方式

- `main`：始终保持可构建。
- `docs/H1-limit`：某个知识专题的增补。
- `fix/L4-rank-condition`：条件、公式或表述纠错。
- `feat/data-contract`：只用于公共空白模板、Schema 或工具变更，不包含个人记录。
- 个人记录不创建公开分支；只保存在 `data/local/` 或其他私有存储。

提交信息示例：

```text
docs(H1): 补充参数极限临界值分类
fix(P6): 修正卡方分布自由度条件
chore(data): 升级公共 CSV Schema
```
