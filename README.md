# EuroBank Prism

**Three signals. One clearer view.**

EuroBank Prism is a research screening dashboard for the 23 constituents of
the EURO STOXX Banks index. It compares public bank disclosures and market
data consistently; it is not personalized investment advice.

## What it shows

- Relative peer ranking using P/B, P/E, ROE, ROA, dividend yield, and growth.
- Price, country, ticker, index weight, and official-report links.
- A separate management-language signal with cited passages, pages, and an
  auditable four-period drift pipeline.
- Price confirmation encoded independently by bubble size, so price
  disagreement remains visible without adding a third spatial axis.
- A compact, interactive first-screen signal map: management language is
  horizontal, fundamentals are vertical, and price confirmation sets bubble
  size. Its investment-group legend is horizontal.
- A waterfall-style homepage that moves from the signal map to
  investment groups, research triage, the full peer ranking, a one-bank
  diagnostic, and the evidence-readiness gate without requiring tab hopping.
- A persistent left navigation rail and a top-right refresh/freshness control.
- Seven transparent investment-value research groups shown by bubble color, with
  a bank-level assignment table and a separate language-history confidence
  gate.
- Evidence controls for reporting period, definition, unit, scope, and source.
- Dark-mode dashboard with a continuous research narrative and a detailed
  signals, ranking, bank, evidence, and methodology workbench at the bottom.

The current release has two spatial axes—fundamentals and management
language—plus price confirmation encoded by bubble size. The three signals
remain visible and are not blended into one opaque score.

## Investment groups

The signal map assigns each bank to one of seven directional research groups
without averaging away disagreement: **Conviction Leaders**, **Re-rating
Candidates**, **Contrarian Value**, **Price-led Momentum**, **Verification
Watch**, **Downside Risk**, or **No Clear Edge**. Missing coordinates are handled separately as
**Insufficient Evidence**, not forced into an investment group. The rules use
axis-specific peer quantiles rather than one shared raw cutoff. All group labels
remain provisional until comparable language history and backtesting are available.

## Workflow

```text
Official reports ──> PDF/page screening ──> cited evidence
                                  └──────> management language + drift history
Market data ──────> comparable metrics ──> weighted peer ranking
              └──> price history ───────> price-confirmation overlay
                    quality and freshness gates ──> dashboard/report
```

## Data and controls

- 23-bank EURO STOXX Banks universe with country, ticker, and index weight.
- Official annual and quarterly/interim report links for every constituent.
- Missing or non-comparable observations are excluded, never invented.
- Language observations retain source URL, document hash, period, and page.
- Table and language evidence remains review-pending until validated.
- The current archive contains 56 validated PDFs: 23 curated latest-period
  sources plus 33 review-pending historical sources. Ten banks now have a
  preliminary four-period trend; the remaining 13 are still single-period or
  partial-history snapshots. Eight comparable periods enable drift-alert
  research. Human review and backtesting remain required for publication.
- Price confirmation peer-ranks 1-, 3-, and 6-month return with price versus
  its 200-day average. It confirms or challenges market behaviour only; it does
  not measure analyst expectations and does not alter the fundamental score.
- The top-right refresh control fetches provider fundamentals and price history;
  report-language curation is a separate governed workflow.

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
python discover_language_reports.py
python download_language_reports.py --sources language_history_sources.json --manifest language_history_download_manifest.json
python -m app.language_signals
python build_market_confirmation.py
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
