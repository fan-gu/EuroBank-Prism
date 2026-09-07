"""Transparent three-axis investment-value group rules.

The groups preserve disagreement between fundamentals, management language,
and market confirmation.  They are research-screen labels, not advice.
"""

LEADER_FLOOR = 55.0
LANGUAGE_SUPPORT = 50.0
MOMENTUM_FLOOR = 60.0
PEER_MIDPOINT = 50.0

GROUP_ORDER = (
    "Conviction Leaders",
    "Re-rating Candidates",
    "Contrarian Value",
    "Expectations-led Momentum",
    "Downside Risk",
    "No Clear Edge",
)

GROUP_META = {
    "Conviction Leaders": {
        "color": "#35C48D",
        "meaning": "All three signals agree: strong fundamentals, supportive language and confirming price action.",
    },
    "Re-rating Candidates": {
        "color": "#4FA3FF",
        "meaning": "Fundamentals and language are supportive, but price action has not yet confirmed the thesis.",
    },
    "Contrarian Value": {
        "color": "#32C6D4",
        "meaning": "Fundamentals screen strongly while management language is cautious; verify whether the discount is justified.",
    },
    "Expectations-led Momentum": {
        "color": "#9B7BFF",
        "meaning": "Price momentum is ahead of the fundamental score; upside may depend on future delivery.",
    },
    "Downside Risk": {
        "color": "#EF6262",
        "meaning": "Below-midpoint fundamentals have at least one confirming warning from language or price action.",
    },
    "No Clear Edge": {
        "color": "#FFB347",
        "meaning": "Signals are clustered near the peer middle; the screen does not reveal a differentiated thesis.",
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

    # Six directional research outcomes. Missing evidence remains a separate
    # publication gate and is not counted as an investment group.
    if min(numeric, language, market) >= LEADER_FLOOR:
        return "Conviction Leaders"
    if numeric >= LEADER_FLOOR and language >= LANGUAGE_SUPPORT and market < LEADER_FLOOR:
        return "Re-rating Candidates"
    if market >= MOMENTUM_FLOOR and numeric < LEADER_FLOOR:
        return "Expectations-led Momentum"
    if numeric >= PEER_MIDPOINT and language < LANGUAGE_SUPPORT:
        return "Contrarian Value"
    if numeric < PEER_MIDPOINT and (
        language < LANGUAGE_SUPPORT or market < LANGUAGE_SUPPORT
    ):
        return "Downside Risk"
    return "No Clear Edge"


def evidence_status(history_periods: int | None) -> str:
    """Gate the language-history confidence independently from group identity."""
    if not isinstance(history_periods, int) or history_periods < 1:
        return "insufficient"
    if history_periods < 4:
        return "provisional"
    return "four-period trend available"
