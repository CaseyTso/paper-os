# Figure 解读核心规范 (Figure Interpretation Specification)

本文档是 `paper-os` 中 `Figure解读_<citation_key>.md` 的唯一权威撰写与视觉规范。

---

## 1. Frontmatter 规范 (必填属性)

每个 Figure 解读文件头部必须包含 YAML frontmatter，且**必须包含 `title` 属性（原文完整标题）**：

```yaml
---
title: "Full Original Article Title"
date: YYYY-MM-DD
source:
  - "[[minerUmd_<citation_key>]]"
citation_key: <citation_key>
paper_id: <paper_id>
---
```

- **`title`** (强制必填)：论文的完整英文原始标题（用于 Obsidian Dataview / 知识图谱检索与展示）。
- **`citation_key`**：与文献主条目及目录名完全一致的唯一键（例如 `xuProteasomeguidedHaemSignalling2026`）。
- **`source`**：指向同目录的 MinerU 全文清洗笔记 `[[minerUmd_<citation_key>]]`。
- **`paper_id`**：文献条目的 UUID（若已有主条目，从主条目 frontmatter 继承；若无则生成唯一 UUID）。

---

## 2. 篇首文献元信息 Callout

Frontmatter 之后紧跟一行简洁的学术引用 Callout，格式严格如下：

```markdown
> **FirstAuthor et al., Year, Journal** | DOI: [10.xxxx/xxxx](https://doi.org/10.xxxx/xxxx)
```

---

## 3. Overview 结构（文首必填）

在文献元信息之后、第一张 Figure 之前，必须编写 `## Overview`：

```markdown
## Overview

- **研究背景与问题**：... (1–2句紧凑说明临床/科学瓶颈)
- **核心假说与脉络**：... (问题提出 → 实验思路 → 分析主线)
- **主要方法与模型**：... (实验体系、主要数据源、关键分析方法)
- **核心机制与产物**：... (关键通路、调控轴或生物标志物)
- **转化价值与意义**：... (临床指导价值或未来方向)

**核心信号轴**：分子A → 途径B → 表型C (提炼一句话关键轴线)
```

**写作铁律**：
- 严格以 4–6 条 `- **维度名**：` bullet 组织；
- **禁止写成长篇大段**，读者只扫 Overview 即可在 1 分钟内看懂全文脉络；
- 术语准确，中文叙述，专有名词与基因缩写保留英文。

---

## 4. Sub-panel 独立切图与解读规范（🚨 核心视觉标准）

### 4.1 图片来源与 Sub-panel 粒度
- **唯一来源**：插图**必须**来自 canonical 主 PDF（`<paper_dir>/<citation_key>.pdf`），通过 `paper-os detect-subpanels` 或 PyMuPDF 脚本以 $\ge 300$ dpi 无损 PNG 渲染到 `<paper_dir>/figures/<sha256>.png`。
- **独立切图**：**每个 sub-panel（如 a, b, c...）必须单独切出独立的 PNG 文件并在该 panel 下嵌入**，禁止将整张大图作为单图粗暴堆砌。
- **定位依据**：
  - Nature / Cell / Science 等主流期刊正文中，每个 panel 标签（如 `a`, `b`, `c`）均有专属粗体/黑体字阶（例如 Nature 系的 `HelveticaNeueLTStd-Blk` 或 `GraphikNaturel-Black`）。通过 PyMuPDF 提取其坐标，精准计算切图 bbox。
  - 若遇极复杂紧密排版无法可靠切分单个 panel，可成对切分（如 `Panels C-D`），或在确保清晰度前提下回退至整图；**绝不得猜裁或张冠李戴**。

### 4.2 排版骨架

对每一张 Figure（主图与补充图均逐图排版）：

```markdown
## Figure X. <图标题>

> **叙事位置**：一句话说明该图在全文中要回答的问题与逻辑承接。

**Panel A — <简明面板标题>**
![[<sha256>.png]]
> 原文图注核心片断（英文，逐字或关键截取）

- **是什么**：简述该图展示的图表类型与指标（如：各亚群 scRNA-seq 基因集评分）。
- **为什么**：实验目的（如：验证 T 细胞耗竭是否伴随蛋白酶体活性改变）。
- **怎么做**：实验方法与技术平台。**明确标明实验模型/样本来源**（如：**模型：健康人 CD8+ T 细胞体外分化亚群** 或 **数据来源：黑色素瘤 TIL scRNA-seq 公共数据集**）。
- **发现**：该图得出的确凿数据结论与生物学/临床推论。

**Panel B — <简明面板标题>**
...
```

---

## 5. 补充图 (Supplemental Figures) 规范

- 补充图**与主图使用相同格式逐图排版**（`## Figure S1...`），逐 panel 嵌入高清 PNG 与四维解读，严禁缩减为死板表格。
- **主文 PDF 无完整 SM 图注时**：部分期刊（如 Science）主 PDF 不含详细 Supplementary 图注。此时：
  - 尽量从正文 Results 与 Methods 中定位该图描述；
  - 在图注引用区注明：*主 PDF 无完整 SM 图注；此 Legend 据正文引用与 Methods 归纳，非出版社逐字图注*；
  - 严禁空缺或伪造图注。

---

## 6. 自检清单

- [ ] Frontmatter 包含 `title` 属性且为原论文完整标题
- [ ] 顶部包含 `FirstAuthor et al.` 引用与 DOI 链接
- [ ] `## Overview` 包含 4–6 条加粗维度 bullet，无大段冗余叙述
- [ ] 每个 sub-panel 均有独立的 `![[<sha256>.png]]` 300dpi 嵌入
- [ ] 四维分析（是什么/为什么/怎么做/发现）完整，且「怎么做」中明确标明了动物/细胞模型或数据来源
- [ ] 全文体量通常 $\ge 10$ KB，无空占位符
