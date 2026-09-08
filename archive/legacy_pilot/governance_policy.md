# EuroBank Prism — Governance policy

## Purpose

The agent produces reproducible, evidence-linked relative-value research on
EURO STOXX Banks constituents. It is a screening and research aid, not
personalized investment advice.

## Source hierarchy

1. Official bank investor-relations reports and results releases
2. Official STOXX constituent and methodology files
3. Licensed or clearly identified market-data providers for prices
4. Secondary sources only for discovery, never as the sole evidence for a key metric

## Required provenance

Every extracted metric must retain the bank, ticker, report date, period,
document type, source URL, page (when applicable), extraction timestamp, and
validation status.

## Comparability rules

- Compare peers only when the reporting period, frequency, currency, scope,
  and metric definition match.
- Same-bank time-series comparisons may use different periods, but must keep
  the same frequency and definition.
- Missing or incompatible values are excluded, never silently imputed.

## Communication rules

- Separate reported facts, calculated values, and analyst interpretation.
- Use “potentially attractive/expensive relative to peers,” not “buy” or “sell.”
- Show methodology, weights, timestamps, data gaps, and sensitivity results.
- State that past performance and model rankings do not guarantee future returns.

## Human review

An analyst must review source quality, unusual values, period alignment, and
the final report before external publication.
