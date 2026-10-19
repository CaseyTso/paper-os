# 子 Agent 调度契约 (Sub-Agent Execution Contract)

本文档定义了主 Agent 在 $N \ge 2$ 场景下调用 `delegate_task` 派发并行子 Agent 的任务规范、上下文注入与返回契约。

---

## 1. `paper-fetch` 并行下载任务契约

### 1.1 调度规则
- 当用户要求下载 $N \ge 2$ 篇文献时，主 Agent 解析标识符列表，为每篇文献启动一个独立子 Agent；
- **源感知限流**：若有多篇文献明确需要走 ableSci，调度器限制同时只能有 1 个子 Agent 请求 ableSci，其余在队列中等待或先尝试开放获取。

### 1.2 `delegate_task` 参数模板
```python
delegate_task(tasks=[
    {
        "goal": "Download academic paper PDF using paper-fetch CLI (default without Zotero sync)",
        "context": (
            "Identifier: '10.1038/s41586-026-10250-y'\n"
            "Output directory: '/path/to/downloads'\n"
            "Instructions:\n"
            "1. Run `paper-fetch fetch '10.1038/s41586-026-10250-y' --no-zotero --json`.\n"
            "2. Read the structured JSON stdout.\n"
            "3. If successful, report success and the absolute pdf_path.\n"
            "4. If challenge_required or authentication_required occurs, record the status, source, and exact URL.\n"
            "5. Return a strict JSON summary."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string"},
                "success": {"type": "boolean"},
                "source": {"type": "string"},
                "pdf_path": {"type": "string"},
                "zotero_item_key": {"type": "string"},
                "error": {"type": "string"},
                "action_needed": {"type": "string"}
            },
            "required": ["identifier", "success"]
        }
    }
])
```

---

## 2. `paper-notes` 并行 Figure 解读任务契约

### 2.1 调度规则
- 仅在主 Agent 串行完成 `paper-notes item create` 并准备好 `minerUmd_<citation_key>.md` 与 canonical 主 PDF 后派发；
- 每个子 Agent 独立负责一篇文献的 Sub-panel 高清切图与 `Figure解读_<citation_key>.md` 撰写；
- **子 Agent 绝对不调用涉及全局写锁的 CLI 命令**（如 `item create`, `card create`, `index rebuild`），只写入自己的文献目录。

### 2.2 `delegate_task` 参数模板
```python
delegate_task(tasks=[
    {
        "goal": "Generate complete Figure interpretation note and extract 300dpi sub-panels for paper",
        "context": (
            "Citation Key: xuProteasomeguidedHaemSignalling2026\n"
            "Vault Root: /path/to/vault\n"
            "Paper Directory: /path/to/vault/05 Literature/xuProteasomeguidedHaemSignalling2026\n"
            "Primary PDF: /path/to/vault/05 Literature/xuProteasomeguidedHaemSignalling2026/xuProteasomeguidedHaemSignalling2026.pdf\n"
            "MinerU MD: /path/to/vault/05 Literature/xuProteasomeguidedHaemSignalling2026/minerUmd_xuProteasomeguidedHaemSignalling2026.md\n"
            "Article Title: 'Proteasome-guided haem signalling directs CD8+ T cell exhaustion'\n"
            "Paper ID: '91663a1f-6ea6-40e0-a851-5688813ced77'\n\n"
            "MANDATORY INSTRUCTIONS:\n"
            "1. Read the article title and set frontmatter `title: \"Proteasome-guided haem signalling directs CD8+ T cell exhaustion\"`.\n"
            "2. Read minerUmd and interpret 100% of all main figures (Figure 1 through Figure M). Do NOT skip any figure.\n"
            "3. Run `python3 -m paper_os.cli detect-subpanels <PDF> --page <P> --output-dir <PaperDir>/figures --dpi 300` to extract sub-panels.\n"
            "4. Write ## Overview with 4-6 bullet points (**维度名**：).\n"
            "5. For each Figure, write narrative anchor and four dimensions (是什么/为什么/怎么做/发现) for every sub-panel.\n"
            "6. Embed individual sub-panel PNGs under each panel header.\n"
            "7. Ensure note size >= 15 KB.\n"
            "8. Save final file to `<PaperDir>/Figure解读_<CitationKey>.md`."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "citation_key": {"type": "string"},
                "success": {"type": "boolean"},
                "figure_note_path": {"type": "string"},
                "panels_extracted_count": {"type": "integer"},
                "error": {"type": "string"}
            },
            "required": ["citation_key", "success"]
        }
    }
])
```

---

## 3. 主 Agent 汇聚与展示规范

所有子 Agent 执行完毕后，主 Agent 打印统一汇总 Markdown 表格：

```markdown
| 文献 Key / 标识符 | 阶段 | 状态 | 产出物 / 详情 | 待处理操作 |
|---|---|---|---|---|
| `xuProteasome...2026` | 全流程 | ✅ 成功 | PDF + 20 Panels + Figure解读 | 无需操作 |
| `smithExample2026` | 下载 | ⚠️ 需验证 | Sci-Hub ALTCHA 验证码 | [打开验证链接](...) |
| `zhangSingle...2026` | 全流程 | ✅ 成功 | PDF + 12 Panels + Figure解读 | 无需操作 |
```
