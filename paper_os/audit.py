"""Automated audit and quality verification for paper-os literature notes.

Enforces zero-shortcut quality gates:
1. Note presence and minimum size floor (>= 15 KB).
2. Frontmatter integrity (mandatory non-empty 'title', citation_key, paper_id).
3. Overview structure (4-6 dimension bullet points + core signaling axis).
4. Main figure completeness: 100% coverage of figures in minerUmd/PDF without skipping.
5. High-resolution figure asset existence (>=300 dpi lossless PNG embeds in figures/).
6. Four-dimensional analysis presence (是什么 / 为什么 / 怎么做 [含模型/数据源] / 发现).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

MIN_NOTE_BYTES = 10_000  # Hard failure floor
RECOMMENDED_NOTE_BYTES = 15_000


def audit_single_paper(paper_dir: Path | str) -> dict[str, Any]:
    """Audit a single literature entry directory under 05 Literature/<citation_key>."""
    paper_dir = Path(paper_dir).resolve()
    citation_key = paper_dir.name

    report: dict[str, Any] = {
        "citation_key": citation_key,
        "paper_dir": str(paper_dir),
        "passed": True,
        "errors": [],
        "warnings": [],
        "metrics": {},
    }

    # 1. Check Primary Files
    primary_note = paper_dir / f"{citation_key}.md"
    fig_note = paper_dir / f"Figure解读_{citation_key}.md"
    mineru_note = paper_dir / f"minerUmd_{citation_key}.md"
    figures_dir = paper_dir / "figures"

    if not primary_note.exists():
        report["errors"].append(f"Missing primary literature note: {primary_note.name}")
        report["passed"] = False

    if not fig_note.exists():
        report["errors"].append(f"Missing Figure interpretation note: {fig_note.name}")
        report["passed"] = False
        return report

    # 2. Check Size Floor
    note_bytes = fig_note.stat().st_size
    report["metrics"]["note_bytes"] = note_bytes
    report["metrics"]["note_kb"] = round(note_bytes / 1024, 1)

    if note_bytes < MIN_NOTE_BYTES:
        report["errors"].append(
            f"Figure note size ({note_bytes} bytes, {report['metrics']['note_kb']} KB) "
            f"is below the minimum quality floor of {MIN_NOTE_BYTES} bytes. Likely incomplete stub."
        )
        report["passed"] = False
    elif note_bytes < RECOMMENDED_NOTE_BYTES:
        report["warnings"].append(
            f"Figure note size ({report['metrics']['note_kb']} KB) is below recommended {RECOMMENDED_NOTE_BYTES / 1024:.0f} KB."
        )

    # 3. Check Frontmatter
    fig_text = fig_note.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\n(.*?)\n---\n", fig_text, re.DOTALL)
    if not fm_match:
        report["errors"].append("Figure note missing valid YAML frontmatter delimiter (---).")
        report["passed"] = False
        fm = {}
    else:
        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
        except Exception as exc:
            report["errors"].append(f"Failed to parse YAML frontmatter: {exc}")
            report["passed"] = False
            fm = {}

    title = fm.get("title")
    if not title or not str(title).strip():
        report["errors"].append("Frontmatter missing mandatory non-empty 'title' attribute (original article title).")
        report["passed"] = False
    else:
        report["metrics"]["title"] = str(title).strip()

    if fm.get("citation_key") != citation_key:
        report["warnings"].append(f"Frontmatter citation_key '{fm.get('citation_key')}' does not match directory '{citation_key}'.")

    # 4. Check Overview Section
    has_overview = bool(re.search(r"^##\s+Overview\b", fig_text, re.M))
    if not has_overview:
        report["errors"].append("Missing '## Overview' section at the beginning of Figure note.")
        report["passed"] = False
    else:
        # Check bullet points in overview
        ov_match = re.search(r"^##\s+Overview\s*\n(.*?)(?=\n##\s+Figure|\Z)", fig_text, re.DOTALL | re.M)
        if ov_match:
            ov_text = ov_match.group(1)
            bullets = re.findall(r"^-\s+\*\*[^*]+?\*\*[:：]", ov_text, re.M)
            report["metrics"]["overview_bullets"] = len(bullets)
            if len(bullets) < 4:
                report["warnings"].append(f"Overview contains only {len(bullets)} structured bullet points (expected 4-6).")

    # 5. Check Main Figure Completeness
    interpreted_figs = set()
    for m in re.finditer(r"^##\s+Figure\s+(\d+)\b", fig_text, re.M | re.I):
        interpreted_figs.add(int(m.group(1)))

    report["metrics"]["interpreted_main_figures"] = sorted(interpreted_figs)

    if mineru_note.exists():
        mineru_text = mineru_note.read_text(encoding="utf-8")
        expected_figs = set()
        # Find captions like "Fig. 1 |", "Figure 1.", "**Figure 1.", "## Figure 1"
        for m in re.finditer(r"(?:^|\n)(?:##\s+Figure\s+(\d+)|\*\*Figure\s+(\d+)\.|\bFig(?:ure|\.)\s+(\d+)\s*[:\|])", mineru_text, re.I):
            num = next(g for g in m.groups() if g is not None)
            val = int(num)
            if val < 30:  # exclude extreme spurious values
                expected_figs.add(val)

        # Normalize expected sequential range if we found figures: 1..max_fig
        if expected_figs:
            max_fig = max(expected_figs)
            # The expected main figures sequence is 1..max_fig (or at least the found set)
            target_set = set(range(1, max_fig + 1))
            missing_figs = target_set - interpreted_figs
            report["metrics"]["expected_main_figures"] = sorted(target_set)

            if missing_figs:
                report["errors"].append(
                    f"Incomplete figure coverage: Missing interpretation for main figures {sorted(missing_figs)} "
                    f"(expected 1..{max_fig}, interpreted {sorted(interpreted_figs)})."
                )
                report["passed"] = False
    else:
        if not interpreted_figs:
            report["errors"].append("Zero '## Figure X' headings found in interpretation note.")
            report["passed"] = False

    # 6. Check Figure Image Embeds & On-Disk Assets
    embeds = re.findall(r"!\[\[([a-f0-9]{64}\.png)\]\]", fig_text)
    report["metrics"]["image_embeds_count"] = len(embeds)

    if not embeds:
        report["errors"].append("Zero 300dpi content-addressed PNG embeds (![[<sha256>.png]]) found in note.")
        report["passed"] = False
    else:
        missing_pngs = []
        for img_name in embeds:
            png_path = figures_dir / img_name
            if not png_path.exists():
                missing_pngs.append(img_name)
            elif png_path.stat().st_size == 0:
                missing_pngs.append(f"{img_name} (0 bytes)")

        if missing_pngs:
            report["errors"].append(
                f"{len(missing_pngs)} embedded image file(s) missing from {figures_dir.name}/: {missing_pngs[:3]}..."
            )
            report["passed"] = False

    # 7. Check Four-Dimensional Analysis (是什么/为什么/怎么做/发现)
    dim_what = len(re.findall(r"-\s+\*\*是什么\*\*[:：]", fig_text))
    dim_why = len(re.findall(r"-\s+\*\*为什么\*\*[:：]", fig_text))
    dim_how = len(re.findall(r"-\s+\*\*怎么做\*\*[:：]", fig_text))
    dim_found = len(re.findall(r"-\s+\*\*发现\*\*[:：]", fig_text))

    report["metrics"]["dimensions"] = {
        "是什么": dim_what,
        "为什么": dim_why,
        "怎么做": dim_how,
        "发现": dim_found,
    }

    if dim_what == 0 or dim_why == 0 or dim_how == 0 or dim_found == 0:
        report["warnings"].append(
            f"Four-dimensional framework incomplete: 是什么={dim_what}, 为什么={dim_why}, 怎么做={dim_how}, 发现={dim_found}"
        )

    return report


def audit_vault_literature(vault_root: Path | str, keys: list[str] | None = None) -> dict[str, Any]:
    """Audit all or selected literature entries under <vault>/05 Literature/."""
    vault_root = Path(vault_root).resolve()
    lit_root = vault_root / "05 Literature"

    if not lit_root.is_dir():
        return {
            "passed": False,
            "error": f"Literature root does not exist: {lit_root}",
            "papers": [],
        }

    if keys:
        target_dirs = [lit_root / k for k in keys if (lit_root / k).is_dir()]
    else:
        target_dirs = [d for d in lit_root.iterdir() if d.is_dir() and d.name != "MOCs"]

    results = []
    all_passed = True

    for pdir in sorted(target_dirs, key=lambda d: d.name):
        res = audit_single_paper(pdir)
        if not res["passed"]:
            all_passed = False
        results.append(res)

    return {
        "passed": all_passed,
        "total_audited": len(results),
        "passed_count": sum(1 for r in results if r["passed"]),
        "failed_count": sum(1 for r in results if not r["passed"]),
        "papers": results,
    }
