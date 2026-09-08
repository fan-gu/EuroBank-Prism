"""Unit tests for deterministic management-language signal rules."""

from pathlib import Path
import json
import sys
import unittest

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.language_signals import (
    build_language_alerts,
    calibrate_peer_language_scores,
    category_hits,
    comparable_history,
    is_boilerplate_page,
    is_legal_boilerplate,
    language_drift,
    quadrant,
    relevant_sentence,
    score_features,
    split_sentences,
    summarize_history,
)


class LanguageSignalTests(unittest.TestCase):
    def test_financial_language_categories_are_separate(self):
        hits = category_hits(
            "We will deliver strong capital return, although the outlook may remain challenging."
        )
        self.assertGreater(hits["positive"], 0)
        self.assertGreater(hits["negative"], 0)
        self.assertGreater(hits["strong_modal"], 0)
        self.assertGreater(hits["weak_modal"], 0)

    def test_more_certain_language_scores_higher(self):
        confident = {
            "positive": 8, "negative": 1, "uncertainty": 1,
            "strong_modal": 8, "weak_modal": 1, "caution_buffer": 1,
            "confidence": 6,
        }
        cautious = {
            "positive": 2, "negative": 5, "uncertainty": 8,
            "strong_modal": 1, "weak_modal": 8, "caution_buffer": 6,
            "confidence": 1,
        }
        self.assertGreater(
            score_features(confident, 1000)["language_score"],
            score_features(cautious, 1000)["language_score"],
        )

    def test_negative_pressure_penalizes_weak_and_uncertain_language(self):
        features = score_features(
            {
                "positive": 4, "negative": 2, "uncertainty": 8,
                "strong_modal": 2, "weak_modal": 7, "caution_buffer": 5,
                "confidence": 2,
            },
            1000,
        )
        self.assertGreater(features["negative_pressure_score"], 20)
        self.assertLess(features["management_language_strength_raw"], 0)

    def test_peer_calibration_centers_management_optimism(self):
        records = [
            {"status": "provisional_single_period", "features": {"management_language_strength_raw": value}}
            for value in (10, 20, 30, 40, 50)
        ]
        calibration = calibrate_peer_language_scores(records)
        scores = [record["features"]["language_score"] for record in records]
        self.assertEqual(calibration["method"], "robust_median_mad")
        self.assertEqual(scores[2], 50.0)
        self.assertTrue(any(score < 50 for score in scores))
        self.assertTrue(any(score > 50 for score in scores))

    def test_negative_drift_detects_confidence_to_caution_reversal(self):
        previous = {
            "weak_modal_per_1000_words": 2,
            "uncertainty_per_1000_words": 3,
            "caution_per_1000_words": 1,
            "confidence_per_1000_words": 8,
        }
        current = {
            "weak_modal_per_1000_words": 5,
            "uncertainty_per_1000_words": 7,
            "caution_per_1000_words": 4,
            "confidence_per_1000_words": 4,
        }
        drift = language_drift(current, previous)
        self.assertTrue(drift["directional_reversal"])
        self.assertGreater(drift["drift_penalty"], 0)

    def test_four_comparable_periods_create_preliminary_trend(self):
        base = {
            "ticker": "TEST", "document_type": "quarterly_results",
            "status": "provisional_single_period",
        }
        documents = []
        for quarter, (uncertainty, caution, confidence) in enumerate(((1, 1, 10), (2, 3, 8), (4, 5, 5), (6, 7, 2)), start=1):
            documents.append({
                **base,
                "period": f"Q{quarter} 2025",
                "features": {
                    "weak_modal_per_1000_words": float(quarter),
                    "uncertainty_per_1000_words": float(uncertainty),
                    "caution_per_1000_words": float(caution),
                    "confidence_per_1000_words": float(confidence),
                },
            })
        summary = summarize_history(documents)
        self.assertEqual(summary["history_periods"], 4)
        self.assertEqual(summary["drift_status"], "preliminary_four_period_trend")
        self.assertGreater(summary["language_drift_score"], 0)
        self.assertTrue(summary["directional_reversal"])

    def test_four_reporting_checkpoints_share_management_results_series(self):
        periods = [
            ("Q3 2025", "quarterly_results"),
            ("FY2025", "full_year_results"),
            ("Q1 2026", "quarterly_results"),
            ("H1 2026", "half_year_results"),
        ]
        documents = [
            {
                "ticker": "TEST",
                "period": period,
                "document_type": document_type,
                "document_series": "management_results",
                "status": "provisional_single_period",
                "features": {
                    "weak_modal_per_1000_words": 1.0,
                    "uncertainty_per_1000_words": 1.0,
                    "caution_per_1000_words": 1.0,
                    "confidence_per_1000_words": 5.0,
                },
            }
            for period, document_type in periods
        ]
        summary = summarize_history(documents)
        self.assertEqual(summary["history_periods"], 4)
        self.assertEqual([row["period"] for row in summary["documents"]], [row[0] for row in periods])

    def test_quadrants_preserve_two_axes(self):
        self.assertEqual(quadrant(70, 70), "Confirmed strength")
        self.assertEqual(quadrant(30, 70), "Potential turnaround")
        self.assertEqual(quadrant(70, 30), "Early warning")
        self.assertEqual(quadrant(30, 30), "High-risk screen")

    def test_bullet_fragments_are_preserved_as_passages(self):
        passages = split_sentences(
            "Q2 highlights\n"
            "- We remain confident and will deliver our capital target\n"
            "- The outlook may remain challenging because uncertainty is high"
        )
        self.assertTrue(any("remain confident" in item for item in passages))
        self.assertTrue(any("may remain challenging" in item for item in passages))

    def test_standard_legal_disclaimer_is_excluded_before_scoring(self):
        disclaimer = (
            "These forward-looking statements may involve risks and actual results "
            "could differ materially; the bank undertakes no obligation to update them."
        )
        self.assertTrue(is_legal_boilerplate(disclaimer))
        self.assertFalse(relevant_sentence(disclaimer))
        self.assertTrue(is_boilerplate_page(f"Example Bank Important notice {disclaimer}"))

    def test_genuine_management_risk_commentary_remains_eligible(self):
        commentary = (
            "Management expects credit risk to remain elevated as corporate defaults "
            "increase, and will maintain prudent underwriting."
        )
        self.assertFalse(is_legal_boilerplate(commentary))
        self.assertTrue(relevant_sentence(commentary))

    def test_history_gap_resets_the_comparable_sequence(self):
        documents = [
            {
                "period": period,
                "document_series": "management_results",
                "status": "provisional_single_period",
            }
            for period in ("Q2 2024", "Q3 2024", "Q1 2026", "Q2 2026")
        ]
        history = comparable_history(documents)
        self.assertEqual([row["period"] for row in history], ["Q1 2026", "Q2 2026"])

    def test_all_material_language_warnings_become_alerts(self):
        language = {
            "features": {
                "negative_pressure_score": 30.0,
                "weak_modal_per_1000_words": 8.0,
                "uncertainty_per_1000_words": 7.0,
                "caution_per_1000_words": 6.0,
                "negative_per_1000_words": 5.0,
            }
        }
        history = {
            "directional_reversal": True,
            "language_drift_score": 12.0,
            "drift_observations": [
                {"from_period": "Q1 2026", "to_period": "Q2 2026"}
            ],
        }
        thresholds = {
            "negative_pressure": 20.0,
            "weak_modal_per_1000_words": 5.0,
            "uncertainty_per_1000_words": 5.0,
            "caution_per_1000_words": 5.0,
            "negative_per_1000_words": 5.0,
            "language_drift": 10.0,
        }
        alert_types = {
            alert["type"]
            for alert in build_language_alerts(language, history, -25.0, thresholds)
        }
        self.assertEqual(
            alert_types,
            {
                "numeric_language_divergence",
                "elevated_negative_language_pressure",
                "confidence_to_caution_reversal",
                "adverse_language_drift",
            },
        )


class LanguageCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_dir = Path(__file__).resolve().parent.parent
        cls.sources = json.loads(
            (base_dir / "language_report_sources.json").read_text(encoding="utf-8")
        )["sources"]
        cls.manifest = json.loads(
            (base_dir / "language_download_manifest.json").read_text(encoding="utf-8")
        )
        cls.archive = json.loads(
            (base_dir / "language_signals.json").read_text(encoding="utf-8")
        )

    def test_curated_source_and_download_coverage_is_23_banks(self):
        self.assertEqual(len(self.sources), 23)
        self.assertEqual(len({row["ticker"] for row in self.sources}), 23)
        self.assertEqual(len(self.manifest), 23)
        self.assertTrue(all(row["status"] == "downloaded" for row in self.manifest))

    def test_signal_archive_has_auditable_provisional_coverage(self):
        self.assertEqual(self.archive["coverage"]["provisional_banks"], 23)
        self.assertEqual(self.archive["coverage"]["insufficient_banks"], 0)
        self.assertEqual(self.archive["coverage"]["four_period_trends"], 8)
        self.assertEqual(len(self.archive["documents"]), 66)
        source_statuses = {
            status: sum(row.get("source_status") == status for row in self.archive["documents"])
            for status in (
                "curated", "manually_verified_official", "pending_human_review"
            )
        }
        self.assertEqual(
            source_statuses,
            {
                "curated": 23,
                "manually_verified_official": 9,
                "pending_human_review": 34,
            },
        )
        self.assertTrue(
            all(
                len(row["evidence"]) >= 3
                for row in self.archive["documents"]
                if row["coverage_quality"] == "standard"
            )
        )
        self.assertTrue(
            all(
                len(row["evidence"]) >= 2
                for row in self.archive["documents"]
                if row["coverage_quality"] == "limited"
            )
        )
        self.assertTrue(
            all(row["publication_eligible"] is False for row in self.archive["signals"])
        )
        quadrants = {row["quadrant"] for row in self.archive["signals"]}
        self.assertEqual(
            quadrants,
            {"Confirmed strength", "Potential turnaround", "Early warning", "High-risk screen"},
        )


if __name__ == "__main__":
    unittest.main()
