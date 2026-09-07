"""Tests for compact chart domains and collision-aware label placement."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.dashboard_visuals import layout_signal_labels, market_bubble_diameter, padded_domain


class DashboardVisualTests(unittest.TestCase):
    def test_all_23_bank_logo_assets_are_available(self):
        logo_dir = Path(__file__).resolve().parent.parent / "assets" / "bank_logos"
        logos = list(logo_dir.glob("*.png"))
        self.assertEqual(len(logos), 23)
        self.assertTrue(all(path.stat().st_size > 90 for path in logos))

    def test_domain_zooms_but_keeps_quadrant_boundary(self):
        domain = padded_domain([36.4, 49.6, 68.7])
        self.assertLess(domain[0], 36.4)
        self.assertGreater(domain[1], 68.7)
        self.assertLess(domain[1] - domain[0], 50)
        self.assertLessEqual(domain[0], 50)
        self.assertGreaterEqual(domain[1], 50)

    def test_dense_points_receive_distinct_label_positions(self):
        rows = [
            {
                "Ticker": f"B{i}",
                "Numeric score": 50 + i * 0.05,
                "Language score": 70 + i * 0.05,
            }
            for i in range(8)
        ]
        positioned = layout_signal_labels(rows, [45, 55], [65, 75])
        positions = {(row["Label x"], row["Label y"]) for row in positioned}
        self.assertEqual(len(positions), len(rows))

    def test_market_confirmation_always_increases_bubble_size(self):
        sizes = [market_bubble_diameter(score) for score in (0, 25, 50, 75, 100)]
        self.assertEqual(sizes, sorted(sizes))
        self.assertEqual(len(set(sizes)), len(sizes))
        self.assertEqual(market_bubble_diameter(-20), sizes[0])
        self.assertEqual(market_bubble_diameter(120), sizes[-1])


if __name__ == "__main__":
    unittest.main()
