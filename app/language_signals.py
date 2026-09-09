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
RULE_VERSION = "management-language-v2.4.2"

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
# Results decks often repeat legal language whose purpose is liability control,
# not management communication.  In particular, counting words such as
# "may", "could" and "risk" inside a safe-harbour statement would create a
# false caution signal.  Keep these patterns deliberately specific so genuine
# guidance and risk commentary remain eligible.
LEGAL_BOILERPLATE = re.compile(
    r"\b(?:forward\s*[-–—]?\s*looking statements?|safe[- ]harbou?r|cautionary "
    r"statements?|important (?:legal )?notice|legal disclaimer|disclaimer|"
    r"actual (?:events or )?results (?:may|might|could) differ materially|"
    r"(?:could cause |may cause )?actual results to differ|"
    r"no representation or warranty|does not constitute (?:an )?(?:offer|"
    r"recommendation|solicitation)|offer to (?:buy|sell)|solicitation of "
    r"(?:an )?offer|for information purposes only|should not be relied (?:on|upon)|"
    r"undertakes? no (?:obligation|duty) to update|under no obligation to update|"
    r"securities act|prospectus|inside information|market abuse regulation|"
    r"not intended to be (?:and should not be construed as )?(?:legal|tax|"
    r"accounting|investment) advice|alternative performance measures? "
    r"(?:are|is) defined|non[- ]gaap measures? (?:are|is) defined)\b",
    flags=re.IGNORECASE,
)
BOILERPLATE_PAGE_HEADING = re.compile(
    r"\b(?:important (?:legal )?notice|disclaimer|legal notice|safe[- ]harbou?r|"
    r"forward\s*[-–—]?\s*looking statements?|cautionary statement|alternative "
    r"performance measures?|glossary)\b",
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

# Banking disclosures use "risk" extensively as a neutral taxonomy or metric
# label. Only the risk token inside these compounds is masked for lexicon hit
# counting; the original sentence and its word-count denominator are retained.
NEUTRAL_RISK_COMPOUNDS = re.compile(
    r"\b(?:cost of risks?|risk[- ]weighted(?: assets?)?|credit risks?|"
    r"counterparty (?:credit )?risks?|operational risks?|market risks?|"
    r"liquidity risks?|interest(?:[- ]rate)? risks?|insurance risks?|"
    r"model risks?|risk appetite|risk management|risk profile|"
    r"risk parameters?|risk architecture|risk framework|risk function|"
    r"risk committee|chief risk officer|risk models?|risk taxonom(?:y|ies)|"
    r"risk governance|risk data|risk reporting|risk weights?|risk culture)\b",
    flags=re.IGNORECASE,
)
# Routine distribution and governance conditions are often printed as tiny
# footnotes on results slides. They are legally/procedurally meaningful, but
# they are not evidence that management's operating outlook has weakened.
# Match only the procedural clause so meaningful narrative that happens to be
# joined to a footnote by PDF extraction can still be scored.
PROCEDURAL_CONDITION_PATTERNS = (
    re.compile(
        r"\b(?:dividends?|distributions?|payouts?|share buybacks?|"
        r"interim profits?|full[- ]year profits?|implementation|"
        r"completion)\b.{0,100}?\b(?:subject to|pending)\b.{0,180}?\b(?:"
        r"targets?(?:['’]s)? achievement|approval(?:s)?|authori[sz]ation|"
        r"corporate law requirements?|customary conditions?|board resolution)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:subject to|pending)\b.{0,160}?\b(?:ECB|AGM|shareholders?|"
        r"supervisory|regulatory|governing bod(?:y|ies)|board|BoD|corporate)\b"
        r".{0,100}?\b(?:approval(?:s)?|authori[sz]ation|resolution|"
        r"requirements?|conditions?)\b",
        flags=re.IGNORECASE,
    ),
)
SUBSTANTIVE_CONDITION_TERMS = re.compile(
    r"\b(?:macro(?:economic)?|market|economic|business|funding|liquidity|"
    r"credit|asset quality|capital ratio|CET1|earnings|revenue|cost) "
    r"conditions?\b",
    flags=re.IGNORECASE,
)
# Standard table-arithmetic notes describe presentation precision, not
# management conviction. They commonly trigger the weak modal ``may`` and must
# therefore be removed before language scoring.
STANDARDIZED_CALCULATION_FOOTNOTE = re.compile(
    r"(?:\bnote\s*:\s*)?(?:"
    r"(?:the\s+)?sum\s+of\s+values\s+(?:contained\s+)?in\s+(?:the\s+)?"
    r"tables?\s+and\s+analyses\s+may\s+differ\s+slightly\s+from\s+"
    r"(?:the\s+)?total\s+reported\s+due\s+to\s+rounding(?:\s+rules?)?|"
    r"(?:figures?|numbers?|totals?)\s+may\s+not\s+add\s+up(?:\s+exactly)?"
    r"\s+due\s+to\s+rounding(?:\s+rules?)?|"
    r"(?:figures?|numbers?|totals?)\s+may\s+differ(?:\s+slightly)?\s+"
    r"(?:from\s+(?:the\s+)?reported\s+total\s+)?due\s+to\s+rounding"
    r"(?:\s+rules?)?)",
    flags=re.IGNORECASE,
)
NEGATOR_TOKENS = {
    "no", "not", "without", "lower", "reduced", "limited", "immaterial",
    "absent", "negligible", "contained", "declining",
}
NEGATION_WINDOW = 4
POST_HIT_RELIEF = re.compile(
    r"^\W*(?:is|are|was|were|remain|remains|remained|became|becomes)\s+"
    r"(?:(?:materially|largely|well|very)\s+)?"
    r"(?:lower|reduced|limited|immaterial|absent|negligible|contained|declining)\b",
    flags=re.IGNORECASE,
)
STRONG_PRIOR_TECHNICAL_MARKERS = re.compile(
    r"\b(?:as a reminder|restatement|restated to reflect|restated for|"
    r"previously reported figures? (?:were|have been) restated)\b",
    flags=re.IGNORECASE,
)
WEAK_PRIOR_PERIOD_MARKERS = re.compile(
    r"\b(?:prior (?:year|period|quarter)|comparative period|last year|"
    r"historical (?:basis|scope))\b",
    flags=re.IGNORECASE,
)
TECHNICAL_RESTATEMENT_CONTEXT = re.compile(
    r"\b(?:accounting|classification|methodology|perimeter|presentation|"
    r"reported|published|series|figures?|tables?|data|basis|scope|note)\b",
    flags=re.IGNORECASE,
)
CURRENT_NARRATIVE_ANCHOR = re.compile(
    r"\b(?:current(?:ly)?|now|today|going forward|outlook|guidance|"
    r"we (?:expect|will|aim|target|confirm|now expect))\b",
    flags=re.IGNORECASE,
)
CURRENT_DIRECTIONAL_LANGUAGE = re.compile(
    r"\b(?:increase[ds]?|decrease[ds]?|improve[ds]?|decline[ds]?|grew|grown|"
    r"rose|risen|fell|fallen|strong|robust|resilient|solid|stronger|weaker|"
    r"higher|lower|stable|stabilised|"
    r"stabilized|accelerat(?:e|ed|ing)|slow(?:ed|ing))\b",
    flags=re.IGNORECASE,
)
COUNTRY_CODES = {
    "Austria": "AT", "Belgium": "BE", "Finland": "FI", "France": "FR",
    "Germany": "DE", "Ireland": "IE", "Italy": "IT",
    "Netherlands": "NL", "Spain": "ES",
}
FILTER_EXAMPLE_LIMIT = 5
NEAR_DUPLICATE_MIN_CHARS = 120


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


def mask_neutral_risk_terms(text: str) -> tuple[str, int]:
    """Mask only risk tokens that occur inside neutral banking compounds."""
    count = 0

    def _mask_compound(match: re.Match) -> str:
        nonlocal count
        compound = match.group(0)
        masked, risk_tokens = re.subn(
            r"\brisks?\b",
            lambda risk_match: " " * len(risk_match.group(0)),
            compound,
            flags=re.IGNORECASE,
        )
        count += risk_tokens
        return masked

    return NEUTRAL_RISK_COMPOUNDS.sub(_mask_compound, text), count


def mask_procedural_condition_footnotes(text: str) -> tuple[str, int]:
    """Mask routine approval/target-condition footnotes, preserving offsets.

    This is deliberately narrower than a generic ``subject to`` rule. For
    example, guidance that is subject to macro or market conditions remains
    scoreable because it conveys substantive uncertainty.
    """
    masked = text
    count = 0

    def _mask(match: re.Match) -> str:
        nonlocal count
        # A clause that also names an operating or market condition is a real
        # management caveat, even when a regulatory condition follows it.
        if SUBSTANTIVE_CONDITION_TERMS.search(match.group(0)):
            return match.group(0)
        count += 1
        return " " * len(match.group(0))

    for pattern in PROCEDURAL_CONDITION_PATTERNS:
        masked = pattern.sub(_mask, masked)
    return masked, count


def mask_standardized_calculation_footnotes(text: str) -> tuple[str, int]:
    """Mask routine rounding/summation notes while preserving source offsets."""
    return STANDARDIZED_CALCULATION_FOOTNOTE.subn(
        lambda match: " " * len(match.group(0)),
        text,
    )


def _phrase_matches(text: str, phrase: str):
    return re.finditer(rf"\b{re.escape(phrase)}\b", text, flags=re.IGNORECASE)


def _hit_is_reassuring(text: str, match: re.Match) -> bool:
    # A negator cannot govern a hit across a sentence, bullet, or clause break.
    preceding_text = text[:match.start()]
    boundary = max(
        (preceding_text.rfind(character) for character in ".;:!?•▪|"),
        default=-1,
    )
    preceding = [
        token.group(0).lower()
        for token in WORD_RE.finditer(preceding_text[boundary + 1:])
    ][-NEGATION_WINDOW:]
    negators = sum(token in NEGATOR_TOKENS for token in preceding)
    if negators == 1:
        negator_index = next(
            index for index, token in enumerate(preceding)
            if token in NEGATOR_TOKENS
        )
        scope_breakers = {
            "although", "but", "despite", "due", "from", "however",
            "whereas", "while",
        }
        if any(token in scope_breakers for token in preceding[negator_index + 1:]):
            return False
        return True
    if negators > 1:
        return False
    return bool(POST_HIT_RELIEF.match(text[match.end():match.end() + 80]))


def negation_dropped_categories(text: str) -> dict[str, int]:
    """Count negative/uncertainty occurrences neutralised by relief wording."""
    dropped = {"negative": 0, "uncertainty": 0}
    for category in dropped:
        for phrase in LEXICONS[category]:
            dropped[category] += sum(
                _hit_is_reassuring(text, match)
                for match in _phrase_matches(text, phrase)
            )
    return dropped


def normalized_sentence_key(sentence: str, collapse_numbers: bool = False) -> str:
    """Create a Unicode-safe deterministic sentence key."""
    text = sentence.casefold()
    if collapse_numbers:
        text = re.sub(r"\d[\d.,]*", "#", text)
    text = "".join(character if character.isalnum() or character == "#" else " " for character in text)
    return re.sub(r"\s+", " ", text).strip()


def register_sentence(
    sentence: str,
    seen_exact: set[str],
    seen_templates: set[str],
) -> tuple[bool, str]:
    """Register a sentence and report safe exact/template duplication."""
    exact_key = normalized_sentence_key(sentence)
    if not exact_key:
        return False, exact_key
    if exact_key in seen_exact:
        return True, exact_key
    seen_exact.add(exact_key)

    template_key = normalized_sentence_key(sentence, collapse_numbers=True)
    template_eligible = (
        len(template_key) >= NEAR_DUPLICATE_MIN_CHARS
        and not GUIDANCE_TERMS.search(sentence)
        and not CURRENT_DIRECTIONAL_LANGUAGE.search(sentence)
    )
    if template_eligible and template_key in seen_templates:
        return True, template_key
    if template_eligible:
        seen_templates.add(template_key)
    return False, exact_key


def is_prior_period_technical(sentence: str, period: str | None = None) -> bool:
    """Exclude administrative historical notes, not useful comparisons."""
    current_narrative = bool(
        CURRENT_NARRATIVE_ANCHOR.search(sentence)
        or CURRENT_DIRECTIONAL_LANGUAGE.search(sentence)
        or GUIDANCE_TERMS.search(sentence)
    )
    if STRONG_PRIOR_TECHNICAL_MARKERS.search(sentence):
        return not current_narrative
    if not (
        WEAK_PRIOR_PERIOD_MARKERS.search(sentence)
        and TECHNICAL_RESTATEMENT_CONTEXT.search(sentence)
    ):
        return False

    # Period metadata replaces brittle hard-coded calendar years. A technical
    # comparative that also discusses the document's current year is retained.
    current_year_match = re.search(r"20\d{2}", period or "")
    current_year = current_year_match.group(0) if current_year_match else None
    current_year_present = bool(
        current_year and re.search(rf"\b{re.escape(current_year)}\b", sentence)
    )
    return not current_narrative and not current_year_present


def add_filter_example(
    examples: dict[str, list[dict]],
    category: str,
    page: int,
    sentence: str,
    **details,
) -> None:
    if len(examples[category]) >= FILTER_EXAMPLE_LIMIT:
        return
    examples[category].append(
        {"page": page, "sentence": sentence, **details}
    )


def is_legal_boilerplate(sentence: str) -> bool:
    """Identify standard legal text that must not influence language scores."""
    return bool(LEGAL_BOILERPLATE.search(sentence))


def is_boilerplate_page(page_text: str) -> bool:
    """Reject dedicated disclaimer pages while preserving mixed content pages."""
    opening = clean_text(page_text)[:1_200]
    if BOILERPLATE_PAGE_HEADING.search(opening[:350]):
        return True
    # Some slide decks place a company title before the legal heading.  Two
    # distinct legal markers in the opening reliably identify a dedicated
    # boilerplate slide without discarding an ordinary slide footer.
    markers = {
        match.group(0).lower()
        for match in LEGAL_BOILERPLATE.finditer(opening)
    }
    return len(markers) >= 2


def relevant_sentence(sentence: str) -> bool:
    if EXCLUDED_CONTEXT.search(sentence) or is_legal_boilerplate(sentence):
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


def quantile(values: list[float], probability: float) -> float | None:
    """Return a linearly interpolated quantile for a non-empty peer sample."""
    ordered = sorted(float(value) for value in values if isinstance(value, (int, float)))
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


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
    same_series = [
        document
        for document in ordered
        if document.get("document_series", "management_results") == latest_series
    ]
    # Drift requires adjacent reporting checkpoints. Four files spread across
    # several years are not a four-period trend. Keep only the uninterrupted
    # sequence ending at the latest period and de-duplicate equivalent labels
    # such as Q2/H1 or Q4/FY.
    by_checkpoint = {}
    for document in same_series:
        year, checkpoint = period_sort_key(document["period"])
        if not year or not checkpoint:
            continue
        by_checkpoint[year * 4 + checkpoint] = document
    if not by_checkpoint:
        return []
    latest_checkpoint = max(by_checkpoint)
    contiguous = []
    checkpoint = latest_checkpoint
    while checkpoint in by_checkpoint:
        contiguous.append(by_checkpoint[checkpoint])
        checkpoint -= 1
    return list(reversed(contiguous))


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
            "available_documents": len(documents),
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
        "available_documents": len(documents),
        "history_periods": len(history),
        "language_drift_score": round(sum(penalties) / len(penalties), 2),
        "directional_reversal": any(observation["directional_reversal"] for observation in observations),
        "drift_observations": observations,
        "drift_status": "preliminary_four_period_trend",
    }


