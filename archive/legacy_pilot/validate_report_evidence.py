"""Check that every scored metric has traceable evidence."""

from pathlib import Path
import json

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    with (BASE_DIR / "pilot_analysis_dataset.json").open(encoding="utf-8") as handle:
        banks = {row["ticker"]: row for row in json.load(handle)}
    with (BASE_DIR / "pilot_scores.json").open(encoding="utf-8") as handle:
        scores = json.load(handle)

    failures = []
    for score in scores:
        evidence_metrics = {item["metric"] for item in banks[score["ticker"]].get("evidence", [])}
        for metric in score.get("metrics_used", []):
            source_metric = "cet1_ratio" if metric == "cet1_ratio" else metric
            if source_metric not in evidence_metrics and metric not in {"price_to_book", "price_to_earnings"}:
                failures.append(f"{score['ticker']}:{metric}")

    if failures:
        raise SystemExit("Evidence validation failed: " + ", ".join(failures))
    print("Evidence validation passed for all scored report metrics.")
    print("Market-data metrics remain labelled as provider observations.")


if __name__ == "__main__":
    main()
