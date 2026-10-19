---
name: paper-os
description: Use when downloading literature or importing PDFs into Obsidian.
version: 1.2.0
author: CaseyTso
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [paper-os, literature, obsidian, mineru, figure-interpretation, multi-agent]
    related_skills: [academic-paper-reviewer, plan]
---

# paper-os（学术文献并行摄取与 Obsidian 深度知识体系）

`paper-os` 是面向科研人员的下一代文献摄取与 Obsidian 知识库受管编排系统。通过整合 **源感知并发下载 (Source-Aware Concurrency)** 与 **两段式并行流水线 (Two-Phase Pipeline)**，在保障 Obsidian 全局互斥写锁安全的前提下，充分发挥 Hermes 子 Agent（`delegate_task`）的并发推理与高清视觉切图算力。

> 📌 **核心归档与存储铁律（Canonical Storage & No-Zotero Default）**：
> 1. **默认不入 Zotero 库**：所有文献下载与导入流程**默认不写入 Zotero**（跳过 Zotero API 上传与条目创建，以 Obsidian 为唯一中心化学术知识库）。仅在用户显式要求「同步到 Zotero」时才追加 `--zotero`。
> 2. **PDF 统一落盘归档**：所有获取的文献 PDF 统一归档保存在 Obsidian 文献库对应条目的专属文件夹下：`<vault>/05 Literature/<citation_key>/<citation_key>.pdf`，严禁随意散落外部临时文件夹。

---

## When to Use

**适用触发**：
- 用户要求下载一篇或多篇文献（提供 DOI、PMID、URL、标题列表或文件）
- 用户要求将一个或多个本地 PDF 导入 Obsidian 并生成深度笔记与 Figure 解读
- 用户要求一键完成从「文献下载」到「Obsidian 结构化入库与 Figure 解读」的全流程
- 显式触发：`paper-os`、`/paper-os`、`下载文献`、`导入文献到obsidian`、`生成figure解读`

**不适用**：
- 宽泛的文献泛读或关键词文献调研（使用 `deep-research` 或 `research-lookup`）
- 单纯审阅已写好的论文初稿（使用 `academic-paper-reviewer`）

---

## 1. 意图识别与自动路由 (Intent Routing)

主 Agent 接收用户输入后，首先解析文献篇数 $N$ 及核心意图，自动分流至对应链路：

| 意图场景 | 用户典型指令 | 执行路径 | Obsidian / PDF 归档状态 |
|---|---|---|---|
| **场景 1: 纯下载** | 「帮我下载这 3 篇文献的 PDF」<br>「只下载文献，暂不做解读」 | 默认 `--no-zotero` 抓取 PDF。<br>受管建立条目并直接归档至各条目目录：`<vault>/05 Literature/<citation_key>/<citation_key>.pdf`。<br>$N=1$ 直接执行；$N \ge 2$ 子 Agent 并发抓取。 | PDF 存入 Obsidian 专属条目目录，生成条目元数据卡片，**不跑** MinerU 与 Figure 解读。不入 Zotero。 |
| **场景 2: 纯导入** | 「把下载目录里的这 5 个 PDF 导进 Obsidian」<br>「为这篇文献做 MinerU 转换和 Figure 解读」 | 调用 `paper-notes` 引擎。<br>$N=1$ 主 Agent 单篇执行；<br>$N \ge 2$ 启动 **Two-Phase Pipeline**。 | 受管写入 `05 Literature/`，产出条目、MD、300dpi Figure 与解读。 |
| **场景 3: 下载并导入** | 「下载这 4 篇论文并导入 Obsidian 做解读」<br>「一条龙处理这几个 DOI」 | **端到端组合流水线**：<br>先并发下载 PDF 并归档至条目目录（跳过 Zotero），自动无缝衔接 Two-Phase Pipeline。 | 全流程自动完成，最终重建索引与更新 MOC。 |

---

## 2. 并发规模与子 Agent 规则 (Concurrency & delegate_task)

