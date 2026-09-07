"""User-facing Streamlit dashboard for all 23 EURO STOXX Banks constituents."""

from pathlib import Path
from datetime import date, datetime
import json
import subprocess
import sys

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from app.language_signals import period_sort_key

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent
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
    market_path = BASE_DIR / "market_confirmation.json"
    market_confirmation = (
        json.loads(market_path.read_text(encoding="utf-8"))
        if market_path.exists()
        else {"records": [], "methodology": {}}
    )
    return banks, scores, universe, report_pages, table_evidence, language_signals, market_confirmation


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


def build_signal_cube(rows):
    """Build the interactive three-coordinate research view."""
    quadrant_colors = {
        "Confirmed strength": "#35c48d",
        "Potential turnaround": "#4fa3ff",
        "Early warning": "#ffb347",
        "High-risk screen": "#ef6262",
    }
    figure = go.Figure()
    reference_planes = [
        go.Surface(x=[[50, 50], [50, 50]], y=[[0, 100], [0, 100]], z=[[0, 0], [100, 100]]),
        go.Surface(x=[[0, 100], [0, 100]], y=[[50, 50], [50, 50]], z=[[0, 0], [100, 100]]),
        go.Surface(x=[[0, 100], [0, 100]], y=[[0, 0], [100, 100]], z=[[50, 50], [50, 50]]),
    ]
    for plane in reference_planes:
        plane.update(
            showscale=False,
            opacity=0.055,
            colorscale=[[0, "#8fa1bd"], [1, "#8fa1bd"]],
            hoverinfo="skip",
        )
        figure.add_trace(plane)
    figure.add_trace(
        go.Scatter3d(
            x=[row["Language score"] for row in rows],
            y=[row["Market confirmation"] for row in rows],
            z=[row["Numeric score"] for row in rows],
            mode="markers+text",
            text=[row["Ticker"] for row in rows],
            textposition="top center",
            textfont={"size": 10, "color": "#f4f6fb"},
            marker={
                "size": 10,
                "color": [quadrant_colors.get(row["Research quadrant"], "#9fa8b8") for row in rows],
                "line": {"color": "#f4f6fb", "width": 1},
                "opacity": 0.92,
            },
            customdata=[
                [row["Bank"], row["Research quadrant"], row["Market regime"], row["Gap"]]
                for row in rows
            ],
            hovertemplate=(
                "<b>%{customdata[0]} (%{text})</b><br>"
                "Fundamentals & valuation: %{z:.1f}<br>Language: %{x:.1f}<br>"
                "Market confirmation: %{y:.1f}<br>"
                "Numeric-language gap: %{customdata[3]:+.1f}<br>"
                "%{customdata[1]} · %{customdata[2]}<extra></extra>"
            ),
            name="Banks",
        )
    )
    axis_style = {
        "range": [0, 100],
        "tickvals": [0, 25, 50, 75, 100],
        "gridcolor": "rgba(160,175,200,0.18)",
        "zerolinecolor": "rgba(160,175,200,0.35)",
        "backgroundcolor": "rgba(14,18,27,0.60)",
        "showbackground": True,
    }
    figure.update_layout(
        height=900,
        margin={"l": 0, "r": 0, "t": 12, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        scene={
            "xaxis": {**axis_style, "title": "Management language — horizontal"},
            "yaxis": {**axis_style, "title": "Market confirmation — depth"},
            "zaxis": {**axis_style, "title": "Fundamentals & valuation — vertical"},
            "aspectmode": "cube",
            "camera": {"eye": {"x": 1.50, "y": 1.75, "z": 1.20}},
        },
    )
    return figure


st.set_page_config(page_title="EuroBank Prism", page_icon="🏦", layout="wide")
st.title("EuroBank Prism")
st.caption(
    "Three visible coordinates. One clearer view. · "
    "EURO STOXX Banks research intelligence"
)
st.caption("Current release: fundamentals and management language, with an independent market-positioning overlay")

if st.button("Refresh data"):
    with st.status("Refreshing all 23 banks...", expanded=False) as status:
        fundamental_result = subprocess.run([sys.executable, str(BASE_DIR / "build_full_universe.py")], cwd=BASE_DIR, capture_output=True, text=True)
        market_result = subprocess.run([sys.executable, str(BASE_DIR / "build_market_confirmation.py")], cwd=BASE_DIR, capture_output=True, text=True)
        if fundamental_result.returncode == 0 and market_result.returncode == 0:
            status.update(label="Refresh complete", state="complete")
            st.cache_data.clear()
            st.rerun()
        else:
            status.update(label="Refresh failed", state="error")
            st.code((fundamental_result.stderr or fundamental_result.stdout) + "\n" + (market_result.stderr or market_result.stdout))

banks, scores, universe, report_pages, table_evidence, language_signals, market_confirmation = load_data()
scored_tickers = {row["ticker"] for row in scores if row["status"] == "ranked"}
language_coverage = language_signals.get("coverage", {})
market_by_ticker = {row["ticker"]: row for row in market_confirmation.get("records", [])}
market_coverage = sum(
    row.get("status") == "market_confirmation_available"
    for row in market_by_ticker.values()
)
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
        "Market confirmation": market_by_ticker.get(row["ticker"], {}).get("market_confirmation_score"),
        "Market regime": market_by_ticker.get(row["ticker"], {}).get("market_regime", "Insufficient history"),
    }
    for row in signal_rows
    if row.get("numeric_score") is not None
    and row.get("language_score") is not None
    and market_by_ticker.get(row["ticker"], {}).get("market_confirmation_score") is not None
]

