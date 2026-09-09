# Management-language v2.4.1 validation

This minor release adds a deterministic exception for routine procedural
footnotes attached to dividends, distributions, buybacks and corporate
approvals. The source sentence and page remain in the audit record, but the
procedural clause does not affect the language score or research-triage evidence.

## Acceptance summary

- Rule version: `management-language-v2.4.1`; schema version: `1.3`
- Source set: the same 66 local official PDFs; no network or LLM call
- Coverage: 23/23 banks; 0 latest-period banks insufficient
- Audit result: 32 procedural clauses masked, including 22 standalone passages
- BPER page 33 `Distributions subject to target's achievement` removed from
  scoring and warning evidence
- Genuine conditions remain eligible, including guidance subject to macro or
  market conditions and explicit target-miss/downside language
- Documents with more than 25% denominator shrinkage: 0
- Automated tests: 40 passed

## Governance consequence

Continuous four-period histories decreased from 8 to 7. DBK Q1 2026 had only
one substantive cited passage after its routine ECB-approval footnote was
removed, so it correctly failed the two-passage limited-coverage gate. The
system does not preserve a trend when the old trend depended on pollution.

Peer-language scores were recalibrated after filtering. BPER moved from 45.0 to
55.4 on the peer-relative axis; this is a cohort-relative result, not a claim
that management language improved during the reporting period.
