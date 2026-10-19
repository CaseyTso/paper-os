# Two-Phase Parallel Pipeline for Literature Ingestion

## Context
When ingesting multiple papers concurrently, running full-lifecycle workers causes catastrophic lock contention because `paper-notes` enforces a strict, exclusive workspace write lock (`<vault>/.paper-notes/write.lock`) across all vault mutations (`item create`, `card create`, `rebuild_indexes`). Furthermore, the most time-consuming phase of ingestion is not metadata creation (sub-second), but MinerU OCR extraction (1–2 minutes) and LLM-driven Figure interpretation with 300dpi sub-panel rendering (1–3 minutes per paper).

## Decision
We adopt a Two-Phase Pipeline orchestrated by the parent agent:
1. **Preparation Phase (Parent Agent)**: Sequentially executes `item create` under the workspace write lock, followed by single-batch multi-file MinerU upload and unified polling.
2. **Concurrent Interpretation Phase (Child Agents via `delegate_task`)**: Spawns $N$ isolated child agents in parallel. Each child agent strictly operates on its paper's dedicated directory (`Figure解读_<citation_key>.md` and `figures/`), performing LLM analysis and sub-panel rendering without touching the vault write lock.
3. **Finalization Phase (Parent Agent)**: Collects child reports and executes a single lock-guarded `index rebuild`.

## Consequences
- Zero lock conflict risk without modifying the cooperative lock protocol in `paper_notes.locking`.
- Maximizes compute concurrency during the slowest stage (LLM reasoning and image cropping).
- Child agents are strictly decoupled from global vault state, making failure isolation and retry trivial.
