# paper-os（学术文献并行摄取与 Obsidian 深度知识体系编排器）

`paper-os` 是面向临床与科研人员的下一代文献全自动化处理系统。系统无缝串联文献下载（`paper-fetch`）与 Obsidian 知识库受管写入（`paper-notes`），通过 **源感知并发下载** 与 **两段式流水线 (Two-Phase Pipeline)**，在确保 Obsidian 单一写锁绝对安全的前提下，最大化利用子 Agent 并发处理耗时的视觉切图与长文解读。

[English Documentation (README.md)](README.md)

---

## 核心特性

1. **智能意图分流 (Intent Routing)**：
   - **纯下载**：调用 `paper-fetch` 下载文献（$N \ge 2$ 自动分发并行子 Agent；严格对科研通等敏感源实行排队限流）。绝不改动 Obsidian 库。
   - **纯导入**：对已有本地 PDF 运行两段式流水线（$N \ge 2$ 并发执行 Figure 解读与 300dpi 高清切图）。
   - **下载并导入**：端到端直通组合流水线，自动串联下载与导入。
2. **两段式流水线 (Two-Phase Pipeline · 零写锁冲突)**：
   - **准备期（主 Agent 串行）**：受管写锁下顺序执行 `paper-notes item create` 建条目，随后打包提交 MinerU 批量上传与统一轮询；
   - **精读期（子 Agent 并发 via `delegate_task`）**：分发 $N$ 个独立子 Agent，并发执行 PyMuPDF 字体检测、Sub-panel 切图与 `Figure解读_*.md` 撰写（仅写各篇专属目录，零写锁争抢）；
   - **收尾期（主 Agent 串行）**：校验产物后统一执行单次 `paper-notes index rebuild` 重建索引。
3. **Sub-panel 独立切图标准**：
   - 基于 PyMuPDF 字体级标签检测（如 Nature 系列的 `HelveticaNeueLTStd-Blk` / `GraphikNaturel-Black`），自动定位字母子图标签（`a`, `b`, `c`...）；
   - 自动切分独立子图，渲染 $\ge 300$ dpi 无损 PNG 嵌入笔记，杜绝整张大图粗暴堆砌。
4. **笔记属性规范**：
   - `Figure解读_<citation_key>.md` 强制包含属性 `title`（原论文完整英文标题）；
   - 包含规范的 `## Overview`（4–6 条加粗维度 bullet 紧凑叙述）。

---

## 目录结构

```text
paper-os/
├── SKILL.md                          # Hermes Skill 规范定义与触发引导
├── CONTEXT.md                        # 领域统一词表与定义边界
├── pyproject.toml
├── paper_os/
│   ├── cli.py                        # paper-os 命令行工具 (doctor, detect-subpanels)
│   └── subpanels.py                  # PyMuPDF 子图智能检测与 300dpi 渲染引擎
├── docs/
│   └── adr/
│       └── 0001-two-phase-parallel-pipeline.md  # 核心架构决策记录
├── references/
│   ├── figure_interpretation_spec.md # Figure 解读完整格式与视觉规范
│   ├── subagent_contract.md          # delegate_task 任务 Schema 与提示词模版
│   └── source_aware_concurrency.md   # 下载源并发控制与风控策略
├── scripts/
│   ├── batch_mineru.py               # MinerU 批量上传与轮询脚本
│   └── render_pdf_figure.py          # 300dpi 定位切图脚本
└── tests/                            # 自动化测试用例
```

---

## 快速使用

### 1. 环境诊断
```bash
paper-os doctor
```

### 2. 子图检测与切图
```bash
paper-os detect-subpanels <paper.pdf> --page 3 --output-dir ./figures --dpi 300
```

---

## 许可证

MIT License. Copyright (c) 2026 CaseyTso.