st.subheader("Three-signal research cube")
st.caption(
    "Rotate and zoom to inspect each bank across fundamentals and valuation, "
    "management language, and market confirmation. Language runs horizontally, market confirmation runs into depth, "
    "and fundamentals run vertically. The translucent planes mark the peer center at 50."
)
if plotted_rows:
    st.plotly_chart(
        build_signal_cube(plotted_rows),
        width="stretch",
        height=900,
        key="front_page_signal_cube",
        config={"displaylogo": False, "scrollZoom": False},
    )
    st.caption(
        "Point colors preserve the fundamental-language diagnostic: green confirmed strength, blue potential turnaround, "
        "amber early warning, and red high-risk screen. Hover for exact values."
    )
    st.caption(
        "Color codes: green #35C48D · blue #4FA3FF · amber #FFB347 · red #EF6262. "
        "A higher market-confirmation score means stronger relative price confirmation—not automatically a better bank or investment."
    )
else:
    st.info("Three-coordinate coverage is not yet available.")
st.caption(
    "Market confirmation is the price-action overlay within Axis 1; it remains a separate coordinate so disagreement is visible. "
    "A future market-expectations axis will require consistent consensus-estimate data."
)

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
    st.subheader("Signal diagnostics")
    st.warning(
        "Research preview only: neither the language signal nor market-confirmation overlay changes the fundamental score. "
        "No quadrant, momentum regime, or combination is a buy or sell recommendation."
    )
    with st.container(horizontal=True):
        st.metric("Bank universe", language_coverage.get("universe_banks", len(universe)), border=True)
        st.metric("Provisional language coverage", language_coverage.get("provisional_banks", 0), border=True)
        st.metric("Market confirmation coverage", f"{market_coverage}/{len(universe)}", border=True)
        st.metric("Insufficient language data", language_coverage.get("insufficient_banks", len(universe)), border=True)
        st.metric("Backtested signals", 0, border=True)

    if plotted_rows:
        market_frame = pd.DataFrame(plotted_rows).sort_values("Market confirmation", ascending=True)
        if not market_frame.empty:
            st.markdown("#### Axis 1 market-positioning overlay")
            market_chart = alt.Chart(market_frame).mark_bar().encode(
                x=alt.X("Market confirmation:Q", title="Peer-relative market-confirmation score", scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("Ticker:N", sort="-x", title=None),
                color=alt.Color(
                    "Market regime:N",
                    scale=alt.Scale(domain=["Confirming", "Neutral", "Unconfirmed"], range=["#35c48d", "#9fa8b8", "#ef6262"]),
                    legend=alt.Legend(title=None, orient="bottom"),
                ),
                tooltip=["Bank:N", "Ticker:N", "Market confirmation:Q", "Market regime:N"],
            ).properties(height=max(360, len(market_frame) * 24))
            st.altair_chart(market_chart, width="stretch")
            st.caption("This overlay peer-ranks 1-, 3-, and 6-month returns plus price versus the 200-day average. It qualifies Axis 1 but does not change the fundamental ranking score.")
    else:
        st.info("No bank currently has complete three-coordinate evidence.")

    matrix_rows = [
        {
            "Bank": row["bank_name"],
            "Ticker": row["ticker"],
            "Numeric": row.get("numeric_score"),
            "Language": row.get("language_score"),
            "Negative pressure": row.get("negative_pressure_score"),
            "Gap": row.get("divergence"),
            "Market confirmation": market_by_ticker.get(row["ticker"], {}).get("market_confirmation_score"),
            "Market regime": market_by_ticker.get(row["ticker"], {}).get("market_regime", "Insufficient history"),
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
            "Market confirmation": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    language_documents = language_signals.get("documents", [])
    if language_documents:
        st.markdown("#### Language evidence and review queue")
        language_tickers = sorted({document["ticker"] for document in language_documents})
        selected_language_ticker = st.pills(
            "View language evidence for",
            language_tickers,
            default=language_tickers[0],
            key="language_evidence_bank",
        )
        language_document = max(
            (document for document in language_documents if document["ticker"] == selected_language_ticker),
            key=lambda document: period_sort_key(document.get("period", "")),
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
            "Four comparable reports enable a preliminary drift observation; eight and a backtest are still required before an event alert can be validated."
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
    market = market_by_ticker.get(selected, {})
    cols = st.columns(7)
    cols[0].metric("Screening score", score["score"] if score["score"] is not None else "N/A")
    cols[1].metric("Share price", f"{metrics.get('price'):.2f}" if metrics.get("price") else "N/A")
    cols[2].metric("P/B", multiple(metrics.get("price_to_book")))
    cols[3].metric("P/E", multiple(metrics.get("price_to_earnings")))
    cols[4].metric("ROE", percent(metrics.get("return_on_equity")))
    cols[5].metric("Dividend yield", percent(metrics.get("dividend_yield")))
    cols[6].metric("Market confirmation", market.get("market_confirmation_score") if market.get("market_confirmation_score") is not None else "N/A")
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
    bank_language_documents.sort(key=lambda document: period_sort_key(document["period"]))
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
                "Absolute language score": [document["features"]["absolute_language_score"] for document in bank_language_documents],
            }
        )
        st.line_chart(history_frame, x="Period", y="Absolute language score")
        signal = next((row for row in language_signals.get("signals", []) if row["ticker"] == selected), {})
        st.caption(
            f"Preliminary drift score: {signal.get('language_drift_score', 'N/A')} · "
            f"status: {signal.get('status', 'N/A').replace('_', ' ')}."
        )

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
    st.markdown("**Language history gate:** four comparable reports of the same document type enable a preliminary drift observation; eight enable drift-alert research. Original sentence and PDF page, human approval, and an out-of-sample backtest are still required before a signal becomes validated research output.")
    st.markdown("**Axis 1 market-confirmation overlay:** 1-month (20%), 3-month (35%), and 6-month (35%) return plus price versus the 200-day average (10%) are peer-percentiled separately. It remains a separate cube coordinate so disagreement stays visible, but it is never blended into the fundamental score.")
    st.markdown("**Controls:** common reporting dates, source evidence, freshness checks, sensitivity analysis, and publication gate.")
    st.markdown("**Scope:** this is a research screening tool, not personalized investment advice.")
    report_path = BASE_DIR / "pilot_report.md"
    if report_path.exists():
        st.download_button("Download analyst report", report_path.read_text(encoding="utf-8"), "pilot_report.md", "text/markdown")
