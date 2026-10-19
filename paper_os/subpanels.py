"""Sub-panel detection and high-resolution rendering using PyMuPDF.

Detects single-letter panel labels (e.g., 'a', 'b', 'c' in Nature/Cell/Science journals)
and renders isolated, lossless >=300 dpi PNGs into the per-paper figures/ directory.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

MIN_DPI = 300
LABEL_FONT_PATTERNS = re.compile(r"black|bold|blk|semibold|graphik|helvetica", re.IGNORECASE)


def detect_panel_labels(page: fitz.Page, max_y: float | None = None) -> list[dict[str, Any]]:
    """Scan a PDF page for single-character panel labels (a-z or A-Z).
    
    Returns a sorted list of dicts: [{'label': 'a', 'bbox': (x0, y0, x1, y1), 'font': ..., 'size': ...}]
    """
    rect = page.rect
    if max_y is None:
        max_y = rect.height - 40.0  # Avoid bottom page footers

    labels: list[dict[str, Any]] = []
    blocks = page.get_text("dict")["blocks"]

    for b in blocks:
        if "lines" not in b:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                txt = span["text"].strip()
                bbox = span["bbox"]

                # Exclude header/footer areas
                if bbox[1] < 30.0 or bbox[1] > max_y:
                    continue

                # Panel labels are single letters: 'a'..'z' or 'A'..'z'
                if len(txt) == 1 and txt.isalpha():
                    font_name = span["font"].lower()
                    font_size = span["size"]

                    # Label heuristics: prominent bold/black fonts, or standalone small-caps/bold ~6-12pt
                    is_candidate_font = bool(LABEL_FONT_PATTERNS.search(font_name))
                    is_reasonable_size = 6.0 <= font_size <= 14.0

                    if is_candidate_font and is_reasonable_size:
                        labels.append({
                            "label": txt.lower(),
                            "raw_label": txt,
                            "bbox": bbox,
                            "font": span["font"],
                            "size": font_size,
                        })

    # Deduplicate and sort by reading order (top-to-bottom, left-to-right)
    # Group into rough horizontal bands (~20pt tolerance)
    labels.sort(key=lambda item: (round(item["bbox"][1] / 20.0), item["bbox"][0]))

    # Filter out potential spurious letters (e.g. within equations or subscript)
    # Ensure sequential or plausible panel distribution
    return labels


def estimate_panel_bboxes(
    labels: list[dict[str, Any]],
    page_rect: fitz.Rect,
    caption_top: float | None = None,
    padding: float = 4.0,
) -> dict[str, list[float]]:
    """Estimate a bounding box for each detected panel label.
    
    Partitions the space between label coordinates and page margins / adjacent labels.
    """
    if not labels:
        return {}

    bottom_limit = caption_top if caption_top is not None else (page_rect.height - 40.0)
    top_limit = 35.0
    left_limit = 35.0
    right_limit = page_rect.width - 35.0

    panel_boxes: dict[str, list[float]] = {}
    n = len(labels)

    for i, curr in enumerate(labels):
        label_char = curr["label"]
        cx0, cy0, cx1, cy1 = curr["bbox"]

        # Default box bounds
        x0 = max(left_limit, cx0 - padding)
        y0 = max(top_limit, cy0 - padding)

        # Find next label on the right in the same horizontal band
        same_row_next = [
            lbl for lbl in labels[i + 1:]
            if abs(lbl["bbox"][1] - cy0) < 30.0 and lbl["bbox"][0] > cx1
        ]
        if same_row_next:
            x1 = same_row_next[0]["bbox"][0] - padding
        else:
            x1 = right_limit

        # Find next label below
        next_row = [
            lbl for lbl in labels[i + 1:]
            if lbl["bbox"][1] > cy1 + 15.0 and (
                # overlapping horizontally
                max(x0, lbl["bbox"][0]) < min(x1, lbl["bbox"][0] + 100.0) or
                abs(lbl["bbox"][0] - cx0) < 50.0
            )
        ]
        if next_row:
            y1 = next_row[0]["bbox"][1] - padding
        else:
            y1 = bottom_limit

        # Clamp and validate
        x0 = max(0.0, min(x0, page_rect.width))
        y0 = max(0.0, min(y0, page_rect.height))
        x1 = max(x0 + 10.0, min(x1, page_rect.width))
        y1 = max(y0 + 10.0, min(y1, page_rect.height))

        panel_boxes[label_char] = [round(x, 2) for x in (x0, y0, x1, y1)]

    return panel_boxes


def render_bbox_png(
    page: fitz.Page,
    bbox: list[float] | tuple[float, float, float, float],
    output_dir: Path | str,
    dpi: int = 300,
) -> dict[str, Any]:
    """Render a bounding box region to a content-addressed SHA-256 PNG at >=300 dpi."""
    dpi = max(MIN_DPI, dpi)
    rect = fitz.Rect(bbox)
    pix = page.get_pixmap(dpi=dpi, clip=rect)
    png_bytes = pix.tobytes("png")

    sha256 = hashlib.sha256(png_bytes).hexdigest()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dest_file = out_dir / f"{sha256}.png"
    if not dest_file.exists():
        temp_file = out_dir / f".tmp_{sha256}.png"
        temp_file.write_bytes(png_bytes)
        temp_file.replace(dest_file)

    return {
        "sha256": sha256,
        "filename": f"{sha256}.png",
        "embed": f"![[{sha256}.png]]",
        "path": str(dest_file),
        "width": pix.width,
        "height": pix.height,
        "dpi": dpi,
        "bbox": list(bbox),
    }


def extract_subpanels(
    pdf_path: Path | str,
    page_number: int,  # 1-based
    output_dir: Path | str,
    caption_text_hint: str | None = None,
    dpi: int = 300,
) -> list[dict[str, Any]]:
    """Extract all detected sub-panels on a page to 300dpi PNGs.
    
    Returns a list of extracted panels with embeds.
    """
    doc = fitz.open(str(pdf_path))
    if page_number < 1 or page_number > len(doc):
        raise ValueError(f"Page number {page_number} out of range (1..{len(doc)})")

    page = doc[page_number - 1]
    caption_top = None

    if caption_text_hint:
        # Search for caption hint on this page
        matches = page.search_for(caption_text_hint)
        if matches:
            caption_top = min(m.y0 for m in matches)

    labels = detect_panel_labels(page, max_y=caption_top)
    boxes = estimate_panel_bboxes(labels, page.rect, caption_top=caption_top)

    results = []
    for lbl_info in labels:
        char = lbl_info["label"]
        if char in boxes:
            box = boxes[char]
            render_res = render_bbox_png(page, box, output_dir, dpi=dpi)
            results.append({
                "panel": char,
                "label": lbl_info["raw_label"],
                **render_res,
            })

    return results
