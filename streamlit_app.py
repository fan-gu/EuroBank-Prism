"""User-facing Streamlit dashboard for all 23 EURO STOXX Banks constituents."""

from pathlib import Path
from datetime import date, datetime
import json
import subprocess
import sys

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from app.dashboard_visuals import image_data_url, layout_signal_labels, padded_domain

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent
LOGO_DIR = BASE_DIR / "assets" / "bank_logos"
COUNTRY_INFO = {
    "Austria": ("AT", "at"), "Belgium": ("BE", "be"),
    "Finland": ("FI", "fi"), "France": ("FR", "fr"),
    "Germany": ("DE", "de"), "Ireland": ("IE", "ie"),
    "Italy": ("IT", "it"), "Netherlands": ("NL", "nl"),
    "Spain": ("ES", "es"),
}


@st.cache_data
def load_data():
    with (BASE_DIR / "full_universe_dataset.json").open(encoding="utf-8") as handle:
        banks = {row["ticker"]: row for row in json.load(handle)}
    with (BASE_DIR / "full_universe_scores.json").open(encoding="utf-8") as handle:
        scores = json.load(handle)
    with (BASE_DIR / "bank_master.json").open(encoding="utf-8") as handle:
        universe = json.load(handle)["constituents"]
    with (BASE_DIR / "official_report_pages.json").open(encoding="utf-8") as handle:
        report_pages = json.load(handle)
    evidence_path = BASE_DIR / "table_evidence_index.json"
    table_evidence = (
        json.loads(evidence_path.read_text(encoding="utf-8"))
        if evidence_path.exists()
        else {"source_count": 0, "table_count": 0, "documents": []}
    )
    language_path = BASE_DIR / "language_signals.json"
    language_signals = (
        json.loads(language_path.read_text(encoding="utf-8"))
        if language_path.exists()
        else {
            "coverage": {"universe_banks": len(universe), "provisional_banks": 0, "insufficient_banks": len(universe)},
            "documents": [],
            "signals": [],
        }
    )
    return banks, scores, universe, report_pages, table_evidence, language_signals


def percent(value):
    return f"{value:.1%}" if isinstance(value, (int, float)) else "Not available"


def multiple(value):
    return f"{value:.2f}x" if isinstance(value, (int, float)) else "Not available"


def decimal(value):
    return f"{value:.2f}" if isinstance(value, (int, float)) else "Not available"


def short_comment(score):
    if score is None:
        return "Insufficient comparable data"
    if score >= 67:
        return "Strong relative screen"
    if score >= 45:
        return "Mixed; broadly mid-pack"
    return "Weak relative screen"


st.set_page_config(page_title="EuroBank Prism", page_icon="🏦", layout="wide")
st.title("EuroBank Prism")
st.caption(
    "Three independent signals. One clearer view. · "
    "EURO STOXX Banks research intelligence"
)
st.caption("Current release: fundamentals + management language live · market confirmation next")

if st.button("Refresh data"):
    with st.status("Refreshing all 23 banks...", expanded=False) as status:
        result = subprocess.run([sys.executable, str(BASE_DIR / "build_full_universe.py")], cwd=BASE_DIR, capture_output=True, text=True)
        if result.returncode == 0:
            status.update(label="Refresh complete", state="complete")
            st.cache_data.clear()
            st.rerun()
        status.update(label="Refresh failed", state="error")
        st.code(result.stderr or result.stdout)

banks, scores, universe, report_pages, table_evidence, language_signals = load_data()
scored_tickers = {row["ticker"] for row in scores if row["status"] == "ranked"}
language_coverage = language_signals.get("coverage", {})
ranking_tab, signals_tab, details_tab, evidence_tab, methodology_tab = st.tabs(
    ["Relative ranking", "Signals", "Bank details", "Evidence", "Methodology"]
)

