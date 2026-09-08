"""Run basic quality checks on the real three-bank pilot dataset."""

from pathlib import Path
import json

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent
REQUIRED_TICKERS = {"ACA", "BNP", "DBK"}


def main() -> None:
    with (BASE_DIR / "pilot_analysis_dataset.json").open(encoding="utf-8") as handle:
        banks = json.load(handle)

    checks = []
    tickers = {bank.get("ticker") for bank in banks}
    checks.append(("three pilot banks present", tickers == REQUIRED_TICKERS))
    checks.append(("common balance-sheet date", {bank.get("report_date") for bank in banks} == {"2026-06-30"}))

    for bank in banks:
        checks.append((f"{bank['ticker']} has CET1", isinstance(bank.get("metrics", {}).get("cet1_ratio"), (int, float))))
        checks.append((f"{bank['ticker']} has evidence", bool(bank.get("evidence"))))
        checks.append((f"{bank['ticker']} has market data", bool(bank.get("market_data"))))
        checks.append((f"{bank['ticker']} evidence URLs", all(item.get("source_url", "").startswith("https://") for item in bank.get("evidence", []))))

    passed = sum(ok for _, ok in checks)
    print(f"Passed {passed}/{len(checks)} checks")
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if passed != len(checks):
        raise SystemExit("Data quality gate failed; do not publish a ranking.")


if __name__ == "__main__":
    main()
