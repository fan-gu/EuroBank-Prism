"""Tests for mutually exclusive, transparent three-axis research groups."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.investment_groups import (
    GROUP_META,
    GROUP_ORDER,
    derive_group_thresholds,
    evidence_status,
    investment_group,
)


class InvestmentGroupTests(unittest.TestCase):
    def test_all_primary_group_patterns(self):
        self.assertEqual(investment_group(80, 75, 90), "Conviction Leaders")
        self.assertEqual(investment_group(80, 75, 49), "Strong Signals, Weak Price")
        self.assertEqual(investment_group(75, 45, 45), "Cautious Value")
        self.assertEqual(investment_group(50, 45, 80), "Price Momentum")
        self.assertEqual(investment_group(40, 75, 50), "Story Ahead of Numbers")
        self.assertEqual(investment_group(40, 44, 45), "Downside Risk")
        self.assertEqual(investment_group(55, 52, 55), "No Clear Edge")
        self.assertEqual(investment_group(None, 60, 70), "Insufficient Evidence")

    def test_boundary_values_are_deterministic(self):
        self.assertEqual(investment_group(60, 60, 60), "Conviction Leaders")
        self.assertEqual(investment_group(50, 50, 49.9), "Strong Signals, Weak Price")
        self.assertEqual(investment_group(50, 49.9, 40), "Cautious Value")
        self.assertEqual(investment_group(59.9, 50, 60), "Price Momentum")
        self.assertEqual(investment_group(49.9, 50, 49.9), "Downside Risk")

    def test_review_examples_keep_all_three_axes_informative(self):
        gates = {
            "numeric_mid": 49.6, "numeric_high": 52.0,
            "language_mid": 50.0, "language_high": 57.0,
            "price_low": 34.0, "price_mid": 48.0, "price_high": 60.0,
        }
        self.assertEqual(investment_group(50.1, 57.3, 18.7, gates), "Strong Signals, Weak Price")
        self.assertEqual(investment_group(38.8, 69.8, 44.8, gates), "Story Ahead of Numbers")
        self.assertEqual(investment_group(54.8, 49.7, 2.2, gates), "Downside Risk")
        self.assertEqual(investment_group(55.1, 40.4, 47.4, gates), "Cautious Value")
        self.assertEqual(investment_group(68.7, 45.5, 30.2, gates), "Downside Risk")

    def test_thresholds_are_derived_per_axis(self):
        rows = [
            {"numeric": value, "language": value * 10, "price": 100 - value}
            for value in range(1, 6)
        ]
        gates = derive_group_thresholds(rows)
        self.assertEqual(gates["numeric_mid"], 3)
        self.assertEqual(gates["language_mid"], 30)
        self.assertNotEqual(gates["numeric_high"], gates["language_high"])

    def test_language_history_gate_is_separate(self):
        self.assertEqual(evidence_status(1), "provisional")
        self.assertEqual(evidence_status(4), "four-period trend available")
        self.assertEqual(evidence_status(None), "insufficient")

    def test_each_legend_group_has_one_unique_color(self):
        colors = [GROUP_META[group]["color"] for group in GROUP_ORDER]
        self.assertEqual(len(colors), len(set(colors)))


if __name__ == "__main__":
    unittest.main()
