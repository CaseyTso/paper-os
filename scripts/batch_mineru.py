#!/usr/bin/env python3
"""Batch MinerU uploader and poller for multi-paper ingestion (N >= 2).

Submits multiple PDFs under a single batch_id, sequentially uploads files,
polls extract results with unified backoff, and extracts clean markdown into
each paper's literature directory.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import requests


def get_token() -> str:
    token = os.environ.get("MINERU_TOKEN")
    if token:
        return token
    cfg_file = Path.home() / "Library/Application Support/paper-notes/config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, encoding="utf-8") as f:
                data = json.load(f)
                token = data.get("mineru_key")
                if token:
                    return token
        except Exception:
            pass
    raise RuntimeError("MINERU_TOKEN is not configured in environment or config.json")


def batch_mineru_pipeline(
    items: list[dict[str, str]],  # [{"citation_key": "...", "pdf_path": "...", "out_dir": "..."}]
    poll_interval: int = 15,
    max_wait: int = 900,
    proxy: str | None = None,
) -> dict[str, Any]:
    token = get_token()
    base_url = "https://mineru.net/api/v4"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Step 1: Request batch upload URLs
    files_payload = [{"name": f"{item['citation_key']}.pdf"} for item in items]
    req_body = {
        "files": files_payload,
        "model_version": "vlm",
        "language": "en",
    }

    resp = requests.post(f"{base_url}/file-urls/batch", headers=headers, json=req_body, timeout=60)
    resp.raise_for_status()
    resp_data = resp.json()

    if resp_data.get("code") != 0 and "data" not in resp_data:
        raise RuntimeError(f"MinerU batch URL error: {resp_data}")

    batch_id = resp_data["data"]["batch_id"]
    file_urls = resp_data["data"]["file_urls"]  # Same order as files_payload

    print(f"✅ MinerU batch created: batch_id={batch_id} with {len(items)} files")

    # Step 2: Sequential PUT uploads (sequential is much more reliable across proxies)
    for item, put_url in zip(items, file_urls):
        pdf_path = Path(item["pdf_path"])
        print(f"⬆️ Uploading {item['citation_key']}.pdf ({pdf_path.stat().st_size / 1024 / 1024:.2f} MB)...")

        # Prefer curl if available for better socket/proxy handling on large streams
        curl_cmd = [
            "curl", "-s", "-S", "-X", "PUT",
            "--data-binary", f"@{pdf_path}",
            "-H", "Content-Type:",
            "--max-time", "600",
        ]
        if proxy:
            curl_cmd.extend(["-x", proxy])
        curl_cmd.append(put_url)

        res = subprocess.run(curl_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to upload {pdf_path}: {res.stderr}")

    print("✅ All PDFs uploaded successfully. Beginning batch polling...")

    # Step 3: Polling
    start_time = time.time()
    results_map: dict[str, Any] = {}

    while time.time() - start_time < max_wait:
        poll_resp = requests.get(f"{base_url}/extract-results/batch/{batch_id}", headers=headers, timeout=60)
        poll_resp.raise_for_status()
        pdata = poll_resp.json().get("data", {})
        extract_results = pdata.get("extract_result", [])

        all_terminal = True
        for res_entry in extract_results:
            fname = res_entry.get("file_name")
            state = res_entry.get("state")  # waiting | running | done | failed
            results_map[fname] = res_entry
            if state not in ("done", "failed"):
                all_terminal = False

        if all_terminal and len(results_map) >= len(items):
            break

        print(f"⏳ Polling MinerU batch... elapsed {int(time.time() - start_time)}s")
        time.sleep(poll_interval)

    # Step 4: Download and unzip
    final_report = []
    for item in items:
        fname = f"{item['citation_key']}.pdf"
        entry = results_map.get(fname, {})
        state = entry.get("state")
        zip_url = entry.get("full_zip_url")

        if state == "done" and zip_url:
            out_dir = Path(item["out_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            zip_dest = out_dir / "mineru_result.zip"

            # Download without proxy for CDN stability
            dl_cmd = ["curl", "-s", "-S", "--noproxy", "*", "-L", "-o", str(zip_dest), "--max-time", "180", zip_url]
            subprocess.run(dl_cmd, check=True)

            # Unzip
            extract_dir = out_dir / "mineru_extract"
            extract_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(zip_dest, "r") as z:
                z.extractall(extract_dir)

            # Locate and move markdown
            md_files = list(extract_dir.glob("**/*.md"))
            if md_files:
                target_md = out_dir / f"minerUmd_{item['citation_key']}.md"
                shutil.copyfile(md_files[0], target_md)
                final_report.append({
                    "citation_key": item["citation_key"],
                    "status": "success",
                    "minerUmd_path": str(target_md),
                })
            else:
                final_report.append({
                    "citation_key": item["citation_key"],
                    "status": "failed",
                    "error": "No markdown file found in extract zip",
                })

            # Cleanup zip
            if zip_dest.exists():
                zip_dest.unlink()
        else:
            final_report.append({
                "citation_key": item["citation_key"],
                "status": "failed",
                "error": entry.get("err_msg") or f"state: {state}",
            })

    return {"batch_id": batch_id, "items": final_report}


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch MinerU Conversion CLI")
    parser.add_argument("--items-json", required=True, help="JSON list of items with citation_key, pdf_path, out_dir")
    parser.add_argument("--proxy", default=None, help="Proxy for PUT upload (e.g. http://127.0.0.1:8080)")
    args = parser.parse_args()

    items = json.loads(args.items_json)
    res = batch_mineru_pipeline(items, proxy=args.proxy)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
