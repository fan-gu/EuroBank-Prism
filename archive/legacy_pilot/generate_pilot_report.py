"""Generate an evidence-linked Markdown report for the three-bank pilot."""

from pathlib import Path
from datetime import datetime, timezone
import json

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    with (BASE_DIR / "pilot_analysis_dataset.json").open(encoding="utf-8") as handle:
        banks = {row["ticker"]: row for row in json.load(handle)}
    with (BASE_DIR / "pilot_scores.json").open(encoding="utf-8") as handle:
        scores = json.load(handle)

    lines = [
        "# EuroBank Prism — Pilot report",
        "",
        f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        "> Screening output only; not personalized investment advice.",
        "> Reporting format: [analyst report template](analyst_report_template.md).",
        "> Governance rules: [governance policy](governance_policy.md).",
        "",
        "## Ranking",
        "",
        "| Rank | Bank | Score | Metrics used |",
        "|---:|---|---:|---|",
    ]
    for rank, row in enumerate(scores, start=1):
        lines.append(f"| {rank} | {row['bank_name']} ({row['ticker']}) | {row['score']} | {', '.join(row['metrics_used']) or 'none'} |")

    lines += ["", "## Evidence and raw observations", ""]
    for row in scores:
        bank = banks[row["ticker"]]
        lines += [f"### {bank['bank_name']} ({row['ticker']})", "", f"Report period: {bank['period']} ({bank['report_date']})", ""]
        for metric, detail in row["contributions"].items():
            lines.append(f"- **{metric}**: {detail['raw_value']} (normalized {detail['normalized_score']}, weight {detail['weight']:.0%})")
        for evidence in bank.get("evidence", []):
            lines.append(f"- Source: [{evidence['metric']}]({evidence['source_url']}) — {evidence.get('note', '')}")
        lines.append("")

    lines += [
        "## Disclosures",
        "",
        "- The analyst/operator must disclose any financial interest in the banks discussed.",
        "- Market prices are provider observations and may be delayed, adjusted, or revised.",
        "- The scoring methodology is model-owned and is not an independent valuation opinion.",
        "",
        "## Limitations",
        "",
        "- P/B and P/E observations come from a market-data provider and require review against official filings.",
        "- Metrics with different reporting scopes (for example, H1 versus Q2) must not be compared directly.",
        "- A high score means relatively stronger inputs under this methodology; it does not establish fair value or a trading recommendation.",
    ]
    output = BASE_DIR / "pilot_report.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
