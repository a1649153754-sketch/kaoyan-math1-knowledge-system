# 贡献指南

欢迎纠错、补充知识点、增加反例或改进项目结构。优先提交小而清晰、能独立审核的改动。

## 可以贡献什么

- 修正公式、条件、定义或措辞。
- 增加某一固定节点下的题型、方法、反例或达标标准。
- 增加 `F / Q / B / J` 卡片并建立交叉挂接。
- 改进网页导航、校验脚本和数据模板。

## 内容质量要求

新增知识内容至少应包含：

1. 所属节点或新编号；
2. 适用条件；
3. 明确结论或执行步骤；
4. 一个失效边界或常见误区；
5. 必要时给出来源说明。

不要只写“记住这个公式”，也不要把经验性技巧伪装成无条件定理。

公共 `data/*.csv` 必须保持仅含表头。个人成绩、用时、错题和掌握状态只写入被 Git 忽略的 `data/local/`；PR 不得包含该目录中的数据或生成报告。

## 编号规范

- **正式知识节点**：`docs/01—04` 中的 `H/L/P/M数字.数字`，例如 `H7.5`。只有这些编号可以作为下游题目与资源的正式节点。
- **三级清单项**：`docs/06-checklists.md` 中的完整 `H1.5-a` 一类编号。它是独立检查项；`H6.11-a` 的前缀 `H6.11` 不一定是正式节点。
- **知识资源**：公式、母题、反例和个人疑问分别使用 `F-`、`Q-`、`B-`、`J-` 前缀。
- 资源关联栏优先填写正式节点；若精确引用清单项，该清单项的父编号必须同时是正式节点，避免下游把清单前缀误识别为悬空节点。
- 已发布 ID 受 `data/released-identities.v1.json` 保护，不得重排、删除或换用。废弃时保留原 ID，并显式记录 `deprecated/replacedBy` 迁移。

## 版权与来源

正式卷公开索引只记录年份、题号、题型、分值、知识节点、母题、难度与简短路线标签。请勿向 `data/exam-evidence/` 写入完整题面、答案、解析、图形、来源文件或本地路径；模拟卷不得公开卷名、机构或逐题身份。请勿提交整套试卷扫描件、付费讲义、教材大段原文或其他未经授权的内容。

## 提交流程

1. Fork 仓库并新建分支。
2. 修改 `docs/` 中对应页面。
3. 运行：

```bash
python -m unittest discover -s tests -p "test_*.py"
python scripts/validate_project.py
python scripts/build_released_identities.py --check
python scripts/build_exam_evidence_indexes.py --check
python scripts/check_bundle_deterministic.py
zensical build --clean
```

4. 更新必要的交叉引用和 `CHANGELOG.md`。
5. 创建 Pull Request，并说明修改原因、条件边界和验证方式。

## 提交信息建议

```text
docs(H8): 补充 Gauss 公式补面的方向检查
fix(L4): 修正非齐次方程组同解判据表述
chore(ci): 更新文档站部署流程
```
