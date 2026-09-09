# Management-language v2.4 validation

Generated from the same 66 local source PDFs used by v2.3. No network or LLM
call was used. Scores remain research signals and are not publication-eligible.

## Acceptance summary

- Rule version: `management-language-v2.4`
- Coverage: 23/23 banks before and after
- Continuous four-period histories: 8 before and after
- Insufficient latest-period banks: 0 before and after
- Uncertainty hits: 249 → 156 (-37.3%)
- All-document filter audit: 84 neutral risk labels, 12 repeats, 3 negated
  hits, and 8 technical prior-period passages
- Documents with more than 25% denominator shrinkage: 0
- Modal-rate review flags: ISP, INGA, and BKT; diagnostic only
- Automated tests: 38 passed

The largest peer-score movements partly reflect median-MAD recalibration after
pollution was removed across the cohort. They do not necessarily represent an
equal change in a bank's absolute wording. Weights and calibration formula were
not tuned to preserve the old ranking.

## Latest-period bank comparison

Audit counters in this table refer to each bank's latest document; the aggregate
figures above cover all 66 documents.

| Bank | Peer v2.3 | Peer v2.4 | Δ | Absolute v2.3 | Absolute v2.4 | Uncertainty v2.3 | Uncertainty v2.4 | Risk labels | Repeats | Negated | Prior-period |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ABN | 56.2 | 54.9 | -1.3 | 69.6 | 100.0 | 39.22 | 0.00 | 2 | 0 | 0 | 0 |
| ACA | 47.6 | 49.7 | +2.1 | 41.3 | 48.2 | 6.84 | 1.71 | 3 | 0 | 0 | 0 |
| AIBG | 60.1 | 60.0 | -0.1 | 65.0 | 65.0 | 0.00 | 0.00 | 0 | 0 | 0 | 0 |
| BAMI | 45.5 | 43.6 | -1.9 | 50.9 | 54.9 | 4.38 | 1.46 | 2 | 0 | 0 | 0 |
| BBVA | 53.9 | 52.9 | -1.0 | 74.7 | 74.7 | 1.26 | 1.26 | 0 | 0 | 0 | 0 |
| BG | 68.5 | 71.1 | +2.6 | 57.9 | 57.9 | 17.59 | 17.59 | 0 | 0 | 0 | 0 |
| BIRG | 60.8 | 62.5 | +1.7 | 56.3 | 64.1 | 3.90 | 0.00 | 1 | 0 | 0 | 1 |
| BKT | 48.9 | 45.2 | -3.7 | 36.2 | 46.7 | 11.67 | 3.89 | 3 | 0 | 1 | 0 |
| BNP | 65.1 | 70.0 | +4.9 | 42.2 | 46.7 | 3.17 | 1.81 | 0 | 0 | 0 | 1 |
| BPE | 40.8 | 45.0 | +4.2 | 60.0 | 63.7 | 5.45 | 2.73 | 3 | 0 | 0 | 0 |
| CABK | 62.7 | 63.5 | +0.8 | 65.2 | 67.6 | 1.77 | 0.00 | 1 | 0 | 0 | 0 |
| CBK | 49.7 | 48.1 | -1.6 | 45.2 | 47.8 | 8.84 | 6.88 | 2 | 0 | 0 | 0 |
| DBK | 41.9 | 39.2 | -2.7 | 46.4 | 46.4 | 3.04 | 3.04 | 0 | 0 | 0 | 0 |
| EBS | 48.2 | 44.2 | -4.0 | 42.0 | 42.0 | 0.00 | 0.00 | 0 | 0 | 0 | 0 |
| FBK | 52.7 | 50.2 | -2.5 | 49.0 | 52.9 | 2.92 | 0.00 | 1 | 0 | 1 | 0 |
| GLE | 66.6 | 73.6 | +7.0 | 70.0 | 76.4 | 4.81 | 0.00 | 2 | 0 | 0 | 0 |
| INGA | 40.7 | 34.4 | -6.3 | 47.9 | 47.9 | 5.63 | 5.63 | 0 | 0 | 0 | 0 |
| ISP | 34.2 | 25.2 | -9.0 | 15.8 | 15.0 | 3.32 | 1.93 | 3 | 1 | 0 | 6 |
| KBC | 55.7 | 54.2 | -1.5 | 62.9 | 62.9 | 6.05 | 6.05 | 0 | 0 | 0 | 0 |
| NDA-FI | 39.8 | 41.0 | +1.2 | 26.4 | 37.6 | 12.40 | 4.13 | 2 | 0 | 0 | 0 |
| SAB | 50.0 | 50.0 | 0.0 | 45.8 | 50.6 | 6.99 | 3.80 | 1 | 1 | 0 | 0 |
| SAN | 57.0 | 58.1 | +1.1 | 59.2 | 62.2 | 4.43 | 2.82 | 3 | 3 | 1 | 0 |
| UCG | 40.7 | 34.9 | -5.8 | 28.0 | 28.9 | 9.24 | 8.63 | 1 | 0 | 0 | 0 |

## Human spot-check conclusions

- Neutral metric and taxonomy phrases such as `cost of risk`, `risk-weighted
  assets`, and `risk management` no longer create uncertainty hits.
- Standalone outlook risk remains eligible.
- Relief constructions such as `lower tax pressure`, `lower market volatility`,
  and `limited balance sheet risk` are dropped rather than converted to positive.
- Negation does not cross punctuation or scope-breaking prepositions.
- BNP, ISP, and BIRG technical restatement notes were removed. A current-period
  GLE result using `restated` in a live distribution calculation was retained.
- Useful year-on-year comparisons and the BPE guidance regression sentence remain
  eligible.
