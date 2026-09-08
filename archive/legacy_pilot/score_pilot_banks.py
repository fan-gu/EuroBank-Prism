"""Score the pilot banks with transparent, missing-data-aware normalization."""

from pathlib import Path
import json

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent
WEIGHTS = {"cet1_ratio": 0.40, "price_to_book": 0.35, "price_to_earnings": 0.25}
LOWER_IS_BETTER = {"price_to_book", "price_to_earnings"}


def normalize(values, value, lower_is_better=False):
    low, high = min(values), max(values)
    if high == low:
        return 1.0
    score = (value - low) / (high - low)
    return 1.0 - score if lower_is_better else score


def main() -> None:
    with (BASE_DIR / "pilot_analysis_dataset.json").open(encoding="utf-8") as handle:
        banks = json.load(handle)

    available = {}
    for metric in WEIGHTS:
        rows = []
        for bank in banks:
            source = bank["metrics"] if metric == "cet1_ratio" else bank.get("valuation_metrics", {})
            value = source.get(metric)
            if isinstance(value, (int, float)) and value > 0:
                rows.append((bank["ticker"], value))
        available[metric] = rows

    scores = []
    for bank in banks:
        contributions = {}
        for metric, weight in WEIGHTS.items():
            rows = available[metric]
            lookup = dict(rows)
            if bank["ticker"] not in lookup:
                continue
            values = list(lookup.values())
            normalized = normalize(values, lookup[bank["ticker"]], metric in LOWER_IS_BETTER)
            contributions[metric] = {
                "raw_value": lookup[bank["ticker"]],
                "normalized_score": round(normalized, 4),
                "weight": weight,
            }

        weight_total = sum(item["weight"] for item in contributions.values())
        score = (
            sum(item["normalized_score"] * item["weight"] for item in contributions.values())
            / weight_total
            if weight_total
            else None
        )
        scores.append(
            {
                "ticker": bank["ticker"],
                "bank_name": bank["bank_name"],
                "score": round(score, 4) if score is not None else None,
                "metrics_used": list(contributions),
                "contributions": contributions,
                "status": "screening_score_only",
            }
        )

    scores.sort(key=lambda row: row["score"] if row["score"] is not None else -1, reverse=True)
    with (BASE_DIR / "pilot_scores.json").open("w", encoding="utf-8") as handle:
        json.dump(scores, handle, indent=2, ensure_ascii=False)
    print("Wrote pilot_scores.json")
    for rank, row in enumerate(scores, start=1):
        print(f"{rank}. {row['ticker']}: {row['score']} ({', '.join(row['metrics_used'])})")
    print("This is a relative screening score, not investment advice.")


if __name__ == "__main__":
    main()
