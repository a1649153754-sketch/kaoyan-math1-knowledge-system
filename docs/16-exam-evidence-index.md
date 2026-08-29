# 真题证据索引

`v1.4.0` 将本仓库的稳定知识节点和母题资源与 2010—2026 数学一逐题元数据连接起来。它是“题目出现过什么能力要求”的证据层，不是试卷镜像，也不是答案库。

## 公开边界

正式真题逐题记录只包含：年份、题号、题型、分值、知识节点、母题主/辅助挂接、100 分难度、简短路线标签和衍生错因标签。以下内容不会进入仓库、Pages、Release 或 PR：

- 完整题面、选项、图形；
- 答案、解析、陷阱说明；
- 下游源文件及本地路径；
- 来源再发布权未确认的模拟卷逐题身份。

2010—2025 的 `official-archive` 只表示考试年份与数学（一）归档身份。2026 数据是考后重构、多源交叉和模型独立复算结果，明确标记为 `reconstructed`、`officialOriginalAvailable: false`、`officialAnswerAvailable: false`；不得称为官方原卷或官方答案。

模拟卷只发布匿名聚合统计，不发布卷名、机构、题号或逐题路线。节点和母题聚合采用至少 5 题的小样本抑制门槛。

## 机器接口

| 产物 | 用途 |
|---|---|
| [`official-questions.json`](../data/exam-evidence/v1/official-questions.json) | 2010—2026 正式卷版权安全逐题元数据 |
| [`mock-aggregate.json`](../data/exam-evidence/v1/mock-aggregate.json) | 模拟卷匿名聚合统计 |
| [`indexes.json`](../data/exam-evidence/v1/indexes.json) | 年份、母题、知识节点、错因四向反查 |
| [`manifest.json`](../data/exam-evidence/v1/manifest.json) | 来源快照、真实性边界、计数与 SHA-256 |
| [`schemas/`](../data/exam-evidence/v1/schemas/) | 版本化 JSON Schema |

接口身份使用 `kaoyan-math1/exam-evidence/*@1`，结构版本为 `1.0.0`。题目 ID 采用 `YYYY-M1-QNN`；知识节点和母题继续引用本仓库既有稳定 ID，不另建同义身份。

## 挂接规则

主母题按核心节点直接重合优先，辅助节点重合次之；无直接重合时，退回同章节的最近母题。`H0/L0` 基础节点使用显式、稳定的基础映射。每题保留一个主母题和至多两个辅助母题，简短路线标签来自公开母题表的“第一动作”，不从下游解析摘录。

错因标签由 100 分难度模型的五个分量确定：路线识别、计算、知识连接、条件检查和路线耦合。它们是复盘入口，不宣称考生已经发生对应错误。

## 生成与校验

生成器只读本地私有下游，不把路径或题面写入产物：

```bash
python scripts/import_exam_evidence.py --source /path/to/private-downstream --write
python scripts/build_exam_evidence_indexes.py --check
python scripts/validate_project.py
```

提交后的验证不依赖私有下游，只检查已发布产物是否自洽：字段白名单、ID 解析、年份覆盖、2026 真实性边界、模拟卷匿名边界、反向索引一致性和清单哈希都会在 CI 中执行。重新生成时，`generatedAt` 继承下游固定快照时间，不读取系统当前时间，因此同一输入会得到确定性输出。
