# paper-os

Autonomous literature acquisition and Obsidian-native knowledge system orchestrator.

`paper-os` bridges academic paper acquisition (`paper-fetch`) and structured Obsidian vault integration (`paper-notes`). By combining **Source-Aware Concurrency** for downloads and a **Two-Phase Pipeline** for Obsidian ingestion, it maximizes parallel compute through Hermes child agents while strictly respecting the global workspace write lock on your Obsidian vault.

[中文文档 (README.zh-CN.md)](README.zh-CN.md)

---

## Key Features

1. **Intelligent Intent Routing**:
   - **Download only**: Fetches papers via `paper-fetch` ($N \ge 2$ spawns parallel sub-agents; respects ableSci WAF and rate limits). Never modifies Obsidian.
   - **Import only**: Ingests local PDFs into Obsidian via the Two-Phase Pipeline ($N \ge 2$ parallelizes Figure interpretation and 300dpi sub-panel rendering).
   - **Download & Import**: End-to-end pipeline that downloads PDFs and seamlessly feeds them into Obsidian notes.
2. **Two-Phase Pipeline (Lock-Safe Concurrency)**:
   - **Phase 1 (Parent Agent)**: Sequentially executes `paper-notes item create` under the vault lock, then submits multi-file batch to MinerU.
   - **Phase 2 (Child Agents)**: Spawns $N$ concurrent workers to perform LLM Figure interpretation and 300dpi sub-panel visual rendering into per-paper directories (zero lock contention).
   - **Phase 3 (Parent Agent)**: Rebuilds global library indexes with a single atomic operation.
3. **Sub-panel 300dpi Extraction**:
   - Uses PyMuPDF font-level detection (e.g. Nature's `GraphikNaturel-Black` / `HelveticaNeueLTStd-Blk`) to isolate individual panel letters (`a`, `b`, `c`).
   - Renders each panel as a lossless $\ge 300$ dpi PNG embedded into notes.
4. **Strict Note Properties**:
   - Every `Figure解读_<citation_key>.md` enforces a mandatory `title` property containing the full original article title.
   - Requires a concise `## Overview` with 4–6 structured bullet points.

---

## Directory Structure

```text
paper-os/
├── SKILL.md                          # Hermes agent skill definition
├── CONTEXT.md                        # Domain language and glossary
├── pyproject.toml
├── paper_os/
│   ├── cli.py                        # CLI entry points (doctor, detect-subpanels)
│   └── subpanels.py                  # PyMuPDF sub-panel detection & renderer
├── docs/
│   └── adr/
│       └── 0001-two-phase-parallel-pipeline.md
├── references/
│   ├── figure_interpretation_spec.md # High-res sub-panel & note specification
│   ├── subagent_contract.md          # delegate_task schema & prompt templates
│   └── source_aware_concurrency.md   # Download rate limiting & fallback policy
├── scripts/
│   ├── batch_mineru.py               # Batch MinerU upload/poll orchestrator
│   └── render_pdf_figure.py          # Standalone 300dpi figure renderer
└── tests/
```

---

## Quick Start

### 1. Doctor & Verification
```bash
paper-os doctor
```

### 2. Sub-panel Detection & Extraction
```bash
paper-os detect-subpanels <paper.pdf> --page 3 --output-dir ./figures --dpi 300
```

---

## License

MIT License. Copyright (c) 2026 CaseyTso.
