"""Run all pre-publication controls for the pilot ranking."""

from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent
CHECKS = [
    "evaluate_pilot_data.py",
    "check_data_freshness.py",
    "validate_report_evidence.py",
]


def main() -> None:
    for check in CHECKS:
        print(f"\n--- {check} ---")
        subprocess.run([sys.executable, str(BASE_DIR / check)], cwd=BASE_DIR, check=True)
    print("\nPUBLICATION GATE PASSED")
    print("The ranking may be displayed with its evidence and limitations.")


if __name__ == "__main__":
    main()
