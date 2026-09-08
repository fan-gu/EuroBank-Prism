"""Build auditable management-language signals from official bank PDFs.

This module intentionally keeps language and quantitative scores separate.
Signals are provisional until comparable history and an out-of-sample backtest
exist. The LLM is not used as an untraceable sentiment judge; every feature is
deterministic and every displayed observation retains its source page.
"""

from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import statistics

from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REPORTS_DIR = BASE_DIR / "reports"
DEFAULT_OUTPUT = BASE_DIR / "language_signals.json"
RULE_VERSION = "management-language-v2.2"

LEXICONS = {
    "positive": {
        "strong", "stronger", "robust", "resilient", "solid", "improved",
        "improving", "growth", "successful", "attractive", "outperform",
        "progress", "momentum", "confident", "confidence",
    },
    "negative": {
        "challenging", "headwind", "headwinds", "deterioration", "deteriorated",
        "pressure", "pressures", "adverse", "decline", "declined", "weak",
        "weaker", "downturn", "stress", "stressed", "downside",
        "deteriorating", "softening", "slowdown", "contraction",
        "below expectations", "lower guidance", "margin compression",
        "higher impairments", "under pressure",
    },
    "uncertainty": {
        "uncertain", "uncertainty", "volatile", "volatility", "potentially",
        "approximately", "depending", "subject", "risk", "risks",
    },
    "strong_modal": {
        "will", "must", "committed", "commit", "commits", "expect", "expects",
        "target", "targets",
    },
    "weak_modal": {
        "may", "might", "could", "would", "aim", "aims", "intend", "intends",
        "seek", "seeks", "consider", "expects approximately",
    },
    "caution_buffer": {
        "normalisation", "normalization", "prudent", "prudently", "one-off",
        "normalising", "cautious", "vigilant", "temporary", "temporarily",
        "transitory", "selective", "broadly stable", "limited visibility",
        "subject to", "assuming",
    },
    "confidence": {
        "momentum", "capital return", "share buyback", "buyback", "confident",
        "confidence", "strong", "robust", "solid",
    },
}

NARRATIVE_TERMS = re.compile(
    r"\b(?:outlook|guidance|expect|target|strategy|strategic|ambition|priority|"
    r"momentum|profitability|headwind|challenge|capital return|distribution|"
    r"dividend|buyback|management|we will|we aim|committed to|confident|"
    r"strong results|strong financial position|robust performance|"
    r"resilient performance|uncertain|uncertainty|volatile|volatility|prudent|"
    r"cautious|normalisation|normalization|pressure|downside|may|might|could|"
    r"subject to)\b",
    flags=re.IGNORECASE,
)
EXCLUDED_CONTEXT = re.compile(
    r"\b(?:remuneration report|compensation report|accounting polic(?:y|ies)|"
    r"notes to the consolidated financial statements|auditor.?s report|"
    r"variable compensation|executive compensation|remuneration|"
    r"committed to compliance|applicable laws and regulations|"
    r"sustainable finance|sustainability|climate change|ESG risk|"
    r"described in the management report|glossary|table of contents)\b",
    flags=re.IGNORECASE,
)
GUIDANCE_TERMS = re.compile(
    r"\b(?:outlook|guidance|target|expect|forecast|ambition|objective|we will|"
    r"we aim|committed to)\b",
    flags=re.IGNORECASE,
)
ANNUAL_MANAGEMENT_SECTION = re.compile(
    r"\b(?:letter from|chief executive|ceo|management report|group performance|"
    r"financial performance|business review|strategic priorities|strategy|"
    r"outlook|targets and ambitions|financial objectives|results)\b",
    flags=re.IGNORECASE,
)
WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'-]*\b")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\u00ad", "")
    return " ".join(text.split())


def split_sentences(text: str) -> list[str]:
    clean = clean_text(text)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", clean)
    # Investor presentations frequently use bullet fragments without terminal
    # punctuation. Preserve those management statements as auditable passages
    # instead of silently treating a slide as empty.
    bullet_blocks = re.split(r"\n\s*(?:[•▪◼�]|[-–—]\s+)", text)
    candidates = sentences + [clean_text(block) for block in bullet_blocks]
    unique = []
    seen = set()
    for sentence in candidates:
        if 40 <= len(sentence) <= 600 and sentence not in seen:
            seen.add(sentence)
            unique.append(sentence)
    return unique


def phrase_count(text: str, phrase: str) -> int:
    return len(re.findall(rf"\b{re.escape(phrase)}\b", text, flags=re.IGNORECASE))


