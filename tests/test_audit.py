"""Tests for paper_os audit module."""

import shutil
import tempfile
import unittest
from pathlib import Path

from paper_os.audit import audit_single_paper, audit_vault_literature


class TestAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.lit_dir = self.tmp / "05 Literature"
        self.paper_dir = self.lit_dir / "testPaper2026"
        self.figures_dir = self.paper_dir / "figures"
        self.figures_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_audit_missing_files(self):
        res = audit_single_paper(self.paper_dir)
        self.assertFalse(res["passed"])
        self.assertTrue(any("Missing primary literature note" in e for e in res["errors"]))
        self.assertTrue(any("Missing Figure interpretation note" in e for e in res["errors"]))

    def test_audit_short_stub_failure(self):
        # Create minimal primary note
        (self.paper_dir / "testPaper2026.md").write_text("item", encoding="utf-8")

        # Create short stub figure note (< 10 KB)
        stub_text = """---
title: "A Test Paper Title"
citation_key: testPaper2026
paper_id: 123456
---

## Overview
- **研究背景**：测试
- **主要方法**：测试
- **关键结论**：测试
- **研究意义**：测试

## Figure 1. Test
![[0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.png]]
- **是什么**：测试
- **为什么**：测试
- **怎么做**：测试
- **发现**：测试
"""
        (self.paper_dir / "Figure解读_testPaper2026.md").write_text(stub_text, encoding="utf-8")
        res = audit_single_paper(self.paper_dir)
        self.assertFalse(res["passed"])
        self.assertTrue(any("below the minimum quality floor" in e for e in res["errors"]))

    def test_audit_missing_title_failure(self):
        # Create primary note
        (self.paper_dir / "testPaper2026.md").write_text("item", encoding="utf-8")

        # Create long figure note without title in frontmatter
        long_body = "word " * 3000
        text = f"""---
citation_key: testPaper2026
paper_id: 123456
---

## Overview
- **研究背景**：测试
- **主要方法**：测试
- **关键结论**：测试
- **研究意义**：测试

## Figure 1. Test
![[0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.png]]
- **是什么**：测试
- **为什么**：测试
- **怎么做**：测试
- **发现**：测试

{long_body}
"""
        (self.paper_dir / "Figure解读_testPaper2026.md").write_text(text, encoding="utf-8")
        res = audit_single_paper(self.paper_dir)
        self.assertFalse(res["passed"])
        self.assertTrue(any("mandatory non-empty 'title'" in e for e in res["errors"]))


if __name__ == "__main__":
    unittest.main()