- **$N < 2$ (单篇文献)**：当前主 Agent 顺序完整执行全部步骤，不调用 `delegate_task`，避免不必要的子 Agent 通信与冷启动开销。
- **$N \ge 2$ (多篇文献)**：自动开启并发处理。
  - **下载阶段**：主 Agent 解析标识符列表，分发子 Agent 运行 `paper-fetch fetch '<id>' --no-zotero --json`；遵循 **源感知限流**（Open Access 并发 3~5；ableSci 严格排队串行 1 并发）。
  - **导入阶段**：主 Agent 采用 **Two-Phase Pipeline**，仅在耗时最长的「Figure 解读与切图」阶段分发子 Agent。

> 🚨 **【主 Agent 负向绝对禁令（Operational Invariant）】**：
> 当 $N \ge 2$ 时，主 Agent **绝对禁止**在自身会话中直接通过脚本、write_file 或任何方式代写 `Figure解读_*.md`。
> 该解读任务必须且只能由 `delegate_task` 派发的独立上下文子 Agent 独占执行。主 Agent 代写将被视为严重违规与伪完成！

---

## 3. Two-Phase Pipeline 两段式流水线 (规避写锁冲突)

Obsidian 文献库共用全局单一互斥写锁（`<vault>/.paper-notes/write.lock`）。任何两个进程同时写元数据均会导致 `LockConflict` 报错崩溃。为此，本系统严格实行两段式流水线：

```
[Phase 1: 准备期 (主 Agent 串行/批处理)]
   │
   ├── 1.1 顺序执行 `paper-notes item create` (持锁建条目目录与权威元数据，各耗时 <0.5s)
   │
   └── 1.2 批量打包 MinerU 转换 (单 batch_id 顺序上传多 PDF，统一轮询，下载并清洗 minerUmd)
   │
   ▼
[Phase 2: 密集精读与切图期 (子 Agent 并发 via delegate_task 🚨 禁止主 Agent 代写)]
   │
   ├── Worker 1 (文献 A) ───┐
   ├── Worker 2 (文献 B) ───┼── 并发运行 PyMuPDF Sub-panel 高清切图 (300dpi PNG)
   └── Worker 3 (文献 C) ───┘   并发撰写 `Figure解读_*.md` (长文推理，各耗时 1-3 min)
                                【零锁冲突：仅写入各篇专属目录，绝不调用全局写锁 CLI】
   │
   ▼
[Phase 3: 自动化质量审计与收尾期 (主 Agent 串行)]
   │
   ├── 3.1 强制运行 `paper-os audit <vault>` 机器门禁校验 (100% 主图覆盖、体量 >=15KB、title属性、PNG实体)
   │       【若 audit 非零退出，严禁结案，必须针对性打回重做】
   │
   └── 3.2 统一持锁执行一次 `paper-notes index rebuild` 重建全局库索引
```

---

## 4. Figure 解读核心规范 (Sub-panel Extraction & Title Property)

所有生成的 `Figure解读_<citation_key>.md` 必须严格遵循以下医学与视觉规范（详见 `references/figure_interpretation_spec.md`）：

### 4.1 核心质量铁律与反作弊指标 (Anti-Cheat Invariants)
- **主图 100% 穷尽覆盖 (Figure Completeness)**：必须从头到尾解读 `minerUmd` 中出现的所有正文主图（Figure 1 到 Figure M）。**绝对禁止**只写前 1~2 张图！遗漏任何一张主图直接判定审计失败。
- **体量底线 (Size Floor)**：单篇解读正文必须 $\ge 15$ KB（严禁 2~3KB 的提纲式残卷）。
- **图片实体真实性 (Asset Integrity)**：每个 Panel 对应的 `![[<sha256>.png]]` 必须真实存在于 `<paper_dir>/figures/` 且字节数非零。

### 4.2 笔记属性 (Frontmatter) 强制要求
笔记头部 YAML 必须包含 **`title`** 属性，内容为原论文完整英文标题：
```yaml
---
title: "Proteasome-guided haem signalling directs CD8+ T cell exhaustion"
date: 2026-10-18
source:
  - "[[minerUmd_xuProteasomeguidedHaemSignalling2026]]"
citation_key: xuProteasomeguidedHaemSignalling2026
paper_id: 91663a1f-6ea6-40e0-a851-5688813ced77
---
```

