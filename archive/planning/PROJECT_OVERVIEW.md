# EuroSTOXX Bank Valuation Agent

## Problem

Compare public financial information for EURO STOXX Banks constituents and
identify potentially attractive or expensive banks relative to peers.

## Inputs

- Official quarterly and annual bank reports
- Page-level extracted evidence
- Market prices with retrieval timestamps
- Comparable banking and valuation metrics

## Workflow

```text
Official reports -> PDF extraction -> evidence archive
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

## Run

```powershell
& "C:\FG\.venv\Scripts\python.exe" `
  "C:\FG\Roadmap to AI\run_pilot_pipeline.py"
streamlit run "C:\FG\Roadmap to AI\pilot_dashboard.py"
```

This is a research screening tool, not personalized investment advice.
