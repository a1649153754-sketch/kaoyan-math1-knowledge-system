# 考研数学一知识体系

> 一套可持续增补、可定位薄弱点、可关联真题与错题的考研数学一知识树。

<p align="center">
  <img src="docs/assets/images/social-preview.svg" alt="考研数学一知识体系封面" width="900">
</p>

## 当前版本

**v1.5.0 · 2026-08-30**

| 模块 | 当前规模 |
| --- | ---: |
| 正式知识节点 | 253 |
| 三级知识点检查项 | 321 |
| 公式与结论速查卡 | 212 |
| 典型真题母题 | 68 |
| 最小反例与失效边界 | 40 |
| 个人高频疑问挂接 | 12 |
| 2010—2026 正式卷元数据 | 17 卷 / 385 题 |
| 全章节执行卡 / 核心讲解 | 253 张 / 87 组 |
| 冲刺候选 / 核心公式 | 56 个 / 64 张 |

## 项目特点

- **固定编号**：高数 `H`、线代 `L`、概率统计 `P`、方法库 `M`，增补时尽量不改旧编号。
- **条件优先**：公式与定理同时记录触发条件、结论和失效边界，不做裸公式堆砌。
- **题目挂接**：真题、错题和疑问可挂到 `Q / B / J` 编号，逐步形成个人掌握图谱。
- **版本可追溯**：`releases/` 保存历史版本；`CHANGELOG.md` 记录每次升级。
- **契约可校验**：正式节点、三级清单项与 `F / Q / B / J` 资源使用独立命名空间；发布过的 ID 由机器基线保护。
- **公核私层**：Git 只保存通用知识、空白模板和版本化 Schema；个人掌握、用时、错题与报告写入被忽略的 `data/local/`。
- **真题证据层**：公开 2010—2026 的去题面化逐题元数据和四向索引；模拟卷只保留匿名聚合。
- **正文自包含**：35 章、253 个节点均有执行卡；原理、路线演示与最小反例写在正文内，外部来源只用于核验和延伸。
- **冲刺生成层**：依据题数、挂接分值、跨章连接和难度确定性生成 56 个候选节点、64 张核心公式、条件表与反例速翻页。
- **网页可发布**：内置 Zensical 配置和 GitHub Actions，推送后可自动部署为 GitHub Pages 文档站。

## 快速阅读

- [体系总览](docs/00-overview.md)
- [高等数学](docs/01-calculus.md)
- [线性代数](docs/02-linear-algebra.md)
- [概率论与数理统计](docs/03-probability-statistics.md)
- [公式速查系统](docs/10-formula-cards.md)
- [典型母题索引](docs/11-problem-archetypes.md)
- [反例与失效边界库](docs/12-counterexamples.md)
- [本地掌握图谱与自动复盘](docs/15-local-data.md)
- [2010—2026 真题证据索引](docs/16-exam-evidence-index.md)
- [v1.5 冲刺速查手册](docs/17-sprint-manual.md)

## 获取完整版本

- 在线阅读：进入 [GitHub Pages 文档站](https://a1649153754-sketch.github.io/kaoyan-math1-knowledge-system/)（首次部署完成后生效）。
- 单文件 Markdown：运行 `python scripts/build_bundle.py`，输出到 `dist/`。
- Word、PDF 与发布压缩包：在仓库的 **Releases** 页面下载；二进制发布物不重复写入 Git 历史。

## 一键上传到 GitHub（Windows）

解压项目后，双击根目录中的 `UPLOAD_TO_GITHUB.cmd`。脚本会通过 GitHub CLI 的官方网页授权完成登录，并在实际推送前要求你明确选择公开或私有仓库、核对目标账号与仓库名。

脚本不会要求你粘贴 GitHub 密码或 Personal Access Token。完整说明见 [UPLOAD_TO_GITHUB.md](UPLOAD_TO_GITHUB.md)。

## 本地预览文档站

需要 Python 3.10 或更高版本：

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
zensical serve
```

浏览器打开 `http://127.0.0.1:8000`。构建静态站点：

```bash
zensical build --clean
```

## 推荐维护流程

1. 在 `docs/` 对应章节中增补内容。
2. 给新增内容分配稳定编号，并补齐“条件—结论—边界—掌握证据”。
3. 个人记录先运行 `python scripts/init_local_data.py`，只写入被 Git 忽略的 `data/local/`。
4. 运行 `python -m unittest discover -s tests -p "test_*.py"` 和 `python scripts/validate_project.py` 检查结构、编号、引用、链接与公开数据边界。
5. 运行 `python scripts/build_released_identities.py --check`、`python scripts/build_exam_evidence_indexes.py --check` 和 `python scripts/build_sprint_manual.py --check` 检查稳定 ID、真题反向索引与冲刺手册。
6. 运行 `python scripts/check_bundle_deterministic.py` 生成含冲刺手册的单文件 Markdown，并确认构建可复现。
7. 更新 `VERSION` 与 `CHANGELOG.md`，再提交 Pull Request 或创建新版本标签。

详细规则见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [项目维护指南](docs/14-project-maintenance.md)。

## 仓库结构

```text
.
├─ docs/                    # 可直接编辑、可发布成网站的分章节正文
├─ releases/                # v1.0—v1.5 历史版本说明
├─ data/                    # 空白模板、Schema、稳定 ID、真题证据与被忽略的 local 私层
├─ scripts/                 # 校验与单文件打包脚本
├─ tests/                   # 项目契约的正例与故障夹具
├─ .github/                 # Actions、Issue 表单和 PR 模板
├─ zensical.toml            # 文档站配置
├─ CHANGELOG.md             # 版本更新记录
├─ ROADMAP.md               # 后续完善路线
├─ UPLOAD_TO_GITHUB.cmd     # Windows 双击上传入口
├─ UPLOAD_TO_GITHUB.ps1     # GitHub CLI 自动上传脚本
└─ UPLOAD_TO_GITHUB.md      # 上传与开启 Pages 的说明
```

## 内容说明

本项目是复习框架与学习工具，不替代报考年度官方考试大纲。正式卷索引只发布年份、题号、分值、节点、母题、难度与短路线标签，不上传题面、答案、解析、未经授权的整套试卷扫描件或大段教材内容；2026 明确属于非官方考后重构。个人成绩、用时、错题正文和掌握状态只进入 `data/local/`，不得加入 Git、Pages、Release 或 PR。

## 许可

- 原创文字、表格和知识体系内容：`CC BY-NC-SA 4.0`，见 [LICENSE](LICENSE)。
- 脚本、工作流和配置文件：`MIT`，见 [LICENSE-CODE](LICENSE-CODE)。

项目维护者可在公开发布前自行更换许可方式。
