"""Test whether the pilot ranking is stable under small weight changes."""

from pathlib import Path
import json

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent


def rank(scores, weights):
    output = []
    for row in scores:
        contributions = row.get("contributions", {})
        used = {metric: detail for metric, detail in contributions.items() if metric in weights}
        total_weight = sum(weights[m] for m in used)
        value = sum(detail["normalized_score"] * weights[m] for m, detail in used.items()) / total_weight if total_weight else None
        output.append((row["ticker"], value))
    return sorted(output, key=lambda item: item[1] if item[1] is not None else -1, reverse=True)


def main() -> None:
    with (BASE_DIR / "pilot_scores.json").open(encoding="utf-8") as handle:
        scores = json.load(handle)
    scenarios = {
        "base": {"cet1_ratio": 0.40, "price_to_book": 0.35, "price_to_earnings": 0.25},
        "capital_heavy": {"cet1_ratio": 0.50, "price_to_book": 0.30, "price_to_earnings": 0.20},
        "valuation_heavy": {"cet1_ratio": 0.30, "price_to_book": 0.45, "price_to_earnings": 0.25},
    }
    for name, weights in scenarios.items():
        ordered = rank(scores, weights)
        print(f"{name}: " + " > ".join(ticker for ticker, _ in ordered))
    print("Use stability—not a single score—as the confidence signal.")


if __name__ == "__main__":
    main()
