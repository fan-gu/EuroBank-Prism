# EuroBank Prism

**Three independent signals. One clearer view.**

EuroBank Prism is a research screening dashboard for the 23 constituents of
the EURO STOXX Banks index. It compares public bank disclosures and market
data consistently; it is not personalized investment advice.

## What it shows

- Relative peer ranking using P/B, P/E, ROE, ROA, dividend yield, and growth.
- Price, country, ticker, index weight, and official-report links.
- A separate management-language signal with cited passages and page numbers.
- Evidence controls for reporting period, definition, unit, scope, and source.
- Dark-mode dashboard with ranking, signals, bank details, evidence, and
  methodology views.

The current release has two live axes: fundamentals and management language.
Market confirmation is the next independent signal; the axes are intentionally
not blended into one opaque score.

## Workflow

```text
Official reports ──> PDF/page screening ──> cited evidence
                                  └──────> management-language signal
Market data ──────> comparable metrics ──> weighted peer ranking
                    quality and freshness gates ──> dashboard/report
```

## Data and controls

- 23-bank EURO STOXX Banks universe with country, ticker, and index weight.
- Official annual and quarterly/interim report links for every constituent.
- Missing or non-comparable observations are excluded, never invented.
- Language observations retain source URL, document hash, period, and page.
- Table and language evidence remains review-pending until validated.
- Four comparable periods enable a preliminary language trend; eight enable
  drift-alert research. Human review and backtesting are required for validated
  publication.

## Run locally

From the repository root, with the project virtual environment activated:

```powershell
python run_pilot_pipeline.py
python -m streamlit run streamlit_app.py
```

Useful maintenance commands:

```powershell
python coverage_report.py
python download_language_reports.py
python -m app.language_signals
python app/table_evidence.py
```

The `.env` file is local-only and must contain any required provider keys. Never
commit secrets. Large PDF and evidence archives are retained for auditability;
the dashboard reads the curated JSON indexes and evidence images.

## Repository map

```text
streamlit_app.py           Dashboard entry point
app/                       Ingestion, language signals, table evidence, visuals
assets/bank_logos/         Issuer logo assets
tests/                     Automated validation
full_universe_*.json       Current 23-bank data and scores
official_report_pages.json Official report directory
archive/                   Historical planning material
```

## Disclaimer

EuroBank Prism is an educational/research screening tool. Scores and labels
are relative inputs, not recommendations to buy, sell, short, or hold any
security. Verify all figures against the linked official disclosures.
