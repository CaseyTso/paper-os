"""CLI entry point for paper-os."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import __version__
from .audit import audit_single_paper, audit_vault_literature
from .subpanels import extract_subpanels, render_bbox_png


def cmd_version(args: argparse.Namespace) -> int:
    payload = {"version": __version__, "system": "paper-os"}
    if args.json:
        print(json.dumps(payload))
    else:
        print(f"paper-os version {__version__}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = []

    # 1. paper-fetch CLI
    pf_path = shutil.which("paper-fetch")
    checks.append({
        "component": "paper-fetch",
        "status": "ok" if pf_path else "missing",
        "detail": pf_path or "paper-fetch CLI not found in PATH",
    })

    # 2. paper-notes CLI
    pn_path = shutil.which("paper-notes")
    checks.append({
        "component": "paper-notes",
        "status": "ok" if pn_path else "missing",
        "detail": pn_path or "paper-notes CLI not found in PATH",
    })

    # 3. MinerU Token
    mineru_token = os.environ.get("MINERU_TOKEN")
    mineru_cfg = Path.home() / "Library/Application Support/paper-notes/config.json"
    has_token = bool(mineru_token)
    if not has_token and mineru_cfg.exists():
        try:
            with open(mineru_cfg, encoding="utf-8") as f:
                cfg_data = json.load(f)
                has_token = bool(cfg_data.get("mineru_key"))
        except Exception:
            pass

    checks.append({
        "component": "mineru_token",
        "status": "ok" if has_token else "warning",
        "detail": "token detected" if has_token else "MINERU_TOKEN not set; needed for PDF->MD conversion",
    })

    # 4. PyMuPDF (fitz)
    try:
        import fitz  # noqa: F401
        has_pymupdf = True
    except ImportError:
        has_pymupdf = False

    checks.append({
        "component": "pymupdf",
        "status": "ok" if has_pymupdf else "error",
        "detail": "installed" if has_pymupdf else "pymupdf package missing",
    })

    overall_ok = all(c["status"] == "ok" for c in checks)

    if args.json:
        print(json.dumps({"success": overall_ok, "checks": checks}, indent=2))
    else:
        print(f"paper-os doctor report (v{__version__}):")
        for c in checks:
            icon = "✅" if c["status"] == "ok" else ("⚠️" if c["status"] == "warning" else "❌")
            print(f"  {icon} {c['component']}: {c['detail']}")

    return 0 if overall_ok else 1


def cmd_detect_subpanels(args: argparse.Namespace) -> int:
    try:
        results = extract_subpanels(
            pdf_path=args.pdf,
            page_number=args.page,
            output_dir=args.output_dir,
            caption_text_hint=args.caption_hint,
            dpi=args.dpi,
        )
        if args.json:
            print(json.dumps({"success": True, "count": len(results), "panels": results}))
        else:
            print(f"Extracted {len(results)} panels to {args.output_dir}:")
            for p in results:
                print(f"  Panel {p['panel']}: {p['embed']} ({p['width']}x{p['height']} px)")
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"success": False, "error": str(exc)}))
        else:
            print(f"Error extracting subpanels: {exc}", file=sys.stderr)
        return 1


def cmd_render_figure(args: argparse.Namespace) -> int:
    try:
        import fitz
        doc = fitz.open(args.pdf)
        if args.page < 1 or args.page > len(doc):
            raise ValueError(f"Page {args.page} out of bounds")
        page = doc[args.page - 1]

        bbox_parts = [float(x) for x in args.bbox.split(",")]
        if len(bbox_parts) != 4:
            raise ValueError("--bbox must have 4 coordinates: x0,y0,x1,y1")

        result = render_bbox_png(page, bbox_parts, args.output_dir, dpi=args.dpi)
        if args.json:
            print(json.dumps({"success": True, **result}))
        else:
            print(f"Rendered figure to {result['path']}")
            print(f"Obsidian Embed: {result['embed']}")
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"success": False, "error": str(exc)}))
        else:
            print(f"Error rendering figure: {exc}", file=sys.stderr)
        return 1


def cmd_audit(args: argparse.Namespace) -> int:
    try:
        keys = [args.key] if args.key else None
        res = audit_vault_literature(args.vault, keys=keys)

        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\n📋 paper-os audit report (Vault: {args.vault})")
            print(f"Total: {res['total_audited']} | Passed: {res['passed_count']} | Failed: {res['failed_count']}\n")

            for p in res["papers"]:
                icon = "✅" if p["passed"] else "❌"
                m = p["metrics"]
                kb = m.get("note_kb", 0)
                figs = m.get("interpreted_main_figures", [])
                embeds = m.get("image_embeds_count", 0)
                title = m.get("title", "")[:35]
                print(f"{icon} {p['citation_key']} ({kb} KB, {len(figs)} Figs, {embeds} PNGs)")
                if title:
                    print(f"   Title: \"{title}...\"")
                for err in p["errors"]:
                    print(f"   ❌ Error: {err}")
                for warn in p["warnings"]:
                    print(f"   ⚠️ Warning: {warn}")

        return 0 if res["passed"] else 1
    except Exception as exc:
        if args.json:
            print(json.dumps({"passed": False, "error": str(exc)}))
        else:
            print(f"Audit failure: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--json", action="store_true", help="output structured JSON")

    parser = argparse.ArgumentParser(
        prog="paper-os",
        description="Autonomous literature acquisition & Obsidian orchestrator",
        parents=[parent_parser],
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # version
    p_ver = subparsers.add_parser("version", help="show version", parents=[parent_parser])
    p_ver.set_defaults(func=cmd_version)

    # doctor
    p_doc = subparsers.add_parser("doctor", help="check runtime dependencies", parents=[parent_parser])
    p_doc.set_defaults(func=cmd_doctor)

    # detect-subpanels
    p_sub = subparsers.add_parser(
        "detect-subpanels",
        help="detect and extract subpanels from a PDF page",
        parents=[parent_parser],
    )
    p_sub.add_argument("pdf", help="path to PDF file")
    p_sub.add_argument("--page", type=int, required=True, help="1-based page number")
    p_sub.add_argument("--output-dir", required=True, help="directory to write PNGs")
    p_sub.add_argument("--caption-hint", default=None, help="caption search string to bound bottom of figure")
    p_sub.add_argument("--dpi", type=int, default=300, help="rendering DPI (>=300)")
    p_sub.set_defaults(func=cmd_detect_subpanels)

    # render-figure
    p_ren = subparsers.add_parser(
        "render-figure",
        help="render a specific bbox region as 300dpi PNG",
        parents=[parent_parser],
    )
    p_ren.add_argument("pdf", help="path to PDF file")
    p_ren.add_argument("--page", type=int, required=True, help="1-based page number")
    p_ren.add_argument("--bbox", required=True, help="x0,y0,x1,y1 in PDF points")
    p_ren.add_argument("--output-dir", required=True, help="directory to write PNG")
    p_ren.add_argument("--dpi", type=int, default=300, help="rendering DPI (>=300)")
    p_ren.set_defaults(func=cmd_render_figure)

    # audit
    p_aud = subparsers.add_parser(
        "audit",
        help="audit and verify note completeness and quality",
        parents=[parent_parser],
    )
    p_aud.add_argument("vault", help="path to Obsidian vault root")
    p_aud.add_argument("--key", default=None, help="specific citation key to audit (default: audit all)")
    p_aud.set_defaults(func=cmd_audit)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
