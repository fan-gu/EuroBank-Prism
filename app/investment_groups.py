"""Transparent three-axis investment-value group rules.

The groups preserve disagreement between fundamentals, management language,
and price confirmation. They are research-screen labels, not advice.
"""

DEFAULT_THRESHOLDS = {
    "numeric_mid": 50.0,
    "numeric_high": 60.0,
    "language_mid": 50.0,
    "language_high": 60.0,
    "price_low": 40.0,
    "price_mid": 50.0,
    "price_high": 60.0,
}

GROUP_ORDER = (
    "Conviction Leaders",
    "Strong Signals, Weak Price",
    "Cautious Value",
    "Price Ahead of Fundamentals",
    "Story Ahead of Numbers",
    "Downside Risk",
)

GROUP_META = {
    "Conviction Leaders": {
        "color": "#35C48D",
        "meaning": "All three signals agree: strong fundamentals, supportive language and confirming price action.",
        "signals": (
            "📊 Fundamentals  ✅",
            "🗣️ Management language  💪",
            "📈 Price confirmation  ↑",
        ),
        "summary": "All three signals agree.",
    },
    "Strong Signals, Weak Price": {
        "color": "#4FA3FF",
        "meaning": "Fundamentals and language are supportive, but price action has not yet confirmed the thesis.",
        "signals": (
            "📊 Fundamentals  ✅",
            "🗣️ Management language  💪",
            "📈 Price confirmation  ↓",
        ),
        "summary": "Strong case; price has not confirmed it.",
    },
    "Cautious Value": {
        "color": "#FFD84D",
        "meaning": "Fundamentals are at or above the peer median and price avoids the bottom tier, while language remains cautious.",
        "signals": (
            "📊 Fundamentals  ✅",
            "🗣️ Management language  ⚠️",
            "📈 Price confirmation  ↔",
        ),
        "summary": "Value support, but management stays cautious.",
    },
    "Price Ahead of Fundamentals": {
        "color": "#9B7BFF",
        "meaning": "Price action is stronger than the fundamental case; further upside may depend on future delivery.",
        "signals": (
            "📊 Fundamentals  ⚠️",
            "🗣️ Management language  ↔",
            "📈 Price confirmation  ↑",
        ),
        "summary": "Price leads; verify future delivery.",
    },
    "Story Ahead of Numbers": {
        "color": "#F28E5B",
        "meaning": "Management language is materially stronger than the accounts; verify whether delivery catches up with the story.",
        "signals": (
            "📊 Fundamentals  ↓",
            "🗣️ Management language  💪",
            "📈 Price confirmation  ↔",
        ),
        "summary": "Management's story leads the numbers.",
    },
    "Downside Risk": {
        "color": "#EF6262",
        "meaning": "Weak fundamentals have a confirming warning, or apparently stronger fundamentals face both cautious language and bottom-tier price action.",
        "signals": (
            "📊 Fundamentals  ↓",
            "🗣️ Management language  ⚠️",
            "📈 Price confirmation  ↓",
        ),
        "summary": "Weak inputs reinforce the risk case.",
    },
    "Insufficient Evidence": {
        "color": "#9FA8B8",
        "meaning": "At least one coordinate is unavailable; no investment-value group is inferred.",
    },
}


def _quantile(values: list[float], probability: float) -> float:
    """Return a linearly interpolated quantile without a heavy dependency."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a threshold from an empty axis")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def derive_group_thresholds(rows: list[dict]) -> dict[str, float]:
    """Derive axis-specific peer gates from the current complete cross-section."""
    complete = [
        row for row in rows
        if all(isinstance(row.get(key), (int, float)) for key in ("numeric", "language", "price"))
    ]
    if len(complete) < 5:
        return DEFAULT_THRESHOLDS.copy()
    axes = {
        key: [float(row[key]) for row in complete]
        for key in ("numeric", "language", "price")
    }
    return {
        "numeric_mid": _quantile(axes["numeric"], 0.50),
        "numeric_high": _quantile(axes["numeric"], 0.60),
        "language_mid": _quantile(axes["language"], 0.50),
        "language_high": _quantile(axes["language"], 0.60),
        "price_low": _quantile(axes["price"], 0.40),
        "price_mid": _quantile(axes["price"], 0.50),
        "price_high": _quantile(axes["price"], 0.60),
    }


def investment_group(
    numeric_score,
    language_score,
    price_score,
    thresholds: dict[str, float] | None = None,
) -> str:
    """Assign one mutually exclusive group without blending the three axes."""
    values = (numeric_score, language_score, price_score)
    if not all(isinstance(value, (int, float)) for value in values):
        return "Insufficient Evidence"

    numeric = float(numeric_score)
    language = float(language_score)
    price = float(price_score)
    gates = DEFAULT_THRESHOLDS if thresholds is None else thresholds

    # Six directional research outcomes. Missing evidence remains a separate
    # publication gate and is not counted as an investment group.
    # The gates are axis-specific peer percentiles.  A supportive language
    # reading is above its median; it need not clear the much stricter 60th
    # percentile to corroborate a genuinely strong numeric and price case.
    if (
        numeric >= gates["numeric_high"]
        and language >= gates["language_mid"]
        and price >= gates["price_high"]
    ):
        return "Conviction Leaders"
    if (
        numeric >= gates["numeric_mid"]
        and language >= gates["language_mid"]
        and price < gates["price_high"]
    ):
        return "Strong Signals, Weak Price"
    if numeric < gates["numeric_mid"] and language >= gates["language_high"]:
        return "Story Ahead of Numbers"
    if numeric < gates["numeric_high"] and price >= gates["price_high"]:
        return "Price Ahead of Fundamentals"
    if (
        numeric < gates["numeric_mid"]
        and language >= gates["language_mid"]
        and price >= gates["price_mid"]
    ):
        return "Story Ahead of Numbers"
    if (
        numeric >= gates["numeric_mid"]
        and language < gates["language_mid"]
        and price >= gates["price_low"]
    ):
        return "Cautious Value"
    if (
        numeric < gates["numeric_mid"]
        and (language < gates["language_mid"] or price < gates["price_mid"])
    ) or (
        numeric >= gates["numeric_mid"]
        and language < gates["language_mid"]
        and price < gates["price_low"]
    ):
        return "Downside Risk"
    return "Downside Risk"


def evidence_status(history_periods: int | None) -> str:
    """Gate the language-history confidence independently from group identity."""
    if not isinstance(history_periods, int) or history_periods < 1:
        return "insufficient"
    if history_periods < 4:
        return "provisional"
    return "four-period trend available"