def category_hits(text: str) -> dict[str, int]:
    return {
        category: sum(phrase_count(text, phrase) for phrase in phrases)
        for category, phrases in LEXICONS.items()
    }


def relevant_sentence(sentence: str) -> bool:
    if EXCLUDED_CONTEXT.search(sentence):
        return False
    # Requiring the narrative trigger in the same sentence prevents a single
    # word such as "performance" in a page heading from pulling an entire
    # accounting, regulatory or risk page into the language sample.
    return bool(NARRATIVE_TERMS.search(sentence))


def evidence_priority(record: dict) -> tuple[int, int, int]:
    hits = record["hits"]
    divergence_terms = hits["negative"] + hits["uncertainty"] + hits["weak_modal"]
    guidance = 1 if record["is_guidance"] else 0
    total = sum(hits.values())
    return guidance, divergence_terms, total


def score_features(counts: dict[str, int], word_count: int) -> dict:
    positive = counts["positive"]
    negative = counts["negative"]
    strong = counts["strong_modal"]
    weak = counts["weak_modal"]
    uncertainty = counts["uncertainty"]
    caution = counts["caution_buffer"]
    confidence = counts["confidence"]

    positive_rate = 1000 * positive / max(word_count, 1)
    negative_rate = 1000 * negative / max(word_count, 1)
    strong_rate = 1000 * strong / max(word_count, 1)
    weak_rate = 1000 * weak / max(word_count, 1)
    uncertainty_rate = 1000 * uncertainty / max(word_count, 1)
    caution_rate = 1000 * caution / max(word_count, 1)
    confidence_rate = 1000 * confidence / max(word_count, 1)

    # Management disclosures have a positive base rate. Measure explicit
    # downside pressure separately before peer calibration instead of allowing
    # promotional wording to accumulate around an assumed neutral score of 50.
    positive_signal = (
        0.35 * positive_rate
        + 0.65 * confidence_rate
        + 0.80 * strong_rate
    )
    negative_pressure = (
        2.00 * negative_rate
        + 1.35 * uncertainty_rate
        + 1.75 * weak_rate
        + 1.15 * caution_rate
    )
    raw_strength = positive_signal - negative_pressure
    absolute_score = round(max(0, min(100, 50 + raw_strength)), 1)
    return {
        "language_score": absolute_score,
        "absolute_language_score": absolute_score,
        "management_language_strength_raw": round(raw_strength, 4),
        "positive_signal_score": round(positive_signal, 2),
        "negative_pressure_score": round(negative_pressure, 2),
        "positive_per_1000_words": round(positive_rate, 2),
        "negative_per_1000_words": round(negative_rate, 2),
        "strong_modal_per_1000_words": round(strong_rate, 2),
        "weak_modal_per_1000_words": round(weak_rate, 2),
        "uncertainty_per_1000_words": round(uncertainty_rate, 2),
        "caution_per_1000_words": round(caution_rate, 2),
        "confidence_per_1000_words": round(confidence_rate, 2),
    }


def calibrate_peer_language_scores(records: list[dict]) -> dict:
    """Center the current peer cohort with a robust median/MAD transform.

    This corrects the positive base rate of management-authored documents.
    It does not make the scores publication-eligible or replace a backtest.
    """
    eligible = [record for record in records if record["status"] != "insufficient"]
    raw_values = [
        record["features"]["management_language_strength_raw"]
        for record in eligible
    ]
    if not raw_values:
        return {"method": "not_available", "peer_count": 0}
    median = statistics.median(raw_values)
    mad = statistics.median(abs(value - median) for value in raw_values)
    robust_scale = max(1.4826 * mad, 1.0)
    for record in eligible:
        raw = record["features"]["management_language_strength_raw"]
        calibrated = max(15.0, min(85.0, 50 + 12 * (raw - median) / robust_scale))
        record["features"]["language_score"] = round(calibrated, 1)
        record["features"]["peer_centered_z"] = round((raw - median) / robust_scale, 4)
    return {
        "method": "robust_median_mad",
        "peer_count": len(eligible),
        "median_raw_strength": round(median, 4),
        "mad_raw_strength": round(mad, 4),
        "score_center": 50,
        "score_points_per_robust_sigma": 12,
        "score_floor": 15,
        "score_ceiling": 85,
    }


