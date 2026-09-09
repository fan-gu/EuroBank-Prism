# Management-language v2.4.2 validation

This release excludes standardized rounding and table-summation notes before
modal counting. Original source sentences and pages remain in each document's
filter audit.

## Acceptance summary

- Rule version: `management-language-v2.4.2`; schema version: `1.4`
- Source set: the same 66 local official PDFs; no network or LLM call
- Coverage: 23/23 banks; 7 continuous four-period histories
- Audit result: 44 calculation-footnote clauses masked, including 38 standalone
  passages
- GLE's `sum of values ... may differ ... due to rounding rules` note no longer
  appears in scored or warning evidence
- Real narrative attached to a rounding note is retained and scored
- Routine procedural-footnote filtering from v2.4.1 remains active
- Automated tests: 42 passed

## Audit consequence

ISP H1 2026 repeats a rounding note across many table pages. Removing passages
that were admitted only by the note's weak modal reduced its analyzed narrative
sample from 2,029 to 929 words, a 54% reduction versus v2.4.1. This correctly
triggers the denominator-shrink review gate. The latest document still exceeds
the standard coverage gate, but its revised score remains provisional and its
sample should be reviewed.

Peer scores were robustly recalibrated after filtering. ISP moved from 17.1 to
42.9 and GLE from 81.8 to 85.0 on the peer-relative axis. These are methodology
corrections, not period-on-period changes in management language.
