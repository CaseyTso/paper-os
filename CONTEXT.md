# Paper Workflow Architecture

Architecture and domain language for parallel academic literature acquisition and Obsidian-native note generation.

## Language

### Core Subsystems

**Paper Fetch**:
The acquisition subsystem that resolves academic identifiers (DOI, PMID, URL) to locate and download canonical multi-page PDFs, optionally registering them in Zotero.
_Avoid_: PDF downloader, paper scraper, literature crawler

**Paper Notes**:
The Obsidian-native literature management subsystem that maintains persistent Markdown records, MinerU conversions, Figure interpretations, and vault indexes under `05 Literature/`.
_Avoid_: Obsidian importer, note generator, vault writer

### Parallel Orchestration

**Two-Phase Pipeline**:
An orchestration architecture where the parent agent sequentially executes lock-guarded vault mutations (`item create`, MinerU batching, `index rebuild`), while spawned child agents concurrently execute compute-heavy Figure interpretations and sub-panel rendering.
_Avoid_: Full-lifecycle worker, concurrent item creation, uncoordinated sub-agents

**Source-Aware Concurrency**:
A download scheduling policy that permits high concurrency for open-access and institutional sources while strictly serializing requests to session-bound or WAF-sensitive providers (such as ableSci).
_Avoid_: Unbounded parallel fetch, brute-force concurrency

**Sub-panel Extraction**:
The figure processing standard where individual lettered sub-panels (e.g., Fig 1a, 1b) are cropped as dedicated 300dpi lossless PNGs using font-level bounding box detection and embedded individually into notes.
_Avoid_: Monolithic figure crop, full-page screenshot, single-image figure