def language_drift(current: dict, previous: dict) -> dict:
    """Measure negative wording drift between comparable document periods."""
    weak_change = (
        current["weak_modal_per_1000_words"]
        - previous["weak_modal_per_1000_words"]
    )
    uncertainty_change = (
        current["uncertainty_per_1000_words"]
        - previous["uncertainty_per_1000_words"]
    )
    caution_change = (
        current["caution_per_1000_words"]
        - previous["caution_per_1000_words"]
    )
    confidence_change = (
        current["confidence_per_1000_words"]
        - previous["confidence_per_1000_words"]
    )
    reversal = caution_change > 1.0 and confidence_change < -1.0
    penalty = (
        1.75 * max(weak_change, 0)
        + 1.35 * max(uncertainty_change, 0)
        + 1.15 * max(caution_change, 0)
        + 0.65 * max(-confidence_change, 0)
    )
    return {
        "weak_modal_change": round(weak_change, 2),
        "uncertainty_change": round(uncertainty_change, 2),
        "caution_change": round(caution_change, 2),
        "confidence_change": round(confidence_change, 2),
        "directional_reversal": reversal,
        "drift_penalty": round(penalty, 2),
    }


def period_sort_key(period: str) -> tuple[int, int]:
    """Return a stable chronological key for results-reporting periods."""
    year_match = re.search(r"20\d{2}", period or "")
    year = int(year_match.group(0)) if year_match else 0
    label = (period or "").upper()
    quarter_match = re.search(r"Q([1-4])", label)
    if quarter_match:
        return year, int(quarter_match.group(1))
    if "H1" in label or "1H" in label or "HALF" in label:
        return year, 2
    if "9M" in label or "Q3" in label:
        return year, 3
    if "FY" in label or "ANNUAL" in label:
        return year, 4
    return year, 0


def comparable_history(documents: list[dict]) -> list[dict]:
    """Keep one consistent reporting genre, ending with the latest document.

    A Q2 presentation and a full annual report can have very different writing
    styles.  We therefore never create a drift series by mixing their genres.
    """
    eligible = [document for document in documents if document["status"] != "insufficient"]
    if not eligible:
        return []
    ordered = sorted(eligible, key=lambda document: period_sort_key(document["period"]))
    latest_series = ordered[-1].get("document_series", "management_results")
    return [
        document
        for document in ordered
        if document.get("document_series", "management_results") == latest_series
    ]


def summarize_history(documents: list[dict]) -> dict:
    """Describe the latest comparable four-period language trend.

    The output is deliberately a preliminary research observation, not an
    investment signal. Eight periods and a backtest remain necessary before an
    event alert is eligible for publication.
    """
    history = comparable_history(documents)
    if len(history) < 4:
        return {
            "documents": history,
            "history_periods": len(history),
            "language_drift_score": None,
            "directional_reversal": None,
            "drift_observations": [],
            "drift_status": "requires_four_comparable_periods",
        }
    history = history[-4:]
    observations = [
        {"from_period": previous["period"], "to_period": current["period"], **language_drift(current["features"], previous["features"])}
        for previous, current in zip(history, history[1:])
    ]
    penalties = [observation["drift_penalty"] for observation in observations]
    return {
        "documents": history,
        "history_periods": len(history),
        "language_drift_score": round(sum(penalties) / len(penalties), 2),
        "directional_reversal": any(observation["directional_reversal"] for observation in observations),
        "drift_observations": observations,
        "drift_status": "preliminary_four_period_trend",
    }


def infer_document_metadata(path: Path) -> tuple[str, str]:
    name = path.stem.lower()
    year_match = re.search(r"20\d{2}", name)
    year = year_match.group(0) if year_match else "unknown"
    if "annual" in name:
        return "annual_report", f"FY{year}"
    if "h1" in name or "half" in name:
        return "half_year_results", f"H1 {year}"
    if "9m" in name or "nine_month" in name:
        return "nine_month_results", f"9M {year}"
    if "fy" in name or "full_year" in name:
        return "full_year_results", f"FY{year}"
    if "q1" in name or "q2" in name or "q3" in name or "q4" in name:
        quarter = re.search(r"q[1-4]", name).group(0).upper()
        return "quarterly_results", f"{quarter} {year}"
    return "unclassified", year


def page_is_eligible(page_text: str, document_type: str) -> bool:
    if document_type == "annual_report":
        # Annual reports contain hundreds of pages of mandatory risk,
        # accounting and Pillar 3 language. Only management-facing sections
        # are admitted to the language sample in v1.
        return bool(ANNUAL_MANAGEMENT_SECTION.search(page_text[:700]))
    return document_type in {
        "half_year_results", "quarterly_results", "nine_month_results",
        "full_year_results", "results_material",
    }