def warning_evidence(document: dict, limit: int = 3) -> list[dict]:
    """Return the strongest caution passages for an auditable triage card."""
    candidates = []
    for item in document.get("evidence", []):
        hits = item.get("hits", {})
        pressure = (
            2.0 * hits.get("negative", 0)
            + 1.35 * hits.get("uncertainty", 0)
            + 1.75 * hits.get("weak_modal", 0)
            + 1.15 * hits.get("caution_buffer", 0)
        )
        if pressure > 0:
            candidates.append((pressure, item))
    candidates.sort(key=lambda row: row[0], reverse=True)
    return [item for _, item in candidates[:limit]]


def build_language_alerts(
    language: dict,
    history: dict,
    divergence: float | None,
    thresholds: dict[str, float | None],
) -> list[dict]:
    """Create review-only alerts from every warning-bearing language feature."""
    alerts = []
    if divergence is not None and abs(divergence) >= 20:
        alerts.append({
            "type": "numeric_language_divergence",
            "severity": "research_review",
            "message": f"Numeric-language gap reached {divergence:+.1f} points.",
            "review_status": "pending_human_review",
        })

    features = language["features"]
    pressure_threshold = thresholds.get("negative_pressure")
    pressure = features.get("negative_pressure_score")
    if pressure_threshold is not None and pressure is not None and pressure >= pressure_threshold:
        drivers = []
        for feature, label in (
            ("weak_modal_per_1000_words", "weak commitment"),
            ("uncertainty_per_1000_words", "uncertainty"),
            ("caution_per_1000_words", "cautious/euphemistic wording"),
            ("negative_per_1000_words", "negative wording"),
        ):
            threshold = thresholds.get(feature)
            if threshold is not None and features.get(feature, 0) >= threshold:
                drivers.append(label)
        suffix = f" Main drivers: {', '.join(drivers)}." if drivers else ""
        alerts.append({
            "type": "elevated_negative_language_pressure",
            "severity": "research_review",
            "message": (
                f"Negative-language pressure is in the peer top quartile "
                f"({pressure:.1f} versus {pressure_threshold:.1f} gate).{suffix}"
            ),
            "review_status": "pending_human_review",
        })

    if history.get("directional_reversal"):
        alerts.append({
            "type": "confidence_to_caution_reversal",
            "severity": "research_review",
            "message": "Comparable-period language shifted from confidence toward caution.",
            "review_status": "pending_human_review",
        })

    drift = history.get("language_drift_score")
    drift_threshold = thresholds.get("language_drift")
    if drift is not None and drift_threshold is not None and drift >= drift_threshold:
        latest_change = history.get("drift_observations", [])[-1]
        alerts.append({
            "type": "adverse_language_drift",
            "severity": "research_review",
            "message": (
                f"Adverse wording drift is in the peer top quartile ({drift:.1f}); "
                f"latest move {latest_change.get('from_period')} → "
                f"{latest_change.get('to_period')}."
            ),
            "review_status": "pending_human_review",
        })
    return alerts


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


