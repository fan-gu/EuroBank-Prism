# EuroBank Prism

**Evidence-traceable research across fundamentals, management language and price momentum for the 23-bank EURO STOXX Banks universe.**

[Open the live dashboard](https://eurobank-prism.streamlit.app/) · [View the source](https://github.com/fan-gu/EuroBank-Prism)

![EuroBank Prism dashboard](assets/readme/eurobank-prism-dashboard.png)

## What it does

EuroBank Prism compares 23 listed European banks using three independent signals.

| Signal | Display | What it measures |
|---|---|---|
| Fundamentals & Valuation | Vertical Axis | Relative P/B, P/E, profitability, yield, and growth |
| Management language | Horizontal Axis | Disclosure tone, commitment, uncertainty, caution, and linguistic drift |
| Price confirmation | Bubble Size | Relative 1-, 3-, and 6-month price momentum plus the 200-day trend |

Bubble colour identifies the bank's deterministic research group. A separate
Gemini semantic-research layer answers natural-language questions from the
indexed official reports and cites the source bank, period and PDF page.

## Research workflow

```text
Official reports ──> pollution filters ──────> language evidence and drift
                 └─> page-aware chunks ─────> Gemini embeddings ──> cited Q&A
Market data ───────> comparable metrics ─────> peer-relative fundamentals
Price history ─────> momentum checks ────────> price-confirmation bubble
                               governance gates ──> Streamlit dashboard
```

## Evidence and governance

- The universe is fixed to 23 EURO STOXX Banks constituents.
- Standard legal disclaimers and safe-harbour boilerplate are excluded from
  management-language scoring.
- Deterministic v2.4.3 filters mask neutral banking risk labels, deduplicate safe
  document repeats, remove technical restatement notes and routine procedural
  footnotes and standardized rounding notes, and drop—not invert—negated
  negative hits. Every action is auditable.
- Language observations retain the source document, reporting period, page,
  quotation, and document hash.
- Four adjacent comparable periods enable a preliminary drift observation;
  eight periods, human review, and out-of-sample testing are required before a
  drift signal is treated as validated research.
- Missing or non-comparable observations remain missing—they are never inferred.
- Semantic answers cannot change a score or investment group and must cite the
  retrieved official-report evidence; insufficient evidence produces no claim.

[Language-filter validation](docs/validation/language-v2.4.3-expanded-rounding-filter.md) · [Semantic-search design](docs/semantic-research.md)

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Core refresh commands:

```powershell
python build_full_universe.py
python build_market_confirmation.py
python discover_language_reports.py
python download_language_reports.py
python -m app.language_signals
python build_semantic_index.py
```

Set `GEMINI_API_KEY` in a local `.env` file or Streamlit Community Cloud Secrets.
The committed index contains embeddings—not the API key. Never commit secrets.

## Repository structure

```text
streamlit_app.py             Streamlit entry point
app/                         Scoring, ingestion, evidence, and visual modules
semantic_*.json / .npz       Filtered corpus metadata and local cosine index
assets/                      Bank logos and README media
evidence/                    Reviewable table evidence
reports/                     Local official-report archive (Git-ignored PDFs)
tests/                       Automated checks
archive/legacy_pilot/        Superseded three-bank prototype
archive/planning/            Historical roadmap material
```

## Disclaimer

EuroBank Prism is an educational research tool, not personalized investment
advice. Verify all observations against the linked official disclosures.