def analyze_pdf(path: Path, source: dict) -> dict:
    ticker = source["ticker"]
    inferred_type, inferred_period = infer_document_metadata(path)
    document_type = source.get("document_type", inferred_type)
    period = source.get("period", inferred_period)
    evidence = []
    counts = {category: 0 for category in LEXICONS}
    word_count = 0
    page_count = 0

    reader = PdfReader(str(path))
    print(f"Analyzing {ticker}: {path.name} ({len(reader.pages)} pages)", flush=True)
    for page_number, page in enumerate(reader.pages, start=1):
        page_count += 1
        page_text = clean_text(page.extract_text() or "")
        if not page_text or not page_is_eligible(page_text, document_type):
            continue
        for sentence in split_sentences(page_text):
            if not relevant_sentence(sentence):
                continue
            hits = category_hits(sentence)
            words = WORD_RE.findall(sentence)
            if not words:
                continue
            word_count += len(words)
            for category, value in hits.items():
                counts[category] += value
            if any(hits.values()) or GUIDANCE_TERMS.search(sentence):
                evidence.append(
                    {
                        "page": page_number,
                        "sentence": sentence[:500],
                        "is_guidance": bool(GUIDANCE_TERMS.search(sentence)),
                        "hits": hits,
                        "review_status": "pending_human_review",
                    }
                )

    features = score_features(counts, word_count)
    evidence.sort(key=evidence_priority, reverse=True)
    selected_evidence = evidence[:8]
    minimum_coverage = word_count >= 150 and len(selected_evidence) >= 3
    record = {
        "ticker": ticker,
        "bank_name": source.get("bank_name"),
        "document": path.name,
        "document_type": document_type,
        "document_series": source.get("document_series", "management_results"),
        "period": period,
        "publication_date": None,
        "source_url": source.get("download_url"),
        "official_page": source.get("official_page"),
        "source_status": source.get("source_status", "curated"),
        "document_sha256": sha256(path),
        "page_count": page_count,
        "analyzed_word_count": word_count,
        "feature_counts": counts,
        "features": features,
        "evidence": selected_evidence,
        "status": "provisional_single_period" if minimum_coverage else "insufficient",
        "history_periods": 1,
        "language_drift_score": None,
        "directional_reversal": None,
        "drift_status": "requires_comparable_history",
        "backtest_status": "not_run",
        "publication_eligible": False,
        "comparability_warning": (
            "Single-period and mixed document genres; do not interpret as a trading signal."
        ),
    }
    print(
        f"Completed {ticker}: {word_count:,} narrative words, "
        f"status={record['status']}",
        flush=True,
    )
    return record


def load_language_manifest() -> list[dict]:
    paths = [
        BASE_DIR / "language_download_manifest.json",
        BASE_DIR / "language_history_download_manifest.json",
    ]
    if not paths[0].exists():
        raise FileNotFoundError(
            "language_download_manifest.json is missing; run "
            "download_language_reports.py first."
        )
    records = []
    seen = set()
    for path in paths:
        if not path.exists():
            continue
        for record in json.loads(path.read_text(encoding="utf-8")):
            key = (record.get("ticker"), record.get("period"))
            if key in seen or record.get("status") != "downloaded":
                continue
            if record.get("source_status", "curated") not in {
                "curated", "pending_human_review"
            }:
                continue
            seen.add(key)
            records.append(record)
    return records


def load_universe() -> list[dict]:
    path = BASE_DIR / "bank_master.json"
    return json.loads(path.read_text(encoding="utf-8"))["constituents"]


def load_numeric_scores() -> dict[str, float]:
    path = BASE_DIR / "full_universe_scores.json"
    return {
        record["ticker"]: record["score"]
        for record in json.loads(path.read_text(encoding="utf-8"))
        if record.get("status") == "ranked"
    }


def quadrant(numeric_score: float, language_score: float) -> str:
    if numeric_score >= 50 and language_score >= 50:
        return "Confirmed strength"
    if numeric_score < 50 <= language_score:
        return "Potential turnaround"
    if numeric_score >= 50 > language_score:
        return "Early warning"
    return "High-risk screen"