with ranking_tab:
    st.subheader("Relative ranking")
    timestamps = [bank.get("retrieved_at") for bank in banks.values() if bank.get("retrieved_at")]
    if timestamps:
        latest = max(timestamps)
        observed = datetime.fromisoformat(latest.replace("Z", "+00:00")).date()
        age = (date.today() - observed).days
        (st.error if age > 3 else st.info)(f"Provider data retrieved: {observed} ({age} day(s) old)." + (" Refresh before analysis." if age > 3 else ""))
    st.caption(
        f"Coverage: {len(scored_tickers)}/{len(universe)} banks ranked · "
        f"{language_coverage.get('provisional_banks', 0)}/{len(universe)} banks with provisional language signals"
    )
    ranking_rows = []
    for i, row in enumerate((item for item in scores if item["status"] == "ranked"), 1):
        bank = banks[row["ticker"]]
        metrics = bank.get("metrics", {})
        country_code, flag_code = COUNTRY_INFO.get(bank["country"], (bank["country"], ""))
        ranking_rows.append({
            "Rank": i,
            "Flag": f"https://flagcdn.com/20x15/{flag_code}.png" if flag_code else "",
            "Country": country_code,
            "Bank": row["bank_name"],
            "Ticker": row["ticker"],
            "Index weight": bank.get("weight_percent"),
            "Current price": metrics.get("price"),
            "P/E": metrics.get("price_to_earnings"),
            "P/B": metrics.get("price_to_book"),
            "ROE": metrics.get("return_on_equity") * 100 if metrics.get("return_on_equity") is not None else None,
            "Div. yield": metrics.get("dividend_yield") * 100 if metrics.get("dividend_yield") is not None else None,
            "Score": row["score"],
            "Comment": short_comment(row["score"]),
        })
    st.dataframe(
        ranking_rows,
        width="stretch",
        hide_index=True,
        height=845,
        row_height=28,
        column_config={
            "Flag": st.column_config.ImageColumn("Flag", width=38),
            "Index weight": st.column_config.NumberColumn("Index wt.", format="%.2f%%"),
            "Current price": st.column_config.NumberColumn("Price", format="€%.2f"),
            "P/E": st.column_config.NumberColumn("P/E", format="%.2fx"),
            "P/B": st.column_config.NumberColumn("P/B", format="%.2fx"),
            "ROE": st.column_config.NumberColumn("ROE", format="%.1f%%"),
            "Div. yield": st.column_config.NumberColumn("Div. yield", format="%.1f%%"),
            "Score": st.column_config.NumberColumn("Score", format="%.1f"),
        },
    )
    st.warning("A higher score indicates stronger relative inputs under this methodology; it is not a buy or sell recommendation.")

