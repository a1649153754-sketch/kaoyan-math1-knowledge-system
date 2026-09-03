# Codex 项目交接：考研数学一知识体系

## 当前基线

- 仓库：`a1649153754-sketch/kaoyan-math1-knowledge-system`
- 远端版本：v1.5.0
- 在线站点：`https://a1649153754-sketch.github.io/kaoyan-math1-knowledge-system/`
- 下一主要里程碑：v2.0 知识图谱重构

## 已完成资产

- 高等数学 `H`、线性代数 `L`、概率统计 `P`、跨模块方法 `M` 四个主域；
- 253 个正式知识节点、321 个三级检查项；
- 212 张公式与结论卡、68 类母题、40 张反例边界、12 条个人疑问；
- 2010—2026 共 17 卷、385 题的去题面化真题元数据；
- 253 张节点执行卡、253 条温柔讲解、87 组自包含核心讲解；
- 56 个冲刺候选节点、64 张核心公式，以及可确定性重建的冲刺手册；
- `data/local/` 公核私层，个人正确率、用时、错题正文和复测记录不进入公开仓库。

## 关键架构

```text
正文正式节点 H/L/P/M
        ↓
公式卡 F / 母题 Q / 边界 B / 个人问题 J
        ↓
真题证据元数据与双向索引
        ↓
冲刺候选、核心公式和生成手册
        ↓
本地私有掌握数据与报告
```

正式节点、三级清单项与资源 ID 是不同命名空间。发布过的 ID 由机器基线保护；任何迁移都必须给出无损映射。

## 必需校验

```bash
python -m unittest discover -s tests -p "test_*.py"
python scripts/validate_project.py
python scripts/build_released_identities.py --check
python scripts/build_exam_evidence_indexes.py --check
python scripts/build_sprint_manual.py --check
python scripts/check_bundle_deterministic.py
zensical build --clean
git diff --check
```

## v2.0 建议拆分

### PR 1：图 Schema 与 ID 映射

定义节点、边、前置依赖、同义关系、题型触发、错因关联和来源字段。旧 ID 必须一一可查询，且不能要求手工维护第二套正文。

### PR 2：图数据生成器

从现有 Markdown、公式卡、母题、边界卡和真题元数据生成机器可读图。输出必须确定性、可校验、可重复构建。

### PR 3：契约测试与故障夹具

检测孤立节点、悬空引用、非法边、循环依赖、跨命名空间误用、ID 漂移和非确定性输出。

### PR 4：可视化与本地学习应用

生成章节依赖图、母题—节点图和本地掌握热力图。个人数据仍只在本机生成，不进入 Pages。

## Codex 首个任务

先做只读架构审计，不立即迁移正文：

1. 列出所有 ID 类型、规范源、生成物和测试契约；
2. 给出最小知识图谱 Schema；
3. 说明如何从现有内容确定性生成；
4. 证明所有旧 ID 能无损映射；
5. 给出分阶段迁移计划和故障回滚方案。

验收标准：旧文件零破坏、现有校验全部通过、图数据可重复生成、公开与私有数据边界不变。
