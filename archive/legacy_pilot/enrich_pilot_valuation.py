"""Add dated market valuation fields to the real three-bank pilot."""

from pathlib import Path
from datetime import datetime, timezone
import json

from dotenv import load_dotenv
import yfinance as yf

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent
TICKERS = {"ACA": "ACA.PA", "BNP": "BNP.PA", "DBK": "DBK.DE"}


def safe_number(value):
    return value if isinstance(value, (int, float)) else None


def main() -> None:
    input_path = BASE_DIR / "pilot_analysis_dataset.json"
    with input_path.open(encoding="utf-8") as handle:
        banks = json.load(handle)

    retrieved_at = datetime.now(timezone.utc).isoformat()
    for bank in banks:
        symbol = TICKERS[bank["ticker"]]
        info = yf.Ticker(symbol).info
        valuation = bank.setdefault("valuation_metrics", {})

        valuation.update(
            {
                "price_to_book": safe_number(info.get("priceToBook")),
                "price_to_earnings": safe_number(info.get("trailingPE")),
                "market_cap": safe_number(info.get("marketCap")),
                "eps_trailing": safe_number(info.get("trailingEps")),
                "provider": "Yahoo Finance via yfinance",
                "retrieved_at": retrieved_at,
                "status": "provider_observation_requires_review",
            }
        )

    output_path = BASE_DIR / "pilot_analysis_dataset.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(banks, handle, indent=2, ensure_ascii=False)
    print(f"Updated {output_path}")
    print("Review provider observations before using them in a ranking.")


if __name__ == "__main__":
    main()
