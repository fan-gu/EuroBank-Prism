"""Transparent three-axis investment-value group rules.

The groups preserve disagreement between fundamentals, management language,
and market confirmation.  They are research-screen labels, not advice.
"""

HIGH = 67.0
LOW = 33.0
LEADER_FLOOR = 55.0
WEAK_LANGUAGE = 45.0

GROUP_ORDER = (
    "Prism Leaders",
    "Re-rating Candidates",
    "Momentum Champions",
    "Divergence & Watch",
    "Structural Laggards",
    "Insufficient Evidence",
)

GROUP_META = {
    "Prism Leaders": {
        "color": "#35C48D",
        "meaning": "Fundamentals, management language and price action all rank in the top peer tier.",
    },
    "Re-rating Candidates": {
        "color": "#4FA3FF",
        "meaning": "Strong fundamentals and language, while market confirmation remains mid-tier.",
    },
    "Momentum Champions": {
        "color": "#9B7BFF",
        "meaning": "Strong market confirmation with at least mid-tier fundamentals and language.",
    },
    "Divergence & Watch": {
        "color": "#FFB347",
        "meaning": "The three signals disagree materially, or the bank remains in the peer middle.",
    },
    "Structural Laggards": {
        "color": "#EF6262",
        "meaning": "Weak fundamentals are confirmed by weak language or weak price action.",
    },
    "Insufficient Evidence": {
        "color": "#9FA8B8",
        "meaning": "At least one coordinate is unavailable; no investment-value group is inferred.",
    },
}


def investment_group(numeric_score, language_score, market_score) -> str:
    """Assign one mutually exclusive group without blending the three axes."""
    values = (numeric_score, language_score, market_score)
    if not all(isinstance(value, (int, float)) for value in values):
        return "Insufficient Evidence"

    numeric = float(numeric_score)
    language = float(language_score)
    market = float(market_score)

    # A three-way intersection of top-tertile scores is usually empty in a
    # 23-name universe.  Leaders therefore require every independent axis to
    # clear a deliberately demanding 55-point floor.
    if min(numeric, language, market) >= LEADER_FLOOR:
        return "Prism Leaders"
    # Fundamentals below the peer centre need confirmation from either weak
    # language or bottom-tertile price action before the laggard label applies.
    if numeric < 50 and (
        (language < WEAK_LANGUAGE and market < HIGH) or market < LOW
    ):
        return "Structural Laggards"
    if numeric >= LEADER_FLOOR and language >= LEADER_FLOOR and LOW <= market < LEADER_FLOOR:
        return "Re-rating Candidates"
    if market >= HIGH and numeric >= 40 and language >= 40:
        return "Momentum Champions"
    return "Divergence & Watch"


def evidence_status(history_periods: int | None) -> str:
    """Gate the language-history confidence independently from group identity."""
    if not isinstance(history_periods, int) or history_periods < 1:
        return "insufficient"
    if history_periods < 4:
        return "provisional"
    return "four-period trend available"