def build_archive(reports_dir: Path, output_path: Path) -> dict:
    manifest = load_language_manifest()
    numeric_scores = load_numeric_scores()
    analyzed: dict[str, list[dict]] = {}
    for source in manifest:
        path = Path(source["path"])
        if not path.is_absolute():
            path = reports_dir / source["ticker"] / path.name
        if not path.exists():
            print(f"Skipping missing curated report: {path}", flush=True)
            continue
        analyzed.setdefault(source["ticker"], []).append(analyze_pdf(path, source))
    latest_documents = {
        ticker: max(documents, key=lambda document: period_sort_key(document["period"]))
        for ticker, documents in analyzed.items()
    }
    calibration = calibrate_peer_language_scores(list(latest_documents.values()))
    signals = []
    for bank in load_universe():
        ticker = bank["ticker"]
        numeric_score = numeric_scores.get(ticker)
        documents = analyzed.get(ticker, [])
        language = latest_documents.get(ticker)
        if not language or language["status"] == "insufficient":
            signals.append(
                {
                    "ticker": ticker,
                    "bank_name": bank["bank_name"],
                    "numeric_score": numeric_score,
                    "language_score": None,
                    "absolute_language_score": None,
                    "negative_pressure_score": None,
                    "language_drift_score": None,
                    "divergence": None,
                    "quadrant": None,
                    "status": "insufficient_language_data",
                    "alerts": [],
                    "publication_eligible": False,
                }
            )
            continue
        history = summarize_history(documents)
        language["history_periods"] = history["history_periods"]
        language["language_drift_score"] = history["language_drift_score"]
        language["directional_reversal"] = history["directional_reversal"]
        language["drift_status"] = history["drift_status"]
        language["drift_observations"] = history["drift_observations"]
        language_score = language["features"]["language_score"]
        absolute_language_score = language["features"]["absolute_language_score"]
        negative_pressure_score = language["features"]["negative_pressure_score"]
        divergence = round(numeric_score - language_score, 1) if numeric_score is not None else None
        alerts = []
        if divergence is not None and abs(divergence) >= 20:
            alerts.append(
                {
                    "type": "numeric_language_divergence",
                    "severity": "research_review",
                    "message": f"Numeric-language gap reached {divergence:+.1f} points.",
                    "review_status": "pending_human_review",
                }
            )
        status = (
            "provisional_four_period_trend"
            if history["history_periods"] >= 4
            else "provisional_single_period"
        )
        signals.append(
            {
                "ticker": ticker,
                "bank_name": bank["bank_name"],
                "numeric_score": numeric_score,
                "language_score": language_score,
                "absolute_language_score": absolute_language_score,
                "negative_pressure_score": negative_pressure_score,
                "language_drift_score": history["language_drift_score"],
                "directional_reversal": history["directional_reversal"],
                "history_periods": history["history_periods"],
                "divergence": divergence,
                "quadrant": quadrant(numeric_score, language_score),
                "status": status,
                "alerts": alerts,
                "publication_eligible": False,
            }
        )

    archive = {
        "schema_version": "1.1",
        "rule_version": RULE_VERSION,
        "generated_at": utc_now(),
        "methodology": {
            "axes_are_independent": True,
            "language_model": "deterministic_financial_lexicon",
            "language_score_calibration": calibration,
            "negative_pressure_weights": {
                "negative_terms": 2.0,
                "uncertainty": 1.35,
                "weak_modals": 1.75,
                "caution_or_euphemism": 1.15,
            },
            "drift_penalty": (
                "Weak-modal and uncertainty increases, caution increases, and "
                "confidence declines are activated only for comparable history."
            ),
            "minimum_history_for_preliminary_trend": 4,
            "minimum_history_for_drift_alerts": 8,
            "publication_gate": "backtest_and_human_review_required",
            "labels_are_research_screens_not_investment_recommendations": True,
        },
        "coverage": {
            "universe_banks": len(signals),
            "provisional_banks": sum(s["status"].startswith("provisional") for s in signals),
            "four_period_trends": sum(s["status"] == "provisional_four_period_trend" for s in signals),
            "insufficient_banks": sum(s["status"] == "insufficient_language_data" for s in signals),
        },
        "documents": [
            document
            for documents in analyzed.values()
            for document in sorted(documents, key=lambda item: period_sort_key(item["period"]))
        ],
        "signals": signals,
    }
    output_path.write_text(json.dumps(archive, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"Wrote {output_path}: {archive['coverage']['provisional_banks']} provisional, "
        f"{archive['coverage']['insufficient_banks']} insufficient."
    )
    return archive


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    build_archive(arguments.reports_dir.resolve(), arguments.output.resolve())
