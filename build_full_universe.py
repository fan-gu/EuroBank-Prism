"""Build and score the full 23-bank universe using common provider metrics."""

from pathlib import Path
from datetime import datetime, timezone
import json
import math
import time

from dotenv import load_dotenv
import yfinance as yf

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent
MARKET_TICKERS = {
    "BNP": "BNP.PA", "SAN": "SAN.MC", "INGA": "INGA.AS", "BBVA": "BBVA.MC",
    "ISP": "ISP.MI", "UCG": "UCG.MI", "NDA-FI": "NDA-FI.HE", "DBK": "DBK.DE",
    "GLE": "GLE.PA", "KBC": "KBC.BR", "CABK": "CABK.MC", "ACA": "ACA.PA",
    "CBK": "CBK.DE", "EBS": "EBS.VI", "BIRG": "BIRG.IR", "FBK": "FBK.MI",
    "ABN": "ABN.AS", "BAMI": "BAMI.MI", "SAB": "SAB.MC", "AIBG": "A5G.IR",
    "BKT": "BKT.MC", "BG": "BG.VI", "BPE": "BPE.MI",
}
WEIGHTS = {
    "price_to_book": 0.25,
    "price_to_earnings": 0.15,
    "return_on_equity": 0.20,
    "return_on_assets": 0.10,
    "dividend_yield": 0.10,
    "earnings_growth": 0.10,
    "revenue_growth": 0.10,
}
LOWER_IS_BETTER = {"price_to_book", "price_to_earnings"}


def number(value):
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def percentage_points_to_ratio(value):
    """Convert provider percentage points, e.g. 5.63, to 0.0563."""
    value = number(value)
    if value is None:
        return None
    return value / 100


def percentile(values, value, reverse=False):
    if len(values) <= 1:
        return 0.5
    below = sum(candidate < value for candidate in values)
    equal = sum(candidate == value for candidate in values)
    result = (below + 0.5 * equal) / len(values)
    return 1.0 - result if reverse else result


def main():
    master = json.loads((BASE_DIR / "bank_master.json").read_text(encoding="utf-8"))
    universe = master["constituents"]
    seed_path = BASE_DIR / "prudential_evidence_seed.json"
    prudential_seed = (
        {
            row["ticker"]: row
            for row in json.loads(seed_path.read_text(encoding="utf-8"))
        }
        if seed_path.exists()
        else {}
    )
    retrieved_at = datetime.now(timezone.utc).isoformat()
    records = []

    for bank in universe:
        ticker = bank["ticker"]
        symbol = MARKET_TICKERS[ticker]
        record = {**bank, "market_ticker": symbol, "retrieved_at": retrieved_at, "provider": "Yahoo Finance via yfinance"}
        try:
            info = yf.Ticker(symbol).info
            record["metrics"] = {
                "price": number(info.get("currentPrice") or info.get("regularMarketPrice")),
                "market_cap": number(info.get("marketCap")),
                "price_to_book": number(info.get("priceToBook")),
                "price_to_earnings": number(info.get("trailingPE")),
                "forward_price_to_earnings": number(info.get("forwardPE")),
                "book_value_per_share": number(info.get("bookValue")),
                "earnings_per_share": number(info.get("trailingEps")),
                "return_on_equity": number(info.get("returnOnEquity")),
                "return_on_assets": number(info.get("returnOnAssets")),
                "profit_margin": number(info.get("profitMargins")),
                "dividend_yield": percentage_points_to_ratio(info.get("dividendYield")),
                "payout_ratio": number(info.get("payoutRatio")),
                "earnings_growth": number(info.get("earningsGrowth")),
                "revenue_growth": number(info.get("revenueGrowth")),
                "beta": number(info.get("beta")),
            }
            record["status"] = "market_data_loaded"
        except Exception as exc:
            record["metrics"] = {}
            record["status"] = "market_data_failed"
            record["error"] = str(exc)
        if ticker in prudential_seed:
            record["prudential_metrics"] = prudential_seed[ticker].get("metrics", {})
            record["official_evidence"] = prudential_seed[ticker].get("evidence", [])
        else:
            record["prudential_metrics"] = {}
            record["official_evidence"] = []
        records.append(record)
        print(f"{ticker}: {record['status']}")
        time.sleep(0.15)

    metric_values = {
        metric: [
            row["metrics"][metric]
            for row in records
            if row.get("metrics", {}).get(metric) is not None
            and (metric not in LOWER_IS_BETTER or row["metrics"][metric] > 0)
        ]
        for metric in WEIGHTS
    }
    scores = []
    for row in records:
        components = {}
        for metric, weight in WEIGHTS.items():
            value = row.get("metrics", {}).get(metric)
            if value is None or (metric in LOWER_IS_BETTER and value <= 0):
                continue
            components[metric] = {
                "raw_value": value,
                "percentile_score": round(percentile(metric_values[metric], value, metric in LOWER_IS_BETTER), 4),
                "weight": weight,
            }
        weight_used = sum(item["weight"] for item in components.values())
        score = sum(item["percentile_score"] * item["weight"] for item in components.values()) / weight_used if weight_used else None
        scores.append({
            "ticker": row["ticker"], "bank_name": row["bank_name"],
            "score": round(score * 100, 1) if score is not None else None,
            "metric_count": len(components), "weight_coverage": round(weight_used, 2),
            "components": components,
            "status": "ranked" if weight_used >= 0.60 else "insufficient_data",
        })

    scores.sort(key=lambda row: row["score"] if row["status"] == "ranked" and row["score"] is not None else -1, reverse=True)
    (BASE_DIR / "full_universe_dataset.json").write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    (BASE_DIR / "full_universe_scores.json").write_text(json.dumps(scores, indent=2, ensure_ascii=False), encoding="utf-8")
    ranked = sum(row["status"] == "ranked" for row in scores)
    print(f"Ranked {ranked}/{len(scores)} banks. Provider observations require review.")


if __name__ == "__main__":
    main()
