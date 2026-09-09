"""Unit tests for deterministic management-language signal rules."""

from pathlib import Path
import json
import sys
import unittest

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.language_signals import (
    build_modal_diagnostics,
    build_language_alerts,
    calibrate_peer_language_scores,
    category_hits,
    comparable_history,
    is_boilerplate_page,
    is_legal_boilerplate,
    is_prior_period_technical,
    language_drift,
    mask_neutral_risk_terms,
    mask_procedural_condition_footnotes,
    mask_standardized_calculation_footnotes,
    negation_dropped_categories,
    normalized_sentence_key,
    quadrant,
    register_sentence,
    relevant_sentence,
    score_features,
    split_sentences,
    summarize_history,
)


class LanguageSignalTests(unittest.TestCase):
    def test_neutral_risk_compounds_are_masked_but_outlook_risk_survives(self):
        sentence = "Low cost of risk was in line with guidance."
        masked, count = mask_neutral_risk_terms(sentence)
        self.assertEqual(count, 1)
        self.assertEqual(len(masked), len(sentence))
        self.assertEqual(category_hits(masked)["uncertainty"], 0)

        management = (
            "LLPs were stable, reflecting our active risk management and confidence."
        )
        masked, count = mask_neutral_risk_terms(management)
        self.assertEqual(count, 1)
        self.assertEqual(category_hits(masked)["uncertainty"], 0)

        outlook = "We see downside risks to the outlook and risks remain elevated."
        masked, count = mask_neutral_risk_terms(outlook)
        self.assertEqual(count, 0)
        self.assertEqual(category_hits(masked)["uncertainty"], 2)

    def test_negation_is_drop_only_and_supports_post_hit_relief(self):
        self.assertEqual(
            negation_dropped_categories("We face no material headwinds this year.")["negative"],
            1,
        )
        self.assertEqual(
            negation_dropped_categories("We face headwinds this year.")["negative"],
            0,
        )
        self.assertGreaterEqual(
            negation_dropped_categories("The risks are limited.")["uncertainty"],
            1,
        )
        self.assertEqual(
            negation_dropped_categories("The outlook is not without pressure.")["negative"],
            0,
        )
        self.assertEqual(
            negation_dropped_categories(
                "Costs had no effect on income. Volatility remained elevated."
            )["uncertainty"],
            0,
        )
        self.assertEqual(
            negation_dropped_categories(
                "Asset income was lower versus 2025 from margin pressure."
            )["negative"],
            0,
        )

    def test_document_dedup_is_exact_first_and_number_safe(self):
        exact_seen, template_seen = set(), set()
        sentence = "We remain confident that our capital position is robust."
        first, _ = register_sentence(sentence, exact_seen, template_seen)
        repeated, _ = register_sentence(sentence, exact_seen, template_seen)
        self.assertFalse(first)
        self.assertTrue(repeated)

        # Short metric statements with different values are not collapsed.
        different_number, _ = register_sentence(
            "The CET1 ratio was 15.7%.", exact_seen, template_seen
        )
        another_number, _ = register_sentence(
            "The CET1 ratio was 13.2%.", exact_seen, template_seen
        )
        self.assertFalse(different_number)
        self.assertFalse(another_number)

        # Long, non-directional templates may be safely collapsed across pages.
        prefix = "This information is supplied for presentation purposes " * 3
        first_template, _ = register_sentence(
            f"{prefix} reference 2025.", exact_seen, template_seen
        )
        repeated_template, _ = register_sentence(
            f"{prefix} reference 2026.", exact_seen, template_seen
        )
        self.assertFalse(first_template)
        self.assertTrue(repeated_template)

    def test_unicode_sentence_normalization_preserves_letters(self):
        key = normalized_sentence_key("Crédit Agricole — resilient.")
        self.assertIn("crédit agricole", key)

    def test_prior_period_gate_removes_notes_not_current_comparisons(self):
        restatement = (
            "As a reminder, on 28 March 2025, BNP Paribas published quarterly "
            "series for 2024, restated to reflect the new presentation."
        )
        self.assertTrue(is_prior_period_technical(restatement, "Q1 2026"))
        self.assertFalse(
            is_prior_period_technical(
                "Revenue increased by 8% compared with last year.", "Q2 2026"
            )
        )
        self.assertFalse(
            is_prior_period_technical(
                "Unlike last year's decline, we now expect robust growth in 2026.",
                "Q2 2026",
            )
        )

    def test_bpe_guidance_regression_survives_every_filter(self):
        sentence = (
            "Full year 2026 Guidance improved, subject to macro and market conditions"
        )
        self.assertTrue(relevant_sentence(sentence))
        self.assertFalse(is_prior_period_technical(sentence, "H1 2026"))
        masked, count = mask_neutral_risk_terms(sentence)
        self.assertEqual(count, 0)
        self.assertEqual(sum(negation_dropped_categories(masked).values()), 0)

    def test_procedural_condition_footnotes_are_removed_conservatively(self):
        bper = "Distributions subject to target's achievement ."
        filtered, count = mask_procedural_condition_footnotes(bper)
        self.assertEqual(count, 1)
        self.assertFalse(filtered.strip(". "))

        approval = "Ordinary dividend subject to shareholder approval."
        filtered, count = mask_procedural_condition_footnotes(approval)
        self.assertEqual(count, 1)
        self.assertEqual(sum(category_hits(filtered).values()), 0)

        substantive = (
            "Full year 2026 Guidance improved, subject to macro and market conditions"
        )
        filtered, count = mask_procedural_condition_footnotes(substantive)
        self.assertEqual(count, 0)
        self.assertEqual(filtered, substantive)

        mixed_substantive = (
            "The issuance plan is subject to market conditions and regulatory "
            "requirements."
        )
        filtered, count = mask_procedural_condition_footnotes(mixed_substantive)
        self.assertEqual(count, 0)
        self.assertEqual(filtered, mixed_substantive)

        genuine_warning = (
            "Capital distributions may be reduced if the CET1 target is missed."
        )
        filtered, count = mask_procedural_condition_footnotes(genuine_warning)
        self.assertEqual(count, 0)
        self.assertGreater(category_hits(filtered)["weak_modal"], 0)

    def test_mixed_passage_retains_narrative_after_procedural_clause_mask(self):
        sentence = (
            "We remain confident in our capital return; dividend subject to "
            "shareholder approval."
        )
        filtered, count = mask_procedural_condition_footnotes(sentence)
        self.assertEqual(count, 1)
        self.assertIn("We remain confident in our capital return", filtered)
        self.assertGreater(category_hits(filtered)["confidence"], 0)

    def test_standardized_rounding_footnotes_do_not_create_weak_modals(self):
        gle = (
            "The sum of values contained in the tables and analyses may differ "
            "slightly from the total reported due to rounding rules."
        )
        filtered, count = mask_standardized_calculation_footnotes(gle)
        self.assertEqual(count, 1)
        self.assertFalse(filtered.strip(". "))
        self.assertEqual(category_hits(filtered)["weak_modal"], 0)

        common = "Note: figures may not add up exactly due to rounding"
        filtered, count = mask_standardized_calculation_footnotes(common)
        self.assertEqual(count, 1)
        self.assertFalse(filtered.strip(". "))

        variants = (
            "Numbers throughout the presentation may not add up precisely to "
            "the totals provided in tables and text due to rounding.",
            "Notes: throughout this presentation totals may not sum due to "
            "rounding differences and percentages may not precisely reflect "
            "the absolute figures.",
            "All figures in this presentation are subject to rounding.",
            "All figures in this presentation subject to rounding.",
            "The shareholder structure may contain rounding differences.",
            "Small differences are possible in the tables due to rounding.",
            "Note rounding may apply",
        )
        for variant in variants:
            with self.subTest(variant=variant):
                filtered, count = mask_standardized_calculation_footnotes(variant)
                self.assertEqual(count, 1)
                self.assertEqual(category_hits(filtered)["weak_modal"], 0)

    def test_rounding_note_is_removed_without_losing_attached_narrative(self):
        sentence = (
            "Note: figures may not add up exactly due to rounding. "
            "Revenue declined because of weaker fees."
        )
        filtered, count = mask_standardized_calculation_footnotes(sentence)
        self.assertEqual(count, 1)
        self.assertIn("Revenue declined because of weaker fees", filtered)
        self.assertGreater(category_hits(filtered)["negative"], 0)

    def test_modal_diagnostics_use_master_country_data_without_scoring(self):
        universe = [
            {"ticker": "BG", "country": "Austria"},
            {"ticker": "FBK", "country": "Italy"},
            {"ticker": "ISP", "country": "Italy"},
        ]
        documents = {
            ticker: {
                "status": "provisional_single_period",
                "document_type": "quarterly_results",
                "features": {
                    "weak_modal_per_1000_words": weak,
                    "uncertainty_per_1000_words": 1.0,
                    "language_score": score,
                },
            }
            for ticker, weak, score in (
                ("BG", 0.0, 55.0), ("FBK", 1.0, 50.0), ("ISP", 12.0, 45.0)
            )
        }
        scores_before = {
            ticker: document["features"]["language_score"]
            for ticker, document in documents.items()
        }
        diagnostics = build_modal_diagnostics(documents, universe)
        self.assertFalse(diagnostics["scores_affected"])
        self.assertEqual(diagnostics["country_modal_profile"]["AT"]["banks"], ["BG"])
        self.assertEqual(
            diagnostics["country_modal_profile"]["IT"]["banks"], ["FBK", "ISP"]
        )
        self.assertEqual(
            scores_before,
            {
                ticker: document["features"]["language_score"]
                for ticker, document in documents.items()
            },
        )

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

    def test_esg_and_flattened_table_pollution_are_excluded(self):
        disclaimer = (
            "This document may contain ESG-related material based on publicly "
            "available information and sources believed to be reliable."
        )
        table = "Q2 2026 results overview Reported P&L € mln 2,354 1,987 24% 17%"
        self.assertFalse(relevant_sentence(disclaimer))
        self.assertFalse(relevant_sentence(table))

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
        self.assertEqual(self.archive["schema_version"], "1.4")
        self.assertEqual(self.archive["rule_version"], "management-language-v2.4.3")
        self.assertEqual(self.archive["coverage"]["provisional_banks"], 23)
        self.assertEqual(self.archive["coverage"]["insufficient_banks"], 0)
        # DBK Q1 2026 now has only one substantive cited passage after routine
        # approval footnotes are removed, so it correctly fails the two-piece
        # limited-coverage gate instead of creating a pollution-backed trend.
        self.assertEqual(self.archive["coverage"]["four_period_trends"], 7)
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
        audit_fields = {
            "masked_neutral_risk_spans",
            "deduplicated_repeats",
            "negated_hits_dropped",
            "excluded_prior_period_passages",
            "masked_procedural_condition_spans",
            "excluded_procedural_condition_passages",
            "masked_standardized_footnote_spans",
            "excluded_standardized_footnote_passages",
            "pre_filter_analyzed_word_count",
            "filter_shrink_ratio",
            "filter_shrink_warning",
            "filter_examples",
        }
        self.assertTrue(
            all(audit_fields <= set(document) for document in self.archive["documents"])
        )
        # ISP's deck repeats the same rounding note across many table pages.
        # Removing passages admitted only by its weak modal intentionally
        # triggers the >25% denominator-shrink audit gate.
        self.assertEqual(self.archive["coverage"]["filter_shrink_warnings"], 1)
        shrink_warning_documents = [
            document
            for document in self.archive["documents"]
            if document["filter_shrink_warning"]
        ]
        self.assertEqual(
            [(document["ticker"], document["period"]) for document in shrink_warning_documents],
            [("ISP", "H1 2026")],
        )
        self.assertGreater(
            sum(row["masked_neutral_risk_spans"] for row in self.archive["documents"]),
            0,
        )
        diagnostics = self.archive["diagnostics"]
        self.assertFalse(diagnostics["scores_affected"])
        self.assertIn("BG", diagnostics["country_modal_profile"]["AT"]["banks"])
        self.assertIn("FBK", diagnostics["country_modal_profile"]["IT"]["banks"])
        quadrants = {row["quadrant"] for row in self.archive["signals"]}
        self.assertEqual(
            quadrants,
            {"Confirmed strength", "Potential turnaround", "Early warning", "High-risk screen"},
        )


if __name__ == "__main__":
    unittest.main()