with signals_tab:
    st.subheader("Independent numeric and management-language signals")
    st.warning(
        "Research preview only: the language score is peer-calibrated to correct management-document optimism, "
        "but document genres and reporting periods are not yet aligned. "
        "No quadrant label is a buy or sell recommendation."
    )
    with st.container(horizontal=True):
        st.metric("Bank universe", language_coverage.get("universe_banks", len(universe)), border=True)
        st.metric("Provisional language coverage", language_coverage.get("provisional_banks", 0), border=True)
        st.metric("Insufficient language data", language_coverage.get("insufficient_banks", len(universe)), border=True)
        st.metric("Backtested signals", 0, border=True)

    signal_rows = language_signals.get("signals", [])
    plotted_rows = [
        {
            "Ticker": row["ticker"],
            "Bank": row["bank_name"],
            "Numeric score": row["numeric_score"],
            "Language score": row["language_score"],
            "Negative pressure": row.get("negative_pressure_score"),
            "Gap": row["divergence"],
            "Research quadrant": row["quadrant"],
        }
        for row in signal_rows
        if row.get("numeric_score") is not None and row.get("language_score") is not None
    ]
    if plotted_rows:
        for row in plotted_rows:
            logo_path = LOGO_DIR / f"{row['Ticker']}.png"
            row["Logo"] = image_data_url(logo_path) if logo_path.exists() else ""
        x_domain = padded_domain([row["Numeric score"] for row in plotted_rows])
        y_domain = padded_domain([row["Language score"] for row in plotted_rows])
        signal_frame = pd.DataFrame(
            layout_signal_labels(plotted_rows, x_domain, y_domain)
        )
        x_axis = alt.X(
            "Numeric score:Q",
            title="Numeric relative-value score",
            scale=alt.Scale(domain=x_domain, nice=False, zero=False),
        )
        y_axis = alt.Y(
            "Language score:Q",
            title="Peer-calibrated management-language score",
            scale=alt.Scale(domain=y_domain, nice=False, zero=False),
        )
        vertical = alt.Chart(pd.DataFrame({"cut": [50]})).mark_rule(
            color="#7a8599", strokeDash=[6, 6]
        ).encode(x=alt.X("cut:Q", scale=alt.Scale(domain=x_domain, nice=False, zero=False)))
        horizontal = alt.Chart(pd.DataFrame({"cut": [50]})).mark_rule(
            color="#7a8599", strokeDash=[6, 6]
        ).encode(y=alt.Y("cut:Q", scale=alt.Scale(domain=y_domain, nice=False, zero=False)))
        halos = alt.Chart(signal_frame).mark_circle(
            size=980, opacity=0.28, strokeWidth=2
        ).encode(
            x=x_axis,
            y=y_axis,
            color=alt.Color(
                "Research quadrant:N",
                scale=alt.Scale(
                    domain=["Confirmed strength", "Potential turnaround", "Early warning", "High-risk screen"],
                    range=["#35c48d", "#4fa3ff", "#ffb347", "#ef6262"],
                ),
                legend=alt.Legend(title=None, orient="bottom", columns=4),
            ),
            tooltip=["Bank:N", "Ticker:N", "Numeric score:Q", "Language score:Q", "Negative pressure:Q", "Gap:Q", "Research quadrant:N"],
        )
        logos = alt.Chart(signal_frame).mark_image(width=28, height=28).encode(
            x=x_axis,
            y=y_axis,
            url=alt.Url("Logo:N"),
            tooltip=["Bank:N", "Ticker:N", "Numeric score:Q", "Language score:Q", "Negative pressure:Q", "Gap:Q", "Research quadrant:N"],
        )
        connectors = alt.Chart(signal_frame).mark_rule(
            color="#aeb8c8", opacity=0.55, strokeWidth=1
        ).encode(
            x=x_axis,
            y=y_axis,
            x2=alt.X2("Label x:Q"),
            y2=alt.Y2("Label y:Q"),
        )
        label_outline = alt.Chart(signal_frame).mark_text(
            color="#10131a", fontWeight="bold", fontSize=12,
            stroke="#10131a", strokeWidth=4,
        ).encode(x="Label x:Q", y="Label y:Q", text="Ticker:N")
        labels = alt.Chart(signal_frame).mark_text(
            color="#f4f6fb", fontWeight="bold", fontSize=12,
        ).encode(x="Label x:Q", y="Label y:Q", text="Ticker:N")
        st.altair_chart(
            (
                vertical + horizontal + connectors + halos + logos
                + label_outline + labels
            ).properties(height=600, padding={"left": 4, "right": 4, "top": 8, "bottom": 4}),
            width="stretch",
        )
        st.caption(
            "Upper-right: confirmed strength · upper-left: potential turnaround · "
            "lower-right: early warning · lower-left: high-risk screen. "
            "The horizontal 50 line is the robust peer center, not generic sentiment neutrality."
        )
    else:
        st.info("No bank currently has sufficient language evidence for the matrix.")

    matrix_rows = [
        {
            "Bank": row["bank_name"],
            "Ticker": row["ticker"],
            "Numeric": row.get("numeric_score"),
            "Language": row.get("language_score"),
            "Negative pressure": row.get("negative_pressure_score"),
            "Gap": row.get("divergence"),
            "Quadrant": row.get("quadrant") or "Not assigned",
            "Coverage status": row["status"],
        }
        for row in signal_rows
    ]
    st.dataframe(
        matrix_rows,
        width="stretch",
        hide_index=True,
        column_config={
            "Numeric": st.column_config.NumberColumn(format="%.1f"),
            "Language": st.column_config.NumberColumn(format="%.1f"),
            "Negative pressure": st.column_config.NumberColumn(format="%.1f"),
            "Gap": st.column_config.NumberColumn(format="%+.1f"),
        },
    )

    language_documents = language_signals.get("documents", [])
    if language_documents:
        st.markdown("#### Language evidence and review queue")
        language_tickers = [document["ticker"] for document in language_documents]
        selected_language_ticker = st.pills(
            "View language evidence for",
            language_tickers,
            default=language_tickers[0],
            key="language_evidence_bank",
        )
        language_document = next(
            document for document in language_documents if document["ticker"] == selected_language_ticker
        )
        language_signal = next(
            row for row in signal_rows if row["ticker"] == selected_language_ticker
        )
        with st.container(horizontal=True):
            st.metric("Language score", language_signal["language_score"], border=True)
            st.metric("Negative pressure", language_signal.get("negative_pressure_score"), border=True)
            st.metric("Numeric-language gap", f"{language_signal['divergence']:+.1f}", border=True)
            st.metric("History available", f"{language_document['history_periods']} period", border=True)
            st.metric("Review status", "Pending", border=True)
        st.caption(
            "Weak-modal and uncertainty increases plus confidence-to-caution reversals "
            "will add drift penalties once comparable history is available."
        )
        st.caption(
            f"{language_document['document_type'].replace('_', ' ').title()} · "
            f"{language_document['period']} · {language_document['analyzed_word_count']:,} analyzed words · "
            f"rule {language_signals.get('rule_version', 'unknown')}"
        )
        if language_signal.get("alerts"):
            for alert in language_signal["alerts"]:
                st.warning(alert["message"] + " Human review required.")
        for item in language_document.get("evidence", []):
            hit_labels = [name.replace("_", " ") for name, value in item["hits"].items() if value]
            with st.container(border=True):
                st.caption(
                    f"PDF page {item['page']} · {', '.join(hit_labels) or 'guidance'} · "
                    f"{item['review_status'].replace('_', ' ')}"
                )
                st.write(item["sentence"])
        if language_document.get("source_url"):
            st.link_button(
                "Open official source",
                language_document["source_url"],
                icon=":material/open_in_new:",
            )

