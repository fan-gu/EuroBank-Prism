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
- Standard forward-looking, safe-harbour, offer, warranty, and similar legal
  boilerplate is removed before language scoring. Exclusion counts are audited.
- Price confirmation encoded independently by bubble size, so price
  disagreement remains visible without adding a third spatial axis.
- A compact, interactive first-screen signal map: management language is
  horizontal, fundamentals are vertical, and price confirmation sets bubble
  size. Logos sit inside large bubbles and move beside small bubbles so neither
  the logo nor ticker is crushed.
- A waterfall-style homepage that moves from the signal map to
  investment groups, research triage, the full peer ranking, and a compact
  research-readiness gate without requiring tab hopping.
- A persistent left rail containing the product title, refresh/freshness
  control, and section navigation.
- Six transparent investment-value research groups shown by bubble color, with
  a bank-level assignment table and a separate language-history confidence
  gate.
- Evidence controls for reporting period, definition, unit, scope, and source.
- Research triage lists every caution, reversal, drift, and numeric-language
  divergence alert with the supporting passage, page, and official source.
- Dark-mode dashboard with a continuous research narrative; bank research,
  source evidence, and methodology are independent waterfall sections rather
  than nested tabs.

The current release has two spatial axes—fundamentals and management
language—plus price confirmation encoded by bubble size. The three signals
remain visible and are not blended into one opaque score.

## Investment groups

The signal map assigns each bank to one of six directional research groups
without averaging away disagreement: **Conviction Leaders**, **Strong Signals,
Weak Price**, **Cautious Value**, **Price Ahead of Fundamentals**, **Story Ahead
of Numbers**, or **Downside Risk**. Missing coordinates are handled separately as
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
- The current archive contains 66 validated PDFs: 23 curated latest-period
  sources, nine manually verified official history files, and 34 automated
  review-pending history files. Eight banks now have a continuous, same-genre
  four-period trend; the remaining 15 are single-period or partial-history
  snapshots. A missing quarter resets the sequence. Eight comparable periods
  enable drift-alert research. Human review and backtesting remain required.
- The current language build excluded 85 dedicated disclaimer pages and 62
  boilerplate passages before scoring.
- Price confirmation peer-ranks 1-, 3-, and 6-month return with price versus
  its 200-day average. It confirms or challenges market behaviour only; it does
  not measure analyst expectations and does not alter the fundamental score.
- The left-rail refresh control fetches provider fundamentals and price history;
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
python discover_language_reports.py --sources-only
python download_language_reports.py --sources language_history_sources.json --manifest language_history_download_manifest.json
python -m app.language_signals
python build_market_confirmation.py
python app/table_evidence.py
```

The `.env` file is local-only and must contain any required provider keys. Never
commit secrets. Large PDF and evidence archives are retained for auditability;
the dashboard reads the curated JSON indexes and evidence images.
The entry point reloads its small deterministic helper modules on Streamlit
Cloud hot updates, preventing stale imports without a disruptive manual reboot.

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