### 4.2 篇首引用与 Overview
- 紧随 Frontmatter 之后必须包含简洁引用：`> **FirstAuthor et al., Year, Journal** | DOI: [10.xxxx/xxxx](https://...)`
- 必须包含 `## Overview`：**4–6 条** `- **维度名**：` bullet（研究背景、核心假说、主要方法、关键机制、临床意义），禁止大段叙述；末尾附一句话 `**核心信号轴**`。

### 4.3 独立 Sub-panel 300dpi 切图
- **唯一图源**：从主 PDF 通过 `paper-os detect-subpanels <PDF> --page <P> --output-dir <PaperDir>/figures --dpi 300` 切出 $\ge 300$ dpi 无损 PNG；
- **子图粒度**：**每个字母子图（Panel a, Panel b, Panel c...）必须单独切出独立的 PNG 文件嵌入对应面板**，禁止整张大图粗暴堆砌；
- **排版与四维分析**：
  ```markdown
  ## Figure 1. <图标题>
  > **叙事位置**：一句话说明该图在全文中要回答的核心科学问题。

  **Panel A — <简明面板标题>**
  ![[<sha256>.png]]
  > 原文图注核心片断

  - **是什么**：展示的指标或技术类型。
  - **为什么**：实验目的。
  - **怎么做**：实验设计，**必须明确标明实验模型/样本来源**（如：**模型：人 CD8+ T 细胞体外分化亚群**）。
  - **发现**：客观数据结论与推论。
  ```

---

## 5. 阻断隔离与汇报规范 (Failure Isolation)

子 Agent 无法在中途弹窗与用户交互。当遇到验证码或网络阻断时，子 Agent 绝不阻塞其他任务，直接返回结构化失败状态。主 Agent 在批次全部结束后输出汇总表格：

```markdown
### 批量文献处理完成报告

| 序号 | 文献 Key / 标识符 | 阶段 | 状态 | 产出详情 | 用户后续操作 |
|---|---|---|---|---|---|
| 1 | `xuProteasome...2026` | 全流程 | ✅ 成功 | PDF + 20 Panels + Figure解读 | 无需操作 |
| 2 | `smithExample2026` | 下载 | ⚠️ 需验证 | Sci-Hub ALTCHA 验证码 | [点击打开验证链接](https://...) |
| 3 | `chenTargeting2026` | 全流程 | ✅ 成功 | PDF + 14 Panels + Figure解读 | 无需操作 |
```

---

## 6. 核心命令与工具速查

- **环境诊断**：
  ```bash
  paper-os doctor
  ```
- **质量审计与完备性门禁**：
  ```bash
  paper-os audit "<vault>" [--key "<citation_key>"]
  ```
- **单篇/多篇下载**：
  ```bash
  paper-fetch fetch '<identifier>' --json
  # 注：默认已配置为不入 Zotero，若需同步到 Zotero 请显式追加 --zotero
  ```
- **Obsidian 条目创建 (受管写锁)**：
  ```bash
  paper-notes item create --vault "<vault>" --doi "<doi>" --pdf "<pdf_path>"
  ```
- **Sub-panel 高清自动切图**：
  ```bash
  paper-os detect-subpanels "<pdf_path>" --page 3 --output-dir "<paper_dir>/figures" --dpi 300
  ```
- **全局索引重建 (受管写锁)**：
  ```bash
  paper-notes index rebuild --vault "<vault>"
  ```

---

## 7. 验收清单 (Verification Checklist)

- [ ] 默认不入 Zotero 库，以 Obsidian `<vault>/05 Literature/<citation_key>/<citation_key>.pdf` 为统一归档载体
- [ ] $N \ge 2$ 时自动派发 `delegate_task` 并行执行，子 Agent 互不抢占写锁
- [ ] `Figure解读_*.md` Frontmatter 必定包含 `title` 属性（原论文标题）
- [ ] 文首包含规范的 `## Overview`（4–6 条加粗维度 bullet）
- [ ] 图像严格为 300dpi Sub-panel 单独切分，禁止整图糊弄
- [ ] 批次完成后向用户呈报结构化成功/失败汇总表格
