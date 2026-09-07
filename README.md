# EuroBank Prism

**Three independent signals. One clearer view.**

AI-powered European bank research intelligence designed around financial
fundamentals, management language, and market confirmation. The current
release has the fundamentals and management-language axes live; market
confirmation is the next independent signal. Coverage is the 23-member
EURO STOXX Banks index.

## Problem

Compare public financial information for EURO STOXX Banks constituents and
identify potentially attractive or expensive banks relative to peers.

The deployed dashboard ranks all 23 constituents using a common provider-data
screen based on P/B, P/E, ROE, ROA, dividend yield, earnings growth, and revenue
growth. It also displays price, forward P/E, book value per share, EPS, profit
margin, payout ratio, market capitalisation, and beta. Official prudential
metrics are added as a separate evidence-backed overlay as report coverage
expands, and every bank has an official investor-relations link.

The PDF pipeline now performs precision-first table extraction. It screens
pages for bank-metric terminology, rejects chart and slide regions that do not
have a credible row/column structure, converts retained tables to structured
records, and saves an image crop of the exact source table. Every candidate is
marked `pending_human_review`; it cannot enter the ranking until its metric
definition, reporting period, unit and consolidation scope are confirmed.

The dark-mode dashboard presents all 23 ranking rows at once. It includes flag
images, country codes, tickers, index weights, euro-denominated prices, P/E,
P/B, ROE, dividend yield, scores, and concise comments. The Evidence tab is a
complete 23-bank directory of official annual and quarterly-report links.
Country flags use a compact fixed 20×15 size. The Signals matrix uses locally
cached issuer-domain logo icons, close-fit score axes, and collision-aware
ticker labels with leader lines so dense observations remain identifiable.

## Independent management-language axis

The Signals tab keeps the numeric and language axes separate. The versioned,
deterministic language engine measures financial tone, uncertainty, commitment
strength, cautious wording and confidence expressions. Each observation keeps
the original sentence, PDF page, document hash, reporting period and official
source URL. Numeric-language gaps can create research-review alerts, but the
labels are not investment recommendations.

Language rule v2 corrects the positive base rate of management-authored
documents in two steps. First, it calculates explicit negative pressure from
negative terms (2.00×), weak modal density (1.75×), uncertainty (1.35×), and
cautious or euphemistic wording (1.15×), all per 1,000 analyzed words. Second,
it robustly centers net language strength across the 23-bank cohort using the
median and MAD. Therefore, 50 is the peer center rather than generic sentiment
neutrality. A confidence decline combined with rising caution is encoded as a
directional reversal, but the drift penalty remains inactive until comparable
history exists.

Language governance follows a staged history rule:

- 1 period: current-language preview only
- 4 comparable quarterly periods: preliminary trend
- 8 comparable quarterly periods: drift and event-alert research
- Human review plus out-of-sample backtest: eligible for validated publication

The current archive has provisional single-period language coverage for all 23
EURO STOXX Banks constituents: one latest official English Q2 or H1 2026
management-facing results document per bank. Every bank has at least three
page-cited evidence passages. Coverage does not make the observations
publication-eligible: cross-bank document genres and periods are still mixed,
and no missing language value is imputed.

Provider dividend yields arrive in percentage points and are divided by 100
before scoring, then converted back only for display (for example, provider
`5.63` → stored `0.0563` → displayed `5.63%`).

## Inputs

- Official quarterly and annual bank reports
- Page-level extracted evidence
- Market prices with retrieval timestamps
- Comparable banking and valuation metrics

## Workflow

```text
Official reports -> fast page screen -> table extraction -> evidence PNG
                                      -> review-pending evidence archive
                 -> management-section gate -> language evidence + page
                                            -> independent language axis
Market prices ---------------------> comparable dataset
                       -> quality/freshness gates
                       -> weighted peer score
                       -> cited Markdown report and dashboard
```

## Controls

- Period and definition comparability checks
- Missing-data exclusion
- Source and evidence validation
- Stale-price gate
- Weight sensitivity analysis
- Governance disclosures
- Separate numeric and language axes
- Four-period preliminary-trend gate
- Eight-period drift-alert gate
- Human review and out-of-sample backtest gate

## Run

```powershell
& "C:\FG\.venv\Scripts\python.exe" run_pilot_pipeline.py
& "C:\FG\.venv\Scripts\python.exe" -m streamlit run streamlit_app.py
```

To monitor rollout coverage across all 23 constituents:

```powershell
& "C:\FG\.venv\Scripts\python.exe" coverage_report.py
```

The curated language sources are recorded in `language_report_sources.json`.
To download and PDF-validate all 23 current-period documents, then rebuild the
signal archive:

```powershell
& "C:\FG\.venv\Scripts\python.exe" download_language_reports.py
& "C:\FG\.venv\Scripts\python.exe" -m app.language_signals
```

`language_download_manifest.json` records status, final URL, byte size, SHA-256
hash and retrieval time for each file. The Commerzbank endpoint needs a scoped
local certificate-verification exception on this machine; its downloaded
content is still size-limited, PDF-signature checked and hash-recorded. Run
`discover_language_reports.py` to create a review-only candidate registry;
curated sources remain authoritative.

To rebuild structured table evidence from all locally downloaded reports:

```powershell
& "C:\FG\.venv\Scripts\python.exe" app\table_evidence.py
```

Use `--ticker BNP` to process one bank or `--no-images` for a faster diagnostic
run. Evidence screenshots are displayed in the dashboard separately from the
23-bank official report-link directory.

To rebuild the independent management-language archive:

```powershell
& "C:\FG\.venv\Scripts\python.exe" -m app.language_signals
```

This is a research screening tool, not personalized investment advice.
