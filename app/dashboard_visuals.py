"""Deterministic visual helpers for the Streamlit dashboard."""

from __future__ import annotations

from pathlib import Path
import base64
import math


def image_data_url(path: Path) -> str:
    """Embed a local PNG so Vega does not depend on a runtime image host."""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def padded_domain(values: list[float], reference: float = 50.0) -> list[float]:
    """Return a close chart domain that still shows the quadrant boundary."""
    observed = [float(value) for value in values]
    lower = min([reference, *observed])
    upper = max([reference, *observed])
    span = max(upper - lower, 10.0)
    padding = max(2.5, span * 0.12)
    return [round(max(0.0, lower - padding), 1), round(min(100.0, upper + padding), 1)]


def market_bubble_diameter(score: float) -> float:
    """Map a 0–100 confirmation score to a readable 16–58 px diameter."""
    bounded = min(100.0, max(0.0, float(score)))
    return round(16.0 + bounded * 0.42, 2)


def signal_logo_layout(
    row: dict,
    x_domain: list[float],
    y_domain: list[float],
    width: int = 1_150,
    height: int = 385,
    external_threshold: float = 30.0,
) -> dict:
    """Size a logo in screen pixels and move it beside very small bubbles.

    Plotly layout images are sized in axis units. Converting an intended pixel
    square separately on x and y prevents stretched logos. For a small bubble,
    the logo is placed opposite the collision-aware ticker label so the two do
    not cover one another.
    """
    x_span = x_domain[1] - x_domain[0]
    y_span = y_domain[1] - y_domain[0]
    diameter = market_bubble_diameter(row["Price confirmation"])
    inside = diameter >= external_threshold
    logo_pixels = min(18.0, max(10.0, diameter - 6.0)) if inside else 18.0

    anchor_x = (row["Language score"] - x_domain[0]) / x_span * width
    anchor_y = height - (row["Numeric score"] - y_domain[0]) / y_span * height
    logo_x = anchor_x
    logo_y = anchor_y
    if not inside:
        label_x = (row["Label x"] - x_domain[0]) / x_span * width
        label_y = height - (row["Label y"] - y_domain[0]) / y_span * height
        dx = label_x - anchor_x
        dy = label_y - anchor_y
        length = math.hypot(dx, dy) or 1.0
        distance = diameter / 2 + logo_pixels / 2 + 4
        logo_x = anchor_x - distance * dx / length
        logo_y = anchor_y - distance * dy / length
        half = logo_pixels / 2 + 3
        logo_x = min(max(logo_x, half), width - half)
        logo_y = min(max(logo_y, half), height - half)

    score_x = x_domain[0] + logo_x / width * x_span
    score_y = y_domain[0] + (height - logo_y) / height * y_span
    return {
        "placement": "inside" if inside else "outside",
        "x": round(score_x, 3),
        "y": round(score_y, 3),
        "sizex": round(logo_pixels / width * x_span, 3),
        "sizey": round(logo_pixels / height * y_span, 3),
    }


def _overlap_area(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    width = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    height = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    return width * height


def layout_signal_labels(
    rows: list[dict],
    x_domain: list[float],
    y_domain: list[float],
    width: int = 1_000,
    height: int = 520,
    x_key: str = "Numeric score",
    y_key: str = "Language score",
) -> list[dict]:
    """Place ticker labels around logos with collision-aware leader lines.

    Placement happens in approximate screen pixels, which makes collision
    detection meaningful even though the source scores use different ranges.
    The returned coordinates are converted back to score units for Altair.
    """
    if not rows:
        return []

    x_span = x_domain[1] - x_domain[0]
    y_span = y_domain[1] - y_domain[0]

    def to_pixel(row: dict) -> tuple[float, float]:
        x = (row[x_key] - x_domain[0]) / x_span * width
        y = height - (row[y_key] - y_domain[0]) / y_span * height
        return x, y

    def to_score(x: float, y: float) -> tuple[float, float]:
        score_x = x_domain[0] + x / width * x_span
        score_y = y_domain[0] + (height - y) / height * y_span
        return round(score_x, 3), round(score_y, 3)

    anchors = {row["Ticker"]: to_pixel(row) for row in rows}
    logo_boxes = [
        (x - 18, y - 18, x + 18, y + 18)
        for x, y in anchors.values()
    ]

    def local_density(row: dict) -> int:
        x, y = anchors[row["Ticker"]]
        return sum(
            math.hypot(x - other_x, y - other_y) < 95
            for ticker, (other_x, other_y) in anchors.items()
            if ticker != row["Ticker"]
        )

    placed_boxes: list[tuple[float, ...]] = []
    placements: dict[str, tuple[float, float]] = {}
    angles = [-90, -45, 0, 45, 90, 135, 180, 225]
    for row in sorted(rows, key=local_density, reverse=True):
        anchor_x, anchor_y = anchors[row["Ticker"]]
        label_width = max(34, 8 * len(row["Ticker"]) + 12)
        label_height = 19
        best = None
        for radius in (31, 43, 56, 70, 86):
            for angle in angles:
                radians = math.radians(angle)
                center_x = anchor_x + radius * math.cos(radians)
                center_y = anchor_y + radius * math.sin(radians)
                center_x = min(max(center_x, label_width / 2 + 4), width - label_width / 2 - 4)
                center_y = min(max(center_y, label_height / 2 + 4), height - label_height / 2 - 4)
                box = (
                    center_x - label_width / 2,
                    center_y - label_height / 2,
                    center_x + label_width / 2,
                    center_y + label_height / 2,
                )
                label_overlap = sum(_overlap_area(box, other) for other in placed_boxes)
                logo_overlap = sum(_overlap_area(box, other) for other in logo_boxes)
                distance = math.hypot(center_x - anchor_x, center_y - anchor_y)
                score = label_overlap * 100 + logo_overlap * 40 + distance
                if best is None or score < best[0]:
                    best = (score, center_x, center_y, box)
                if label_overlap == 0 and logo_overlap == 0:
                    break
            if best and best[0] < 87:
                break
        _, center_x, center_y, box = best
        placed_boxes.append(box)
        placements[row["Ticker"]] = (center_x, center_y)

    output = []
    for row in rows:
        label_x, label_y = to_score(*placements[row["Ticker"]])
        output.append({**row, "Label x": label_x, "Label y": label_y})
    return output
