# AI + Finance Learning Roadmap

## Month 1 — Python and AI development foundations

| Week | Focus | Main output |
|---|---|---|
| 1 | Python basics: variables, conditions, loops, functions, errors | Portfolio P&L calculator |
| 2 | Lists, dictionaries, nested data, JSON | European Banks Metrics Explorer |
| 3 | Pandas, CSV, grouping, missing data, joins | Combined bank financial/risk dataset |
| 4 | APIs, Git, GitHub, LLM API | Currency converter and financial-news summariser |

## Month 2 — LLM foundations

| Week | Focus | Main output |
|---|---|---|
| 5 | Tokens, context windows, prompting, structured output | Validated financial-news JSON extractor |
| 6 | Embeddings and semantic search | Similarity-search prototype |
| 7 | Vector databases and FAISS | Local financial-document index |
| 8 | Retrieval quality and evaluation | Bank research search application |

## Month 3 — RAG applications

| Week | Focus | Main output |
|---|---|---|
| 9 | PDF extraction, cleaning, chunking, metadata | Document-ingestion pipeline |
| 10 | RAG fundamentals | Annual Report Q&A assistant |
| 11 | RAG tuning: retrieval, citations, hallucination controls | Evaluated RAG assistant |
| 12 | Complete project | European Bank Earnings Intelligence |

## Month 4 — AI agents for finance

| Week | Focus | Main output |
|---|---|---|
| 13 | Tools, function calling, agent loops | Basic tool-using agent |
| 14 | Agent tool design and guardrails | Financial-data agent |
| 15 | Financial analysis workflow | European Equity Analyst Agent |
| 16 | Agent evaluation, cost, latency, reliability | Agent test and scorecard |

## Month 5 — AI + Finance projects

| Week | Focus | Main output |
|---|---|---|
| 17 | Bank universe and public-data research | EURO STOXX Banks universe and report registry |
| 18 | PDF ingestion and financial-document extraction | Page-cited quarterly/annual report archive |
| 19 | Market data and metric normalization | Comparable bank metrics and price dataset |
| 20 | Horizontal valuation analysis | EuroSTOXX Bank Valuation Agent MVP |

## Month 6 — Portfolio and job search

| Week | Focus | Main output |
|---|---|---|
| 21 | Agent and dashboard integration | End-to-end research workflow |
| 22 | Evaluation and data freshness | Accuracy, latency, reproducibility, and update controls |
| 23 | Governance and analyst communication | Auditable research reports and limitations |
| 24 | GitHub portfolio and job positioning | Published EuroSTOXX Bank Valuation Agent |

## Month 5 project — EuroSTOXX Bank Valuation Agent

The flagship project uses the official EURO STOXX Banks constituent universe,
public quarterly and annual reports, and market-price data. It produces a
relative-value research assessment—not personalized investment advice.

### Week 17 — Bank universe and public-data registry

| Day | Topic |
|---|---|
| 1 | Confirm the official EURO STOXX Banks universe and timestamp it |
| 2 | Create a bank master file with names, tickers, countries, and identifiers |
| 3 | Build an official investor-relations report URL registry |
| 4 | Design report-period and document metadata |
| 5 | Download one quarterly and one annual report for three pilot banks |
| 6 | Test the registry and document source-quality rules |

**Main output:** Versioned bank universe and report registry.

### Week 18 — PDF ingestion and extraction

| Day | Topic |
|---|---|
| 1 | Download PDFs safely and calculate file hashes |
| 2 | Extract text while preserving page numbers |
| 3 | Extract tables and identify difficult scanned PDFs |
| 4 | Chunk reports by section with bank and period metadata |
| 5 | Store page-level citations and document provenance |
| 6 | Build and test the multi-bank report archive |

**Main output:** Page-cited quarterly/annual report archive.

### Week 19 — Market data and comparable metrics

| Day | Topic |
|---|---|
| 1 | Retrieve current and historical stock prices from a permitted provider |
| 2 | Extract valuation and banking metrics from reports |
| 3 | Normalize units, currencies, dates, and percentages |
| 4 | Handle missing, restated, and non-comparable values |
| 5 | Create a structured bank-period metrics table |
| 6 | Validate calculations against source documents |

**Main output:** Comparable bank metrics and market-price dataset.

### Week 20 — Horizontal valuation analysis

| Day | Topic |
|---|---|
| 1 | Calculate peer medians and relative valuation measures |
| 2 | Compare profitability, capital, asset quality, and funding |
| 3 | Build a transparent relative-value scoring framework |
| 4 | Generate cited bank comparison reports with Qwen |
| 5 | Add abstention, stale-data, and source-quality warnings |
| 6 | Package the EuroSTOXX Bank Valuation Agent MVP |

**Main output:** Working MVP that identifies potentially attractive or
expensive banks relative to peers, with evidence and limitations.

## Week 9 — LangGraph agent workflows

| Day | Topic |
|---|---|
| 1 | LangGraph state, nodes, edges, and a compiled workflow |
| 2 | Connect FAISS retrieval as a graph node |
| 3 | Add a Gemini answer-generation node |
| 4 | Conditional routing: answer, retrieve again, or abstain |
| 5 | Tool-calling concepts and controlled agent loops |
| 6 | Build and test a market-risk research workflow |

**Main output:** Inspectable LangGraph risk-research agent.

## Week 10 — Ollama and local LLMs

| Day | Topic |
|---|---|
| 1 | Install Ollama and run a local model |
| 2 | Call Ollama from Python and compare local/API responses |
| 3 | Use Ollama through LangChain |
| 4 | Connect a local LLM to the FAISS retriever |
| 5 | Build a local, citation-grounded RAG assistant |
| 6 | Compare quality, latency, privacy, and cost |

**Main output:** Local Ollama + LangChain RAG assistant.

## Week 11 — RAG quality, citations, and controls

| Day | Topic |
|---|---|
| 1 | Retrieval evaluation: top-k accuracy and test datasets |
| 2 | Chunking, metadata, and retrieval-quality tuning |
| 3 | Citation validation and evidence checks |
| 4 | Hallucination controls: abstention, thresholds, and prompt rules |
| 5 | Compare Gemini and Qwen in the same RAG workflow |
| 6 | Evaluate, document, and publish the controlled RAG assistant |

**Main output:** Evaluated, citation-grounded financial RAG assistant.

## Completed earlier — Weeks 1–8

| Day | Topic |
|---|---|
| 1 | What LLMs do: training, inference, tokens, parameters, hallucinations |
| 2 | Context windows and prompt design |
| 3 | Structured outputs and JSON schemas |
| 4 | Few-shot prompting and output evaluation |
| 5 | Building a robust financial-information extractor |
| 6 | Documentation, tests, Git commit, and GitHub push |
