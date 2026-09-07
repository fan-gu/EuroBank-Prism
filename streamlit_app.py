"""User-facing Streamlit dashboard for all 23 EURO STOXX Banks constituents."""

from pathlib import Path
from datetime import date, datetime
import importlib
import json
import subprocess
import sys

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from app.dashboard_visuals import layout_signal_labels, market_bubble_diameter, padded_domain
from app import investment_groups as investment_groups_module
from app.language_signals import period_sort_key

# Streamlit Cloud can hot-rerun this entry point without restarting imported
# modules. Reload the tiny deterministic rule module so deployed group labels
# and gates always match the current commit.
investment_groups_module = importlib.reload(investment_groups_module)
GROUP_META = investment_groups_module.GROUP_META
GROUP_ORDER = investment_groups_module.GROUP_ORDER
evidence_status = investment_groups_module.evidence_status
investment_group = investment_groups_module.investment_group

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


def build_ranking_rows(scores, banks):
    """Create one canonical ranking table for the homepage and workbench."""
    rows = []
    for rank, score_row in enumerate(
        (item for item in scores if item["status"] == "ranked"), 1
    ):
        bank = banks[score_row["ticker"]]
        metrics = bank.get("metrics", {})
        country_code, flag_code = COUNTRY_INFO.get(
            bank["country"], (bank["country"], "")
        )
        rows.append({
            "Rank": rank,
            "Flag": f"https://flagcdn.com/20x15/{flag_code}.png" if flag_code else "",
            "Country": country_code,
            "Bank": score_row["bank_name"],
            "Ticker": score_row["ticker"],
            "Index weight": bank.get("weight_percent"),
            "Current price": metrics.get("price"),
            "P/E": metrics.get("price_to_earnings"),
            "P/B": metrics.get("price_to_book"),
            "ROE": metrics.get("return_on_equity") * 100 if metrics.get("return_on_equity") is not None else None,
            "Div. yield": metrics.get("dividend_yield") * 100 if metrics.get("dividend_yield") is not None else None,
            "Score": score_row["score"],
            "Comment": short_comment(score_row["score"]),
        })
    return rows