with details_tab:
    selected = st.selectbox("Select a bank", [row["ticker"] for row in universe])
    bank = banks[selected]
    score = next((row for row in scores if row["ticker"] == selected), {"score": None, "components": {}})
    st.subheader(f"{bank['bank_name']} ({selected})")
    st.write(f"Country: **{bank['country']}** · market ticker: **{bank['market_ticker']}**")
    metrics = bank.get("metrics", {})
    prudential = bank.get("prudential_metrics", {})
    cols = st.columns(6)
    cols[0].metric("Screening score", score["score"] if score["score"] is not None else "N/A")
    cols[1].metric("Share price", f"{metrics.get('price'):.2f}" if metrics.get("price") else "N/A")
    cols[2].metric("P/B", multiple(metrics.get("price_to_book")))
    cols[3].metric("P/E", multiple(metrics.get("price_to_earnings")))
    cols[4].metric("ROE", percent(metrics.get("return_on_equity")))
    cols[5].metric("Dividend yield", percent(metrics.get("dividend_yield")))
    st.markdown("#### Additional equity-research metrics")
    st.dataframe([
        {"Metric": "Forward P/E", "Value": multiple(metrics.get("forward_price_to_earnings"))},
        {"Metric": "Book value per share", "Value": decimal(metrics.get("book_value_per_share"))},
        {"Metric": "Earnings per share", "Value": decimal(metrics.get("earnings_per_share"))},
        {"Metric": "Return on assets", "Value": percent(metrics.get("return_on_assets"))},
        {"Metric": "Profit margin", "Value": percent(metrics.get("profit_margin"))},
        {"Metric": "Payout ratio", "Value": percent(metrics.get("payout_ratio"))},
        {"Metric": "Earnings growth", "Value": percent(metrics.get("earnings_growth"))},
        {"Metric": "Revenue growth", "Value": percent(metrics.get("revenue_growth"))},
        {"Metric": "Market capitalization", "Value": f"{metrics.get('market_cap'):,.0f}" if metrics.get("market_cap") else "Not available"},
        {"Metric": "Beta", "Value": f"{metrics.get('beta'):.2f}" if metrics.get("beta") is not None else "Not available"},
    ], width="stretch", hide_index=True)
    st.markdown(f"**Verified prudential overlay:** CET1 {percent(prudential.get('cet1_ratio'))} · RoTE {percent(prudential.get('rote'))}")
    st.markdown("#### Score contribution")
    st.dataframe([
        {"Metric": metric.replace("_", " ").title(), "Raw value": detail["raw_value"], "Percentile score": detail["percentile_score"], "Weight": f"{detail['weight']:.0%}"}
        for metric, detail in score.get("components", {}).items()
    ], width="stretch", hide_index=True)
    bank_language_documents = [
        document for document in language_signals.get("documents", []) if document["ticker"] == selected
    ]
    st.markdown("#### Management-language history")
    if len(bank_language_documents) < 4:
        st.info(
            "Four comparable periods are needed for a preliminary language trend; "
            "eight periods are required before drift alerts can enter research validation."
        )
    else:
        history_frame = pd.DataFrame(
            {
                "Period": [document["period"] for document in bank_language_documents],
                "Language score": [document["features"]["language_score"] for document in bank_language_documents],
            }
        )
        st.line_chart(history_frame, x="Period", y="Language score")

