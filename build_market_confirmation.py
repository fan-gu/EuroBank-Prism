"""Build an independent market-confirmation axis for EuroBank Prism.

The axis is deliberately not fed into the fundamental relative-value score.
It measures whether market behaviour confirms or challenges a bank's current
peer position using price momentum and the long-term price trend.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path

import yfinance as yf

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "market_confirmation.json"
LOOKBACKS = {"one_month": 21, "three_month": 63, "six_month": 126}
LONG_TREND_DAYS = 200
MIN_HISTORY_DAYS = LONG_TREND_DAYS + 5

MARKET_TICKERS = {
    "BNP": "BNP.PA", "SAN": "SAN.MC", "INGA": "INGA.AS", "BBVA": "BBVA.MC",
    "ISP": "ISP.MI", "UCG": "UCG.MI", "NDA-FI": "NDA-FI.HE", "DBK": "DBK.DE",
    "GLE": "GLE.PA", "KBC": "KBC.BR", "CABK": "CABK.MC", "ACA": "ACA.PA",
    "CBK": "CBK.DE", "EBS": "EBS.VI", "BIRG": "BIRG.IR", "FBK": "FBK.MI",
    "ABN": "ABN.AS", "BAMI": "BAMI.MI", "SAB": "SAB.MC", "AIBG": "A5G.IR",
    "BKT": "BKT.MC", "BG": "BG.VI", "BPE": "BPE.MI",
}


def finite(value: object) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def return_since(closes: list[float], sessions: int) -> float | None:
    """Return from the close N sessions ago to the latest close."""
    if len(closes) <= sessions:
        return None
    start, end = closes[-(sessions + 1)], closes[-1]
    if start <= 0:
        return None
    return end / start - 1


def percentile(values: list[float], value: float) -> float:
    if len(values) <= 1:
        return 0.5
    below = sum(candidate < value for candidate in values)
    equal = sum(candidate == value for candidate in values)
    return (below + 0.5 * equal) / len(values)


def trend_score(last_price: float, average_200d: float) -> float | None:
    if average_200d <= 0:
        return None
    return last_price / average_200d - 1


def score_records(records: list[dict]) -> list[dict]:
    """Peer-rank market observations without using fundamentals or language."""
    metric_names = ("one_month_return", "three_month_return", "six_month_return", "trend_vs_200d")
    available = {
        name: [row[name] for row in records if row.get(name) is not None]
        for name in metric_names
    }
    weights = {
        "one_month_return": 0.20,
        "three_month_return": 0.35,
        "six_month_return": 0.35,
        "trend_vs_200d": 0.10,
    }
    for row in records:
        components = {}
        for name, weight in weights.items():
            value = row.get(name)
            if value is not None:
                components[name] = {"raw_value": round(value, 6), "percentile_score": round(percentile(available[name], value), 4), "weight": weight}
        weight_used = sum(component["weight"] for component in components.values())
        row["components"] = components
        row["weight_coverage"] = round(weight_used, 2)
        row["market_confirmation_score"] = (
            round(100 * sum(component["percentile_score"] * component["weight"] for component in components.values()) / weight_used, 1)
            if weight_used >= 0.70
            else None
        )
        row["status"] = "market_confirmation_available" if row["market_confirmation_score"] is not None else "insufficient_price_history"
        score = row["market_confirmation_score"]
        row["market_regime"] = (
            "Confirming" if score is not None and score >= 60 else
            "Unconfirmed" if score is not None and score <= 40 else
            "Neutral" if score is not None else "Insufficient history"
        )
    return records


def build_market_confirmation() -> dict:
    banks = json.loads((BASE_DIR / "bank_master.json").read_text(encoding="utf-8"))["constituents"]
    records = []
    retrieved_at = datetime.now(timezone.utc).isoformat()
    for bank in banks:
        ticker = bank["ticker"]
        market_ticker = MARKET_TICKERS[ticker]
        record = {
            "ticker": ticker,
            "bank_name": bank["bank_name"],
            "market_ticker": market_ticker,
            "retrieved_at": retrieved_at,
            "provider": "Yahoo Finance via yfinance",
        }
        try:
            history = yf.Ticker(market_ticker).history(period="18mo", auto_adjust=True)
            closes = [finite(value) for value in history.get("Close", []).tolist()]
            closes = [value for value in closes if value is not None]
            if len(closes) < MIN_HISTORY_DAYS:
                raise ValueError(f"only {len(closes)} valid closing prices")
            record.update(
                last_price=round(closes[-1], 4),
                history_end=str(history.index[-1].date()),
                history_sessions=len(closes),
                one_month_return=return_since(closes, LOOKBACKS["one_month"]),
                three_month_return=return_since(closes, LOOKBACKS["three_month"]),
                six_month_return=return_since(closes, LOOKBACKS["six_month"]),
                trend_vs_200d=trend_score(closes[-1], sum(closes[-LONG_TREND_DAYS:]) / LONG_TREND_DAYS),
            )
        except Exception as exc:
            record.update(error=f"{type(exc).__name__}: {exc}")
            for metric in ("last_price", "history_end", "history_sessions", "one_month_return", "three_month_return", "six_month_return", "trend_vs_200d"):
                record[metric] = None
        records.append(record)
        print(f"{ticker}: price history {'loaded' if not record.get('error') else 'failed'}", flush=True)

    scored = score_records(records)
    payload = {
        "schema_version": "1.0",
        "generated_at": retrieved_at,
        "methodology": {
            "axis": "independent_market_confirmation",
            "components": "1m 20%, 3m 35%, 6m 35%, price versus 200-day average 10%",
            "interpretation": "Cross-sectional peer percentile; not included in the fundamental relative-value score.",
            "provider": "Yahoo Finance via yfinance",
        },
        "records": scored,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    available = sum(row["status"] == "market_confirmation_available" for row in scored)
    print(f"Wrote {OUTPUT_PATH}: {available}/{len(scored)} scores available.")
    return payload


if __name__ == "__main__":
    build_market_confirmation()
