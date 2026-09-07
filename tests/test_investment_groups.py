"""Tests for mutually exclusive, transparent three-axis research groups."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.investment_groups import GROUP_META, GROUP_ORDER, evidence_status, investment_group


class InvestmentGroupTests(unittest.TestCase):
    def test_all_primary_group_patterns(self):
        self.assertEqual(investment_group(80, 75, 90), "Conviction Leaders")
        self.assertEqual(investment_group(80, 75, 50), "Re-rating Candidates")
        self.assertEqual(investment_group(75, 45, 40), "Contrarian Value")
        self.assertEqual(investment_group(50, 55, 80), "Expectations-led Momentum")
        self.assertEqual(investment_group(40, 44, 45), "Downside Risk")
        self.assertEqual(investment_group(50, 52, 50), "No Clear Edge")
        self.assertEqual(investment_group(None, 60, 70), "Insufficient Evidence")

    def test_boundary_values_are_deterministic(self):
        self.assertEqual(investment_group(55, 55, 55), "Conviction Leaders")
        self.assertEqual(investment_group(55, 50, 54.9), "Re-rating Candidates")
        self.assertEqual(investment_group(50, 49.9, 55), "Contrarian Value")
        self.assertEqual(investment_group(54.9, 50, 60), "Expectations-led Momentum")
        self.assertEqual(investment_group(49.9, 50, 49.9), "Downside Risk")

    def test_language_history_gate_is_separate(self):
        self.assertEqual(evidence_status(1), "provisional")
        self.assertEqual(evidence_status(4), "four-period trend available")
        self.assertEqual(evidence_status(None), "insufficient")

    def test_each_legend_group_has_one_unique_color(self):
        colors = [GROUP_META[group]["color"] for group in GROUP_ORDER]
        self.assertEqual(len(colors), len(set(colors)))


if __name__ == "__main__":
    unittest.main()
