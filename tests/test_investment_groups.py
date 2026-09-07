"""Tests for mutually exclusive, transparent three-axis research groups."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.investment_groups import evidence_status, investment_group


class InvestmentGroupTests(unittest.TestCase):
    def test_all_primary_group_patterns(self):
        self.assertEqual(investment_group(80, 75, 90), "Prism Leaders")
        self.assertEqual(investment_group(80, 75, 50), "Re-rating Candidates")
        self.assertEqual(investment_group(55, 50, 80), "Momentum Champions")
        self.assertEqual(investment_group(75, 70, 20), "Divergence & Watch")
        self.assertEqual(investment_group(40, 44, 55), "Structural Laggards")
        self.assertEqual(investment_group(None, 60, 70), "Insufficient Evidence")

    def test_boundary_values_are_deterministic(self):
        self.assertEqual(investment_group(55, 55, 55), "Prism Leaders")
        self.assertEqual(investment_group(55, 55, 33), "Re-rating Candidates")
        self.assertEqual(investment_group(40, 40, 67), "Momentum Champions")

    def test_language_history_gate_is_separate(self):
        self.assertEqual(evidence_status(1), "provisional")
        self.assertEqual(evidence_status(4), "four-period trend available")
        self.assertEqual(evidence_status(None), "insufficient")


if __name__ == "__main__":
    unittest.main()