with evidence_tab:
    st.subheader("Official financial reports")
    st.caption("Links open official issuer reporting pages where the latest publication is maintained.")
    st.dataframe(
        [
            {
                "Bank": row["bank_name"],
                "Ticker": row["ticker"],
                "Annual report": report_pages[row["ticker"]]["annual"],
                "Quarterly / interim": report_pages[row["ticker"]]["quarterly"],
            }
            for row in universe
        ],
        width="stretch",
        hide_index=True,
        height=845,
        column_config={
            "Annual report": st.column_config.LinkColumn("Latest annual report", display_text="Open annual reports"),
            "Quarterly / interim": st.column_config.LinkColumn("Latest quarterly / interim", display_text="Open results"),
        },
    )

    st.markdown("#### Extracted table evidence")
    st.caption(
        f"{table_evidence.get('table_count', 0)} metric-relevant table candidates "
        f"from {table_evidence.get('source_count', 0)} locally processed official reports. "
        "Candidates are excluded from ranking until their definition, period, unit and scope are reviewed."
    )
    evidence_documents = [
        document for document in table_evidence.get("documents", []) if document.get("tables")
    ]
    if not evidence_documents:
        st.info("No structured table evidence has been generated yet.")
    else:
        evidence_tickers = [document["ticker"] for document in evidence_documents]
        selected_evidence_ticker = st.pills(
            "View extracted evidence for",
            evidence_tickers,
            default=evidence_tickers[0],
            key="evidence_bank",
        )
        selected_document = next(
            (document for document in evidence_documents if document["ticker"] == selected_evidence_ticker),
            evidence_documents[0],
        )
        st.write(
            f"**{selected_document.get('bank_name') or selected_document['ticker']}** · "
            f"{selected_document['document']} · {selected_document['table_count']} retained table(s)"
        )
        for table in selected_document["tables"]:
            metric_label = ", ".join(
                metric.replace("_", " ").upper() for metric in table["matched_metrics"]
            )
            with st.expander(
                f"Page {table['page']} · {metric_label} · review pending",
                icon=":material/table_view:",
            ):
                image_path = BASE_DIR / table["evidence_image"] if table.get("evidence_image") else None
                if image_path and image_path.exists():
                    st.image(image_path, caption=f"Source table on PDF page {table['page']}")
                st.dataframe(table.get("rows", []), width="stretch", hide_index=True)
                st.caption(table.get("page_excerpt", ""))
                if table.get("source_url"):
                    st.link_button(
                        "Open official source",
                        table["source_url"],
                        icon=":material/open_in_new:",
                    )

with methodology_tab:
    st.subheader("Methodology and controls")
    st.markdown("#### Data quality")
    st.write(
        f"Market-data ranking coverage: **{len(scored_tickers)}/{len(universe)} banks**. "
        f"Provisional management-language coverage: "
        f"**{language_coverage.get('provisional_banks', 0)}/{len(universe)} banks**. "
        f"Insufficient language data: **{language_coverage.get('insufficient_banks', len(universe))} banks**."
    )
    st.caption(
        "Detailed constituent-level coverage remains available in the internal coverage report and automated tests."
    )
    st.markdown("**Common 23-bank score:** P/B 25%, P/E 15%, ROE 20%, ROA 10%, dividend yield 10%, earnings growth 10%, and revenue growth 10%. Lower valuation multiples score higher; higher returns, yield, and growth score higher. Percentile ranking limits the influence of extreme values.")
    st.markdown("**Official-report overlay:** CET1, leverage, LCR, NSFR, NPL ratio, NPL coverage, cost of risk, NIM, cost/income, loan/deposit ratio, and IRRBB sensitivities are included only when period-aligned evidence is available.")
    st.markdown("**Independent language axis:** negative terms, uncertainty, weak commitment and cautious or euphemistic wording create an explicit negative-pressure penalty. Positive wording is measured separately, then the net result is robustly centered against the 23-bank peer cohort to correct management-document optimism. The numeric and language axes are not combined.")
    st.markdown("**Language history gate:** four comparable periods enable a preliminary trend; eight enable drift alerts. Original sentence and PDF page, human approval, and an out-of-sample backtest are still required before a signal becomes validated research output.")
    st.markdown("**Controls:** common reporting dates, source evidence, freshness checks, sensitivity analysis, and publication gate.")
    st.markdown("**Scope:** this is a research screening tool, not personalized investment advice.")
    report_path = BASE_DIR / "pilot_report.md"
    if report_path.exists():
        st.download_button("Download analyst report", report_path.read_text(encoding="utf-8"), "pilot_report.md", "text/markdown")
