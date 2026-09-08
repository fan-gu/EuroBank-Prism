"""Run the EuroSTOXX pilot as one reproducible Month 6 workflow."""

from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent
STEPS = [
    "build_pilot_dataset.py",
    "enrich_pilot_valuation.py",
    "review_pilot_valuation.py",
    "score_pilot_banks.py",
    "generate_pilot_report.py",
]


def main() -> None:
    for step in STEPS:
        print(f"\n--- Running {step} ---")
        subprocess.run([sys.executable, str(BASE_DIR / step)], cwd=BASE_DIR, check=True)
    print("\nPilot pipeline completed successfully.")


if __name__ == "__main__":
    main()
