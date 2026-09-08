"""Review market valuation observations before they enter the bank score."""

from pathlib import Path
import json

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    path = BASE_DIR / "pilot_analysis_dataset.json"
    with path.open(encoding="utf-8") as handle:
        banks = json.load(handle)

    print("Three-bank valuation review")
    print("=" *  thirty())
    for bank in banks:
        valuation = bank.get("valuation_metrics", {})
        pb = valuation.get("price_to_book")
        pe = valuation.get("price_to_earnings")
        flags = []
        if pb is None:
            flags.append("missing P/B")
        elif pb <= 0 or pb > 20:
            flags.append("review P/B")
        if pe is None:
            flags.append("missing P/E")
        elif pe <= 0 or pe > 100:
            flags.append("review P/E")

        print(f"\n{bank['bank_name']} ({bank['ticker']})")
        print(f"  Report date: {bank['report_date']}")
        print(f"  Market price: {bank.get('market_data', {}).get('price')}")
        print(f"  P/B: {pb}")
        print(f"  P/E: {pe}")
        print(f"  Retrieved: {valuation.get('retrieved_at', 'unknown')}")
        print(f"  Status: {'; '.join(flags) if flags else 'ready for source review'}")


def thirty() -> int:
    return 30


if __name__ == "__main__":
    main()
