"""Tests for paper-os CLI and subpanels module."""

import unittest
from pathlib import Path
from paper_os.cli import main
from paper_os.subpanels import detect_panel_labels, estimate_panel_bboxes
import fitz


class TestPaperOS(unittest.TestCase):
    def test_version_command(self):
        exit_code = main(["version", "--json"])
        self.assertEqual(exit_code, 0)

    def test_doctor_command(self):
        exit_code = main(["doctor", "--json"])
        # May be 0 or 1 depending on whether dependencies are installed, but should not crash
        self.assertIn(exit_code, (0, 1))

    def test_synthetic_page_subpanels(self):
        # Create a synthetic 1-page PDF with panel labels 'a', 'b'
        doc = fitz.open()
        page = doc.new_page(width=600, height=800)

        # Insert bold text for panel 'a' and panel 'b'
        page.insert_text(fitz.Point(50, 60), "a", fontname="helv", fontsize=9)
        page.insert_text(fitz.Point(300, 60), "b", fontname="helv", fontsize=9)
        page.insert_text(fitz.Point(50, 700), "Fig. 1 | Synthetic caption", fontname="helv", fontsize=8)

        # Test bbox estimation
        labels = [
            {"label": "a", "raw_label": "a", "bbox": (50, 50, 60, 65), "font": "helv", "size": 9.0},
            {"label": "b", "raw_label": "b", "bbox": (300, 50, 310, 65), "font": "helv", "size": 9.0},
        ]
        boxes = estimate_panel_bboxes(labels, page.rect, caption_top=700.0)
        self.assertIn("a", boxes)
        self.assertIn("b", boxes)
        self.assertTrue(boxes["a"][0] < boxes["b"][0])
        self.assertTrue(boxes["a"][2] <= boxes["b"][0])
        doc.close()


if __name__ == "__main__":
    unittest.main()
