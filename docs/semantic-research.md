# Semantic research

EuroBank Prism's semantic layer searches 66 official reports across all 23
banks. It is deliberately separate from deterministic scoring.

```text
Official PDF page
  -> legal, rounding and procedural-footnote filters
  -> page-bound research chunks
  -> Gemini Embeddings 2 document vectors (offline build)
  -> bundled cosine index (.npz) stored as a versioned retrieval artefact

User question
  -> Gemini query vector
  -> local cosine retrieval (top six)
  -> Gemini 3.6 Flash grounded answer
  -> [E#] citations with bank, period, PDF page and official link
```

The current index contains 3,179 chunks with 768 dimensions. It is bundled with
the repository/container at deployment time rather than running as a separate
local service. Document and query texts use the asymmetric formats recommended
for Gemini Embeddings 2. Queries may cover the full universe or one selected
bank.

## Governance boundaries

- Retrieved report text is treated as untrusted data, never as an instruction.
- The answer model may use only retrieved evidence and must cite material claims.
- Missing evidence is reported as insufficient; values are never invented.
- Legal safe-harbour text, routine approval conditions and standardized rounding
  notes are removed before embedding.
- Semantic output cannot alter a numerical score, language score, price signal or
  investment group.
- Rebuild the index after the report archive or pollution rules change:

```powershell
python build_semantic_index.py
```

The deployed app requires `GEMINI_API_KEY` in Streamlit Secrets. The key is not
stored in the repository or the index.
