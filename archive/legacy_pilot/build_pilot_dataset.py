"""Build the three-bank real-data pilot without mixing incomparable periods."""

from pathlib import Path
import json

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent


def load_json(name: str):
    with (BASE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    pilot = load_json("pilot_real_data.json")
    prices = {row["internal_ticker"]: row for row in load_json("market_prices.json")}

    for bank in pilot:
        market = prices.get(bank["ticker"])
        bank["market_data"] = market
        bank["valuation_metrics"] = {
            "price_to_book": None,
            "price_to_earnings": None,
            "status": "pending verified book-value and earnings input",
        }

        # A metric can enter a peer score only when its period scope matches.
        bank["comparability"] = {
            "common_balance_date": bank["report_date"] == "2026-06-30",
            "cet1_ratio": "comparable",
            "rote": "not comparable until all three use the same scope",
            "cost_income_ratio": "not comparable until all three use the same scope",
            "price_to_book": "pending",
            "price_to_earnings": "pending",
        }

    output = BASE_DIR / "pilot_analysis_dataset.json"
    with output.open("w", encoding="utf-8") as handle:
        json.dump(pilot, handle, indent=2, ensure_ascii=False)

    print(f"Wrote {output}")
    print("Safe scoring set: CET1 ratio only until period alignment is complete.")


if __name__ == "__main__":
    main()
