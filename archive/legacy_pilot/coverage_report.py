"""Report coverage across the complete EURO STOXX Banks universe."""

from pathlib import Path
import json

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    universe = json.loads((BASE_DIR / "bank_master.json").read_text(encoding="utf-8"))["constituents"]
    registry = {row["ticker"]: row for row in json.loads((BASE_DIR / "report_registry.json").read_text(encoding="utf-8"))["banks"]}
    pilot = {row["ticker"]: row for row in json.loads((BASE_DIR / "pilot_real_data.json").read_text(encoding="utf-8"))}

    verified_urls = sum(bool(registry.get(row.get("ticker"), {}).get("download_url")) for row in universe)
    downloaded = sum(bool(list((BASE_DIR / "reports" / row["ticker"]).glob("*.pdf"))) if (BASE_DIR / "reports" / row["ticker"]).exists() else False for row in universe)
    metric_records = sum(row.get("status") == "verified_source_extracted" for row in pilot.values())

    print(f"Universe: {len(universe)} banks")
    print(f"Verified report URLs: {verified_urls}/{len(universe)}")
    print(f"Downloaded PDFs: {downloaded}/{len(universe)}")
    print(f"Pilot metric records: {metric_records}/{len(universe)}")
    print("A bank enters scoring only after its report and metrics pass validation.")


if __name__ == "__main__":
    main()
