"""Block publication when market observations are too old."""

from pathlib import Path
from datetime import date, datetime
import json

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent
MAX_PRICE_AGE_DAYS = 3


def main() -> None:
    with (BASE_DIR / "market_prices.json").open(encoding="utf-8") as handle:
        prices = json.load(handle)

    today = date.today()
    stale = []
    for row in prices:
        observed = datetime.strptime(row["price_date"], "%Y-%m-%d").date()
        age = (today - observed).days
        print(f"{row['internal_ticker']}: {row['price_date']} ({age} day(s) old)")
        if age > MAX_PRICE_AGE_DAYS:
            stale.append(row["internal_ticker"])

    if stale:
        raise SystemExit(f"Freshness gate failed; stale tickers: {', '.join(stale)}")
    print("Freshness gate passed.")


if __name__ == "__main__":
    main()