def infer_document_series(path: Path, source: dict) -> str:
    """Classify disclosure genre so drift never mixes releases and decks."""
    declared = source.get("document_series")
    text = " ".join(
        str(value or "").lower()
        for value in (
            path.name,
            source.get("filename"),
            source.get("download_url"),
            source.get("label"),
        )
    )
    # Older manifests used the catch-all `other` label before URLs such as
    # `press-presentation.pdf` were recognized. Upgrade only when the artifact
    # itself provides unambiguous genre evidence.
    if declared and declared not in {"management_results", "management_results_other"}:
        return declared
    if any(term in text for term in ("release", "announcement", "press-release", "persbericht")):
        return "management_results_release"
    if any(term in text for term in ("presentation", "slides", "analyst")):
        return "management_results_presentation"
    if "annual" in text:
        return "annual_management_report"
    return "management_results_other"


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
    pre_filter_word_count = 0
    page_count = 0
    eligible_page_count = 0
    excluded_boilerplate_pages = 0
    excluded_boilerplate_passages = 0
    masked_neutral_risk_spans = 0
    deduplicated_repeats = 0
    negated_hits_dropped = 0
    excluded_prior_period_passages = 0
    masked_procedural_condition_spans = 0
    excluded_procedural_condition_passages = 0
    masked_standardized_footnote_spans = 0
    excluded_standardized_footnote_passages = 0
    seen_exact: set[str] = set()
    seen_templates: set[str] = set()
    filter_examples = {
        "neutral_risk": [],
        "duplicates": [],
        "negation": [],
        "prior_period": [],
        "procedural_conditions": [],
        "standardized_footnotes": [],
    }

    reader = PdfReader(str(path))
    print(f"Analyzing {ticker}: {path.name} ({len(reader.pages)} pages)", flush=True)
    for page_number, page in enumerate(reader.pages, start=1):
        page_count += 1
        page_text = clean_text(page.extract_text() or "")
        if not page_text or not page_is_eligible(page_text, document_type):
            continue
        eligible_page_count += 1
        if is_boilerplate_page(page_text):
            excluded_boilerplate_pages += 1
            continue
        for sentence in split_sentences(page_text):
            if is_legal_boilerplate(sentence):
                excluded_boilerplate_passages += 1
                continue
            if not relevant_sentence(sentence):
                continue
            words = WORD_RE.findall(sentence)
            if not words:
                continue
            pre_filter_word_count += len(words)
            if is_prior_period_technical(sentence, period):
                excluded_prior_period_passages += 1
                add_filter_example(
                    filter_examples, "prior_period", page_number, sentence
                )
                continue
            duplicate, duplicate_key = register_sentence(
                sentence, seen_exact, seen_templates
            )
            if duplicate:
                deduplicated_repeats += 1
                add_filter_example(
                    filter_examples,
                    "duplicates",
                    page_number,
                    sentence,
                    normalized_key=duplicate_key,
                )
                continue

            filtered_sentence, procedural_count = mask_procedural_condition_footnotes(
                sentence
            )
            masked_procedural_condition_spans += procedural_count
            if procedural_count:
                add_filter_example(
                    filter_examples,
                    "procedural_conditions",
                    page_number,
                    sentence,
                    masked_spans=procedural_count,
                )
                # A standalone routine footnote contributes neither lexicon
                # hits nor denominator words. Mixed passages retain only their
                # substantive narrative after the procedural clause is masked.
            filtered_sentence, standardized_count = (
                mask_standardized_calculation_footnotes(filtered_sentence)
            )
            masked_standardized_footnote_spans += standardized_count
            if standardized_count:
                add_filter_example(
                    filter_examples,
                    "standardized_footnotes",
                    page_number,
                    sentence,
                    masked_spans=standardized_count,
                )

            if not WORD_RE.search(filtered_sentence) or not relevant_sentence(
                filtered_sentence
            ):
                if procedural_count:
                    excluded_procedural_condition_passages += 1
                if standardized_count:
                    excluded_standardized_footnote_passages += 1
                continue

            words = WORD_RE.findall(filtered_sentence)
            if not words:
                continue
            filtered_sentence, masked_count = mask_neutral_risk_terms(
                filtered_sentence
            )
            masked_neutral_risk_spans += masked_count
            filters_applied = []
            if procedural_count:
                filters_applied.append(
                    f"procedural_condition_masked:{procedural_count}"
                )
            if standardized_count:
                filters_applied.append(
                    f"standardized_footnote_masked:{standardized_count}"
                )
            if masked_count:
                filters_applied.append(f"risk_masked:{masked_count}")
                add_filter_example(
                    filter_examples,
                    "neutral_risk",
                    page_number,
                    sentence,
                    masked_spans=masked_count,
                )
            hits = category_hits(filtered_sentence)
            dropped = negation_dropped_categories(filtered_sentence)
            dropped_count = sum(dropped.values())
            if dropped_count:
                for category, value in dropped.items():
                    hits[category] = max(0, hits[category] - value)
                negated_hits_dropped += dropped_count
                filters_applied.append(f"negated_drop:{dropped_count}")
                add_filter_example(
                    filter_examples,
                    "negation",
                    page_number,
                    sentence,
                    dropped=dropped,
                )
            word_count += len(words)
            for category, value in hits.items():
                counts[category] += value
            if any(hits.values()) or GUIDANCE_TERMS.search(sentence):
                evidence.append(
                    {
                        "page": page_number,
                        "sentence": sentence,
                        "is_guidance": bool(GUIDANCE_TERMS.search(sentence)),
                        "hits": hits,
                        "filters_applied": filters_applied,
                        "review_status": "pending_human_review",
                    }
                )

    features = score_features(counts, word_count)
    filter_shrink_ratio = round(
        (pre_filter_word_count - word_count) / max(pre_filter_word_count, 1),
        4,
    )
    evidence.sort(key=evidence_priority, reverse=True)
    selected_evidence = evidence[:8]
    standard_coverage = word_count >= 150 and len(selected_evidence) >= 3
    limited_coverage = word_count >= 80 and len(selected_evidence) >= 2
    record = {
        "ticker": ticker,
        "bank_name": source.get("bank_name"),
        "document": path.name,
        "document_type": document_type,
        "document_series": infer_document_series(path, source),
        "period": period,
        "publication_date": None,
        "source_url": source.get("download_url"),
        "official_page": source.get("official_page"),
        "source_status": source.get("source_status", "curated"),
        "document_sha256": sha256(path),
        "page_count": page_count,
        "eligible_page_count": eligible_page_count,
        "excluded_boilerplate_pages": excluded_boilerplate_pages,
        "excluded_boilerplate_passages": excluded_boilerplate_passages,
        "masked_neutral_risk_spans": masked_neutral_risk_spans,
        "deduplicated_repeats": deduplicated_repeats,
        "negated_hits_dropped": negated_hits_dropped,
        "excluded_prior_period_passages": excluded_prior_period_passages,
        "masked_procedural_condition_spans": masked_procedural_condition_spans,
        "excluded_procedural_condition_passages": excluded_procedural_condition_passages,
        "masked_standardized_footnote_spans": masked_standardized_footnote_spans,
        "excluded_standardized_footnote_passages": excluded_standardized_footnote_passages,
        "pre_filter_analyzed_word_count": pre_filter_word_count,
        "analyzed_word_count": word_count,
        "filter_shrink_ratio": filter_shrink_ratio,
        "filter_shrink_warning": filter_shrink_ratio > 0.25,
        "filter_examples": filter_examples,
        "feature_counts": counts,
        "features": features,
        "evidence": selected_evidence,
        "status": "provisional_single_period" if limited_coverage else "insufficient",
        "coverage_quality": "standard" if standard_coverage else (
            "limited" if limited_coverage else "insufficient"
        ),
        "history_periods": 1,
        "language_drift_score": None,
        "directional_reversal": None,
        "drift_status": "requires_comparable_history",
        "backtest_status": "not_run",
        "publication_eligible": False,
        "comparability_warning": (
            "Limited narrative sample; interpret with extra caution."
            if limited_coverage and not standard_coverage
            else "Single-period evidence; do not interpret as a trading signal."
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
                "curated", "pending_human_review", "manually_verified_official"
            }:
                continue
            seen.add(key)
            records.append(record)
    return records


def load_universe() -> list[dict]:
    path = BASE_DIR / "bank_master.json"
    return json.loads(path.read_text(encoding="utf-8"))["constituents"]


def build_modal_diagnostics(
    latest_documents: dict[str, dict],
    universe: list[dict],
) -> dict:
    """Describe modal-rate dispersion without changing any score."""
    bank_by_ticker = {bank["ticker"]: bank for bank in universe}
    observations = []
    for ticker, document in latest_documents.items():
        if document.get("status") == "insufficient":
            continue
        bank = bank_by_ticker.get(ticker, {})
        country_name = bank.get("country", "Unknown")
        observations.append(
            {
                "ticker": ticker,
                "country": COUNTRY_CODES.get(country_name, country_name),
                "genre": document.get("document_type", "unclassified"),
                "weak_modal_per_1000": document["features"]["weak_modal_per_1000_words"],
                "uncertainty_per_1000": document["features"]["uncertainty_per_1000_words"],
            }
        )

    def _profiles(group_key: str) -> dict:
        groups: dict[str, list[dict]] = {}
        for observation in observations:
            groups.setdefault(observation[group_key], []).append(observation)
        return {
            group: {
                "banks": sorted(row["ticker"] for row in rows),
                "bank_count": len(rows),
                "weak_modal_per_1000_median": round(
                    statistics.median(row["weak_modal_per_1000"] for row in rows), 2
                ),
                "uncertainty_per_1000_median": round(
                    statistics.median(row["uncertainty_per_1000"] for row in rows), 2
                ),
                "interpretation": (
                    "descriptive_only"
                    if len(rows) >= 3
                    else "insufficient_group_size_for_inference"
                ),
            }
            for group, rows in sorted(groups.items())
        }

    weak_rates = [row["weak_modal_per_1000"] for row in observations]
    median_rate = statistics.median(weak_rates) if weak_rates else 0.0
    mad = (
        statistics.median(abs(rate - median_rate) for rate in weak_rates)
        if weak_rates
        else 0.0
    )
    review_gate = max(2 * median_rate, median_rate + 2 * mad, 2.0)
    flags = [
        {
            "ticker": row["ticker"],
            "weak_modal_per_1000": row["weak_modal_per_1000"],
            "reason": (
                "weak-modal rate above robust cross-section review gate "
                f"({review_gate:.2f} per 1,000 words)"
            ),
        }
        for row in observations
        if row["weak_modal_per_1000"] > review_gate
    ]
    flags.sort(key=lambda row: row["weak_modal_per_1000"], reverse=True)
    return {
        "scores_affected": False,
        "cross_section_weak_modal_median": round(median_rate, 2),
        "cross_section_weak_modal_mad": round(mad, 2),
        "modal_review_gate": round(review_gate, 2),
        "country_modal_profile": _profiles("country"),
        "genre_modal_profile": _profiles("genre"),
        "modal_review_flags": flags,
    }


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
    universe = load_universe()
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
    histories = {
        ticker: summarize_history(documents)
        for ticker, documents in analyzed.items()
    }
    latest_eligible = [
        document for document in latest_documents.values()
        if document["status"] != "insufficient"
    ]
    alert_thresholds = {
        "negative_pressure": quantile(
            [document["features"]["negative_pressure_score"] for document in latest_eligible],
            0.75,
        ),
        **{
            feature: quantile(
                [document["features"][feature] for document in latest_eligible],
                0.75,
            )
            for feature in (
                "weak_modal_per_1000_words",
                "uncertainty_per_1000_words",
                "caution_per_1000_words",
                "negative_per_1000_words",
            )
        },
        # A four-period trend is still a research observation, not a trading
        # alert. The upper 40% is routed to triage so a reviewer sees it.
        "language_drift": quantile(
            [
                history["language_drift_score"]
                for history in histories.values()
                if history.get("language_drift_score") is not None
            ],
            0.60,
        ),
    }
    signals = []
    for bank in universe:
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
        history = histories[ticker]
        language["history_periods"] = history["history_periods"]
        language["language_drift_score"] = history["language_drift_score"]
        language["directional_reversal"] = history["directional_reversal"]
        language["drift_status"] = history["drift_status"]
        language["drift_observations"] = history["drift_observations"]
        language_score = language["features"]["language_score"]
        absolute_language_score = language["features"]["absolute_language_score"]
        negative_pressure_score = language["features"]["negative_pressure_score"]
        divergence = round(numeric_score - language_score, 1) if numeric_score is not None else None
        alerts = build_language_alerts(
            language,
            history,
            divergence,
            alert_thresholds,
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
                "warning_evidence": warning_evidence(language),
                "publication_eligible": False,
            }
        )

    diagnostics = build_modal_diagnostics(latest_documents, universe)
    archive = {
        "schema_version": "1.4",
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
            "legal_boilerplate_filter": {
                "rule": "dedicated disclaimer pages and standard legal passages are excluded before lexicon scoring",
                "audited_document_fields": [
                    "eligible_page_count",
                    "excluded_boilerplate_pages",
                    "excluded_boilerplate_passages",
                ],
            },
            "pollution_filters": {
                "version": "v2.4.2",
                "description": (
                    "Technical prior-period/restatement passages and safe "
                    "document-level duplicates are excluded before scoring. "
                    "Neutral banking risk compounds are masked for hit counting, "
                    "and negative or uncertainty hits in deterministic relief "
                    "contexts are dropped rather than inverted. Routine "
                    "distribution, approval and target-achievement footnotes are "
                    "excluded or clause-masked without suppressing substantive "
                    "macro or market conditions. Standard table-rounding and "
                    "summation notes are also excluded or clause-masked before "
                    "modal counting. Original evidence text is preserved; neutral "
                    "risk masking and negation leave the word-count denominator "
                    "unchanged, while excluded footnote words leave the denominator. Every action "
                    "is recorded in per-document audit fields; modal-rate country "
                    "and genre diagnostics never affect scores."
                ),
                "audited_document_fields": [
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
                ],
            },
            "narrative_coverage_gate": {
                "standard": "at least 150 narrative words and 3 cited passages",
                "limited": "at least 80 narrative words and 2 cited passages; extra caution required",
                "insufficient": "below the limited gate; excluded from peer calibration",
            },
            "research_triage_thresholds": {
                key: round(value, 4) if isinstance(value, (int, float)) else None
                for key, value in alert_thresholds.items()
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
            "filter_shrink_warnings": sum(
                document.get("filter_shrink_warning", False)
                for documents in analyzed.values()
                for document in documents
            ),
        },
        "diagnostics": diagnostics,
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