def render_ranking_table(ranking_rows, *, key=None):
    """Render the full-universe table without an internal vertical scrollbar."""
    st.dataframe(
        ranking_rows,
        width="stretch",
        hide_index=True,
        height=845,
        row_height=28,
        key=key,
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


def build_signal_map(rows):
    """Build the two-dimensional signal map with market-sized bubbles."""
    figure = go.Figure()
    x_domain = padded_domain([row["Language score"] for row in rows])
    y_domain = padded_domain([row["Numeric score"] for row in rows])
    positioned = layout_signal_labels(
        rows,
        x_domain,
        y_domain,
        width=1_150,
        height=330,
        x_key="Language score",
        y_key="Numeric score",
    )
    for group_name in GROUP_ORDER:
        group_rows = [row for row in positioned if row["Investment group"] == group_name]
        if not group_rows:
            continue
        figure.add_trace(
            go.Scatter(
            x=[row["Language score"] for row in group_rows],
            y=[row["Numeric score"] for row in group_rows],
            mode="markers",
            marker={
                "size": [market_bubble_diameter(row["Market confirmation"]) for row in group_rows],
                "sizemode": "diameter",
                "color": GROUP_META[group_name]["color"],
                "line": {"color": "#f4f6fb", "width": 1.4},
                "opacity": 0.86,
            },
            customdata=[
                [row["Bank"], row["Ticker"], row["Investment group"], row["Market regime"], row["Gap"], row["Evidence status"], row["Market confirmation"]]
                for row in group_rows
            ],
            hovertemplate=(
                "<b>%{customdata[0]} (%{customdata[1]})</b><br>"
                "Fundamentals & valuation: %{y:.1f}<br>Language: %{x:.1f}<br>"
                "Market confirmation: %{customdata[6]:.1f}<br>"
                "Numeric-language gap: %{customdata[4]:+.1f}<br>"
                "%{customdata[2]} · %{customdata[3]}<br>"
                "Evidence: %{customdata[5]}<extra></extra>"
            ),
            name=group_name,
            )
        )
    for row in positioned:
        figure.add_shape(
            type="line",
            x0=row["Language score"], y0=row["Numeric score"],
            x1=row["Label x"], y1=row["Label y"],
            line={"color": "rgba(210,220,235,0.38)", "width": 1},
        )
        figure.add_annotation(
            x=row["Label x"], y=row["Label y"], text=f"<b>{row['Ticker']}</b>",
            showarrow=False, font={"size": 10, "color": "#f4f6fb"},
            bgcolor="rgba(14,18,27,0.78)", borderpad=3,
        )
    figure.add_vline(x=50, line_width=1, line_dash="dot", line_color="rgba(190,200,220,0.55)")
    figure.add_hline(y=50, line_width=1, line_dash="dot", line_color="rgba(190,200,220,0.55)")
    figure.update_layout(
        height=380,
        margin={"l": 20, "r": 15, "t": 20, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(14,18,27,0.60)",
        showlegend=False,
        xaxis={
            "title": "Management language → stronger",
            "range": x_domain,
            "gridcolor": "rgba(160,175,200,0.16)",
            "zeroline": False,
        },
        yaxis={
            "title": "Fundamentals & valuation → stronger",
            "range": y_domain,
            "gridcolor": "rgba(160,175,200,0.16)",
            "zeroline": False,
        },
        hovermode="closest",
    )
    return figure


st.set_page_config(
    page_title="EuroBank Prism",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
        "Investment group": investment_group(
            row.get("numeric_score"),
            row.get("language_score"),
            market_by_ticker.get(row["ticker"], {}).get("market_confirmation_score"),
        ),
        "Evidence status": evidence_status(row.get("history_periods")),
    }
    for row in signal_rows
    if row.get("numeric_score") is not None
    and row.get("language_score") is not None
    and market_by_ticker.get(row["ticker"], {}).get("market_confirmation_score") is not None
]

ranking_rows = build_ranking_rows(scores, banks)
timestamps = [bank.get("retrieved_at") for bank in banks.values() if bank.get("retrieved_at")]
observed = (
    datetime.fromisoformat(max(timestamps).replace("Z", "+00:00")).date()
    if timestamps else None
)
data_age = (date.today() - observed).days if observed else None
group_counts = {
    group_name: sum(row["Investment group"] == group_name for row in plotted_rows)
    for group_name in GROUP_ORDER
}

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 4rem;}
    .prism-kicker {color:#8fa6c7;font-size:.76rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-top:1.2rem;}
    .prism-rule {height:1px;background:linear-gradient(90deg,#4fa3ff55,transparent);margin:.35rem 0 1.2rem;}
    .prism-group {border-left:4px solid var(--group-color);padding:.1rem 0 .1rem .8rem;min-height:5.4rem;}
    .prism-group-name {font-weight:750;font-size:1rem;}
    .prism-group-count {font-size:1.8rem;font-weight:750;line-height:1.15;}
    .prism-muted {color:#aeb8c7;font-size:.82rem;line-height:1.35;}
    .prism-nav a {display:block;color:#aeb8c7;text-decoration:none;padding:.42rem .2rem;border-left:2px solid #28364b;padding-left:.75rem;}
    .prism-nav a:hover {color:#f4f6fb;border-left-color:#4fa3ff;}
    .prism-legend {display:flex;gap:.3rem;align-items:center;flex-wrap:nowrap;overflow-x:auto;margin:.2rem 0 .42rem;padding-bottom:.1rem;}
    .prism-chip {display:inline-flex;align-items:center;gap:.3rem;border:1px solid #2c3545;border-radius:999px;padding:.2rem .42rem;color:#dce3ee;font-size:.70rem;white-space:nowrap;}
    .prism-dot {width:.62rem;height:.62rem;border-radius:50%;display:inline-block;}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### EuroBank Prism")
    st.caption(f"{len(scored_tickers)}/{len(universe)} banks ranked · 3 independent signals")
    st.markdown(
        """
        <div class="prism-nav">
          <a href="#core-signal-map">Signal map</a>
          <a href="#investment-groups">Investment groups</a>
          <a href="#research-triage">Research triage</a>
          <a href="#full-peer-ranking">Peer ranking</a>
          <a href="#quick-diagnostic">Quick diagnostic</a>
          <a href="#evidence-readiness">Evidence readiness</a>
          <a href="#research-workbench">Research workbench</a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption("Scores are peer-relative research signals, not investment advice.")

brand_col, action_col = st.columns([5.2, 1.45], vertical_alignment="top")
with brand_col:
    st.title("EuroBank Prism")
    st.caption("Three signals. One clearer view. · EURO STOXX Banks research intelligence")
with action_col:
    refresh_clicked = st.button("Refresh data", width="stretch", icon=":material/refresh:")
    if data_age is None:
        st.caption("Data date unavailable")
    elif data_age > 3:
        st.caption(f"⚠ Provider snapshot {observed} · {data_age} days old")
    else:
        st.caption(f"Provider snapshot {observed} · current")

if refresh_clicked:
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

st.markdown("<div id='core-signal-map'></div>", unsafe_allow_html=True)
st.header("Core signal map")
st.caption(
    "Numerical × linguistic: management language runs horizontally and fundamentals & valuation vertically. "
    "Bubble size is market confirmation: larger means stronger relative price confirmation."
)
if plotted_rows:
    legend_chips = "".join(
        f"<span class='prism-chip' title=\"{GROUP_META[group]['meaning']}\">"
        f"<span class='prism-dot' style='background:{GROUP_META[group]['color']}'></span>{group}</span>"
        for group in GROUP_ORDER
    )
    st.markdown(f"<div class='prism-legend'>{legend_chips}</div>", unsafe_allow_html=True)
    st.plotly_chart(
        build_signal_map(plotted_rows),
        width="stretch",
        height=380,
        key="front_page_signal_map",
        config={"displaylogo": False, "scrollZoom": True},
    )

    st.markdown("<div id='investment-groups' class='prism-kicker'>02 · Investment groups</div><div class='prism-rule'></div>", unsafe_allow_html=True)
    st.subheader("Investment Groups")
    st.caption(
        "Six directional outcomes use explicit peer-relative gates and preserve all three signals; "
        "they are not a blended score. Missing evidence remains a separate publication gate. "
        "Language-history confidence is shown separately."
    )
    group_columns = st.columns(3, gap="medium")
    for index, group_name in enumerate(GROUP_ORDER):
        members = sorted(row["Ticker"] for row in plotted_rows if row["Investment group"] == group_name)
        meta = GROUP_META[group_name]
        with group_columns[index % 3].container(border=True):
            st.markdown(
                f"<div class='prism-group' style='--group-color:{meta['color']}'>"
                f"<div class='prism-group-name'>{group_name}</div>"
                f"<div class='prism-group-count'>{len(members)}</div>"
                f"<div class='prism-muted'>{meta['meaning']}</div>"
                f"<div style='margin-top:.55rem'>{' · '.join(members) if members else 'No bank currently assigned'}</div>"
                "</div>",
                unsafe_allow_html=True,
            )

    with st.expander("Bank-level group assignments"):
        st.dataframe(
            [
                {
                    "Group": row["Investment group"],
                    "Ticker": row["Ticker"],
                    "Bank": row["Bank"],
                    "Numeric": row["Numeric score"],
                    "Language": row["Language score"],
                    "Market": row["Market confirmation"],
                    "Evidence": row["Evidence status"],
                }
                for row in sorted(plotted_rows, key=lambda item: (GROUP_ORDER.index(item["Investment group"]), item["Ticker"]))
            ],
            width="stretch",
            hide_index=True,
            column_config={
                "Numeric": st.column_config.NumberColumn(format="%.1f"),
                "Language": st.column_config.NumberColumn(format="%.1f"),
                "Market": st.column_config.NumberColumn(format="%.1f"),
            },
        )
else:
    st.info("Complete three-signal coverage is not yet available.")
st.caption(
    "Market confirmation is encoded only by bubble size, so disagreement remains visible without distorting either axis. "
    "A future market-expectations axis will require consistent consensus-estimate data."
)

st.markdown("<div id='research-triage' class='prism-kicker'>03 · Research triage</div><div class='prism-rule'></div>", unsafe_allow_html=True)
st.subheader("Opportunities and risk queue")
st.caption("A prioritisation view for deeper research—not an investment recommendation.")
opportunity_groups = {"Conviction Leaders", "Re-rating Candidates", "Contrarian Value"}
opportunities = sorted(
    (row for row in plotted_rows if row["Investment group"] in opportunity_groups),
    key=lambda row: (row["Numeric score"] + row["Language score"], row["Market confirmation"]),
    reverse=True,
)
risk_groups = {"Downside Risk", "Expectations-led Momentum"}
risks = sorted(
    (row for row in plotted_rows if row["Investment group"] in risk_groups),
    key=lambda row: (
        row["Investment group"] == "Downside Risk",
        100 - row["Numeric score"],
        abs(row["Gap"]),
    ),
    reverse=True,
)[:6]
left_queue, right_queue = st.columns(2, gap="large")
with left_queue:
    st.markdown("#### Research opportunities")
    if opportunities:
        for row in opportunities:
            with st.container(border=True):
                st.markdown(f"**{row['Ticker']} · {row['Bank']}**")
                st.caption(
                    f"{row['Investment group']} · Numeric {row['Numeric score']:.1f} · "
                    f"Language {row['Language score']:.1f} · Market {row['Market confirmation']:.1f}"
                )
                st.write(GROUP_META[row["Investment group"]]["meaning"])
    else:
        st.info("No bank currently clears the opportunity gates.")
with right_queue:
    st.markdown("#### Risk / verification queue")
    for row in risks:
        with st.container(border=True):
            st.markdown(f"**{row['Ticker']} · {row['Bank']}**")
            st.caption(
                f"{row['Investment group']} · Numeric {row['Numeric score']:.1f} · "
                f"Language {row['Language score']:.1f} · Gap {row['Gap']:+.1f}"
            )
            st.write(GROUP_META[row["Investment group"]]["meaning"])

st.markdown("<div id='full-peer-ranking' class='prism-kicker'>04 · Full peer ranking</div><div class='prism-rule'></div>", unsafe_allow_html=True)
st.subheader("Relative ranking")
st.caption(
    f"Coverage: {len(scored_tickers)}/{len(universe)} banks · all rows are shown · "
    "fundamental score remains separate from the language and market overlays"
)
render_ranking_table(ranking_rows, key="homepage_ranking")
st.warning("A higher score indicates stronger relative inputs under this methodology; it is not a buy or sell recommendation.")

st.markdown("<div id='quick-diagnostic' class='prism-kicker'>05 · Quick diagnostic</div><div class='prism-rule'></div>", unsafe_allow_html=True)
st.subheader("One-bank research snapshot")
quick_ticker = st.selectbox(
    "Select a bank",
    [row["ticker"] for row in universe],
    key="homepage_bank_diagnostic",
)
quick_bank = banks[quick_ticker]
quick_score = next((row for row in scores if row["ticker"] == quick_ticker), {"score": None})
quick_signal = next((row for row in plotted_rows if row["Ticker"] == quick_ticker), None)
quick_metrics = quick_bank.get("metrics", {})
st.markdown(f"#### {quick_bank['bank_name']} ({quick_ticker})")
quick_cols = st.columns(7)
quick_cols[0].metric("Fundamental score", decimal(quick_score.get("score")), border=True)
quick_cols[1].metric("P/B", multiple(quick_metrics.get("price_to_book")), border=True)
quick_cols[2].metric("P/E", multiple(quick_metrics.get("price_to_earnings")), border=True)
quick_cols[3].metric("ROE", percent(quick_metrics.get("return_on_equity")), border=True)
quick_cols[4].metric("Dividend yield", percent(quick_metrics.get("dividend_yield")), border=True)
quick_cols[5].metric("Language", decimal(quick_signal.get("Language score") if quick_signal else None), border=True)
quick_cols[6].metric("Market", decimal(quick_signal.get("Market confirmation") if quick_signal else None), border=True)
if quick_signal:
    st.info(
        f"{quick_signal['Investment group']}: {GROUP_META[quick_signal['Investment group']]['meaning']} "
        f"Evidence status: {quick_signal['Evidence status']}."
    )

st.markdown("<div id='evidence-readiness' class='prism-kicker'>06 · Evidence readiness</div><div class='prism-rule'></div>", unsafe_allow_html=True)
st.subheader("Language drift and governance gate")
evidence_cols = st.columns(5)
evidence_cols[0].metric("Language coverage", f"{language_coverage.get('provisional_banks', 0)}/{len(universe)}", border=True)
evidence_cols[1].metric("Market coverage", f"{market_coverage}/{len(universe)}", border=True)
evidence_cols[2].metric("Table sources", table_evidence.get("source_count", 0), border=True)
evidence_cols[3].metric("Extracted tables", table_evidence.get("table_count", 0), border=True)
evidence_cols[4].metric("Backtested signals", 0, border=True)
st.warning(
    "Four comparable quarterly reports support preliminary linguistic-drift screening. "
    "Signals remain provisional until citations are reviewed and predictive value is backtested."
)

st.markdown("<div id='research-workbench' class='prism-kicker'>07 · Research workbench</div><div class='prism-rule'></div>", unsafe_allow_html=True)
st.caption("Use the tabs below for detailed diagnostics, source links, and methodology.")

ranking_tab, signals_tab, details_tab, evidence_tab, methodology_tab = st.tabs(
    ["Relative ranking", "Signals", "Bank details", "Evidence", "Methodology"]
)

with ranking_tab:
    st.subheader("Relative ranking")
    if observed:
        (st.error if data_age > 3 else st.info)(
            f"Provider data retrieved: {observed} ({data_age} day(s) old)."
            + (" Refresh before analysis." if data_age > 3 else "")
        )
    st.caption(
        f"Coverage: {len(scored_tickers)}/{len(universe)} banks ranked · "
        f"{language_coverage.get('provisional_banks', 0)}/{len(universe)} banks with provisional language signals"
    )
    render_ranking_table(ranking_rows, key="workbench_ranking")
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
        st.info("No bank currently has complete three-signal evidence.")

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
    st.markdown("**Market-confirmation bubble size:** 1-month (20%), 3-month (35%), and 6-month (35%) return plus price versus the 200-day average (10%) are peer-percentiled separately. The result controls only bubble size, so disagreement stays visible and never alters either axis or the fundamental score.")
    st.markdown(
        "**Investment-value groups:** deterministic gates classify the three visible signals without averaging them. "
        "Conviction Leaders clear 55 on every axis. Re-rating Candidates have fundamentals ≥55 and language ≥50 while market confirmation remains below 55. "
        "Contrarian Value combines fundamentals ≥50 with language below 50. Expectations-led Momentum requires market confirmation ≥60 while fundamentals remain below 55. "
        "Downside Risk combines fundamentals below 50 with at least one confirming warning from language or market confirmation below 50. Remaining mid-pack combinations are No Clear Edge. "
        "Missing signals are handled by the separate Insufficient Evidence gate."
    )
    st.markdown("**Controls:** common reporting dates, source evidence, freshness checks, sensitivity analysis, and publication gate.")
    st.markdown("**Scope:** this is a research screening tool, not personalized investment advice.")
    report_path = BASE_DIR / "pilot_report.md"
    if report_path.exists():
        st.download_button("Download analyst report", report_path.read_text(encoding="utf-8"), "pilot_report.md", "text/markdown")
