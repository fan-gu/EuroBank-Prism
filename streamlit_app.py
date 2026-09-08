"""User-facing Streamlit dashboard for all 23 EURO STOXX Banks constituents."""

from pathlib import Path
from datetime import date, datetime
import importlib
import json
import subprocess
import sys

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
derive_group_thresholds = investment_groups_module.derive_group_thresholds

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
def load_data(data_version):
    """Load dashboard files; data_version invalidates stale deployment caches."""
    del data_version
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


def data_version():
    """Fingerprint the small dashboard inputs without reading them twice."""
    names = (
        "full_universe_dataset.json", "full_universe_scores.json", "bank_master.json",
        "official_report_pages.json", "table_evidence_index.json",
        "language_signals.json", "market_confirmation.json",
    )
    return tuple(
        (name, (BASE_DIR / name).stat().st_size, (BASE_DIR / name).stat().st_mtime_ns)
        for name in names if (BASE_DIR / name).exists()
    )


def percent(value):
    return f"{value:.1%}" if isinstance(value, (int, float)) else "Not available"


def multiple(value):
    return f"{value:.2f}x" if isinstance(value, (int, float)) else "Not available"


def decimal(value):
    return f"{value:.2f}" if isinstance(value, (int, float)) else "Not available"


def build_ranking_rows(scores, banks):
    """Create the canonical ranking table for the waterfall homepage."""
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
        })
    return rows


def render_ranking_table(ranking_rows, *, key=None):
    """Render the full-universe table without an internal vertical scrollbar."""
    st.dataframe(
        ranking_rows,
        width="stretch",
        hide_index=True,
        height=610,
        row_height=24,
        key=key,
        column_config={
            "Rank": st.column_config.NumberColumn("#", width=42),
            "Flag": st.column_config.ImageColumn("", width=30),
            "Country": st.column_config.TextColumn("Country", width=54),
            "Bank": st.column_config.TextColumn("Bank", width=175),
            "Ticker": st.column_config.TextColumn("Ticker", width=62),
            "Index weight": st.column_config.NumberColumn("Index wt.", format="%.2f%%", width=70),
            "Current price": st.column_config.NumberColumn("Price", format="€%.2f", width=70),
            "P/E": st.column_config.NumberColumn("P/E", format="%.2fx", width=62),
            "P/B": st.column_config.NumberColumn("P/B", format="%.2fx", width=62),
            "ROE": st.column_config.NumberColumn("ROE", format="%.1f%%", width=62),
            "Div. yield": st.column_config.NumberColumn("Div. yield", format="%.1f%%", width=70),
            "Score": st.column_config.NumberColumn("Score", format="%.1f", width=58),
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
        height=385,
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
                "size": [market_bubble_diameter(row["Price confirmation"]) for row in group_rows],
                "sizemode": "diameter",
                "color": GROUP_META[group_name]["color"],
                "line": {"color": "#f4f6fb", "width": 1.4},
                "opacity": 0.86,
            },
            customdata=[
                [row["Bank"], row["Ticker"], row["Investment group"], row["Price regime"], row["Gap"], row["Evidence status"], row["Price confirmation"]]
                for row in group_rows
            ],
            hovertemplate=(
                "<b>%{customdata[0]} (%{customdata[1]})</b><br>"
                "Fundamentals & valuation: %{y:.1f}<br>Language: %{x:.1f}<br>"
                "Price confirmation: %{customdata[6]:.1f}<br>"
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
        height=430,
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

banks, scores, universe, report_pages, table_evidence, language_signals, market_confirmation = load_data(data_version())
scored_tickers = {row["ticker"] for row in scores if row["status"] == "ranked"}
language_coverage = language_signals.get("coverage", {})
market_by_ticker = {row["ticker"]: row for row in market_confirmation.get("records", [])}
market_coverage = sum(
    row.get("status") in {"market_confirmation_available", "price_confirmation_available"}
    for row in market_by_ticker.values()
)
signal_rows = language_signals.get("signals", [])
group_thresholds = derive_group_thresholds([
    {
        "numeric": row.get("numeric_score"),
        "language": row.get("language_score"),
        "price": market_by_ticker.get(row["ticker"], {}).get(
            "price_confirmation_score",
            market_by_ticker.get(row["ticker"], {}).get("market_confirmation_score"),
        ),
    }
    for row in signal_rows
])
plotted_rows = [
    {
        "Ticker": row["ticker"],
        "Bank": row["bank_name"],
        "Numeric score": row["numeric_score"],
        "Language score": row["language_score"],
        "Negative pressure": row.get("negative_pressure_score"),
        "Gap": row["divergence"],
        "Research quadrant": row["quadrant"],
        "Price confirmation": market_by_ticker.get(row["ticker"], {}).get(
            "price_confirmation_score",
            market_by_ticker.get(row["ticker"], {}).get("market_confirmation_score"),
        ),
        "Price regime": market_by_ticker.get(row["ticker"], {}).get(
            "price_regime",
            market_by_ticker.get(row["ticker"], {}).get("market_regime", "Insufficient history"),
        ),
        "Investment group": investment_group(
            row.get("numeric_score"),
            row.get("language_score"),
            market_by_ticker.get(row["ticker"], {}).get(
                "price_confirmation_score",
                market_by_ticker.get(row["ticker"], {}).get("market_confirmation_score"),
            ),
            group_thresholds,
        ),
        "Evidence status": evidence_status(row.get("history_periods")),
    }
    for row in signal_rows
    if row.get("numeric_score") is not None
    and row.get("language_score") is not None
    and market_by_ticker.get(row["ticker"], {}).get(
        "price_confirmation_score",
        market_by_ticker.get(row["ticker"], {}).get("market_confirmation_score"),
    ) is not None
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
    .prism-nav a.active {color:#ffffff;border-left-color:#4fa3ff;background:linear-gradient(90deg,#4fa3ff18,transparent);font-weight:700;}
    .prism-legend {display:flex;gap:.3rem;align-items:center;flex-wrap:wrap;margin:.2rem 0 .42rem;padding-bottom:.1rem;}
    .prism-chip {display:inline-flex;align-items:center;gap:.3rem;border:1px solid #2c3545;border-radius:999px;padding:.2rem .42rem;color:#dce3ee;font-size:.70rem;white-space:nowrap;}
    .prism-dot {width:.62rem;height:.62rem;border-radius:50%;display:inline-block;}
    .prism-badge {display:inline-block;margin-left:.28rem;padding:.05rem .24rem;border:1px solid #5d6b80;border-radius:4px;color:#9faec2;font-size:.52rem;font-weight:700;letter-spacing:.05em;vertical-align:middle;}
    div[data-testid="stDataFrame"] {font-size:.70rem;}
    div[data-testid="stDataFrame"] * {font-size:.70rem;}
    section[data-testid="stSidebar"] h2 {font-size:2.05rem;line-height:1.05;margin-bottom:.1rem;}
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {overflow-y:hidden !important;}
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.42rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## EuroBank Prism")
    st.caption("Three signals. One clearer view.")
    refresh_clicked = st.button(
        "Refresh data",
        width="stretch",
        icon=":material/refresh:",
        help="Fetch fresh provider metrics and price history. Official-report language history is curated separately.",
    )
    if data_age is None:
        st.caption("Provider snapshot unavailable")
    elif data_age > 3:
        st.caption(f"⚠ {observed} · {data_age} days old")
    else:
        st.caption(f"Data {observed} · current")
    st.markdown(
        """
        <div class="prism-nav">
          <a href="#core-signal-map">Signal map</a>
          <a href="#investment-groups">Investment groups</a>
          <a href="#research-triage">Research triage</a>
          <a href="#full-peer-ranking">Peer ranking</a>
          <a href="#research-readiness">Research readiness</a>
          <a href="#research-details">Research details</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
st.header("Signal Map")
if plotted_rows:
    legend_chips = "".join(
        f"<span class='prism-chip' title=\"{GROUP_META[group]['meaning']}\">"
        f"<span class='prism-dot' style='background:{GROUP_META[group]['color']}'></span>{group}<span class='prism-badge' title='Provisional'>P</span></span>"
        for group in GROUP_ORDER
    )
    st.markdown(f"<div class='prism-legend'>{legend_chips}</div>", unsafe_allow_html=True)
    st.plotly_chart(
        build_signal_map(plotted_rows),
        width="stretch",
        height=430,
        key="front_page_signal_map",
        config={"displaylogo": False, "scrollZoom": True},
    )

    st.markdown("<div id='investment-groups' class='prism-kicker'>02 · Investment groups</div><div class='prism-rule'></div>", unsafe_allow_html=True)
    st.subheader("Investment Groups")
    st.caption(
        "Six directional outcomes use axis-specific peer quantiles and preserve all three signals; "
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
                f"<div class='prism-group-name'>{group_name}<span class='prism-badge'>PROVISIONAL</span></div>"
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
                    "Price": row["Price confirmation"],
                    "Evidence": row["Evidence status"],
                }
                for row in sorted(plotted_rows, key=lambda item: (GROUP_ORDER.index(item["Investment group"]), item["Ticker"]))
            ],
            width="stretch",
            hide_index=True,
            column_config={
                "Numeric": st.column_config.NumberColumn(format="%.1f"),
                "Language": st.column_config.NumberColumn(format="%.1f"),
                "Price": st.column_config.NumberColumn(format="%.1f"),
            },
        )
else:
    st.info("Complete three-signal coverage is not yet available.")
st.caption(
    "Price confirmation is encoded only by bubble size, so disagreement remains visible without distorting either axis. "
    "A future market-expectations axis will require consistent consensus-estimate data."
)

st.markdown("<div id='research-triage' class='prism-kicker'>03 · Research triage</div><div class='prism-rule'></div>", unsafe_allow_html=True)
st.subheader("Opportunities and risk queue")
st.caption("A prioritisation view for deeper research—not an investment recommendation.")
opportunity_groups = {"Conviction Leaders", "Strong Signals, Weak Price", "Cautious Value"}
opportunities = sorted(
    (row for row in plotted_rows if row["Investment group"] in opportunity_groups),
    key=lambda row: (row["Numeric score"] + row["Language score"], row["Price confirmation"]),
    reverse=True,
)
risks = []
for group_name in ("Story Ahead of Numbers", "Downside Risk", "Price Ahead of Fundamentals"):
    group_queue = sorted(
        (row for row in plotted_rows if row["Investment group"] == group_name),
        key=lambda row: (
            abs(row["Gap"]),
            100 - row["Numeric score"],
            row["Price confirmation"],
        ),
        reverse=True,
    )
    risks.extend(group_queue[:2])
left_queue, right_queue = st.columns(2, gap="large")
with left_queue:
    st.markdown("#### Research opportunities")
    if opportunities:
        for row in opportunities:
            with st.container(border=True):
                st.markdown(f"**{row['Ticker']} · {row['Bank']}**")
                st.caption(
                    f"{row['Investment group']} · Numeric {row['Numeric score']:.1f} · "
                    f"Language {row['Language score']:.1f} · Price {row['Price confirmation']:.1f}"
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
    "fundamental score remains separate from the language and price overlays"
)
render_ranking_table(ranking_rows, key="homepage_ranking")
st.warning("A higher score indicates stronger relative inputs under this methodology; it is not a buy or sell recommendation.")

st.markdown("<div id='research-readiness' class='prism-kicker'>05 · Research readiness</div><div class='prism-rule'></div>", unsafe_allow_html=True)
st.subheader("Can these signals support research use?")
st.caption(
    "This gate checks whether the inputs are complete, period-comparable, source-linked and backtested. "
    "It is a confidence control—not another investment signal."
)
four_period_count = language_coverage.get("four_period_trends", 0)
with st.container(horizontal=True):
    st.metric("Current language coverage", f"{language_coverage.get('provisional_banks', 0)}/{len(universe)}", border=True)
    st.metric("Four-period language history", f"{four_period_count}/{len(universe)}", border=True)
    st.metric("Price-history coverage", f"{market_coverage}/{len(universe)}", border=True)
    st.metric("Backtested signals", 0, border=True)
st.caption(
    "Current status: preliminary screening only. Four comparable reports support an early drift view; "
    "eight periods, citation review and out-of-sample testing are required for a validated alert."
)

st.markdown("<div id='research-details' class='prism-kicker'>06 · Research details</div><div class='prism-rule'></div>", unsafe_allow_html=True)
st.caption("Open only the bank detail, source evidence or methodology needed for follow-up research.")

details_tab, evidence_tab, methodology_tab = st.tabs(
    ["Bank research", "Sources & evidence", "Methodology"]
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
    price_confirmation = market.get("price_confirmation_score", market.get("market_confirmation_score"))
    cols[6].metric("Price confirmation", price_confirmation if price_confirmation is not None else "N/A")
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
    if bank_language_documents:
        latest_language_document = bank_language_documents[-1]
        language_signal = next(
            (row for row in signal_rows if row["ticker"] == selected),
            {},
        )
        with st.expander(
            "Latest management-language evidence",
            icon=":material/format_quote:",
        ):
            st.caption(
                f"{latest_language_document['period']} · "
                f"Language {language_signal.get('language_score', 'N/A')} · "
                f"Negative pressure {language_signal.get('negative_pressure_score', 'N/A')} · "
                "human review pending"
            )
            for item in latest_language_document.get("evidence", [])[:5]:
                hit_labels = [
                    name.replace("_", " ")
                    for name, value in item.get("hits", {}).items()
                    if value
                ]
                st.markdown(
                    f"**Page {item['page']} · {', '.join(hit_labels) or 'guidance'}**  \n"
                    f"{item['sentence']}"
                )
            if latest_language_document.get("source_url"):
                st.link_button(
                    "Open official source",
                    latest_language_document["source_url"],
                    icon=":material/open_in_new:",
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
    st.markdown("**Price-confirmation bubble size:** 1-month (20%), 3-month (35%), and 6-month (35%) return plus price versus the 200-day average (10%) are peer-percentiled separately. This is backward-looking price behaviour—not analyst expectations. The result controls only bubble size and never alters either axis or the fundamental score.")
    st.markdown(
        "**Investment-value groups:** deterministic gates use each axis's own current cross-section rather than one shared raw cutoff. "
        f"Current gates — numeric median {group_thresholds['numeric_mid']:.1f}, numeric 60th percentile {group_thresholds['numeric_high']:.1f}; "
        f"language median {group_thresholds['language_mid']:.1f}, language 60th percentile {group_thresholds['language_high']:.1f}; "
        f"price 40th/50th/60th percentiles {group_thresholds['price_low']:.1f}/{group_thresholds['price_mid']:.1f}/{group_thresholds['price_high']:.1f}. "
        "Strong Signals, Weak Price identifies supportive fundamentals and language before price confirmation. Story Ahead of Numbers identifies language materially ahead of below-median fundamentals. "
        "Cautious Value requires at least a 40th-percentile price floor; otherwise the pattern is treated as downside/value-trap risk. Missing signals remain a separate evidence gate."
    )
    st.markdown("**Controls:** common reporting dates, source evidence, freshness checks, sensitivity analysis, and publication gate.")
    st.markdown("**Scope:** this is a research screening tool, not personalized investment advice.")
    report_path = BASE_DIR / "pilot_report.md"
    if report_path.exists():
        st.download_button("Download analyst report", report_path.read_text(encoding="utf-8"), "pilot_report.md", "text/markdown")

st.html(
    """
    <script>
    (() => {
      const sectionIds = [
        "core-signal-map",
        "investment-groups",
        "research-triage",
        "full-peer-ranking",
        "research-readiness",
        "research-details"
      ];
      const links = Array.from(document.querySelectorAll(".prism-nav a"));
      const sections = sectionIds
        .map((id) => document.getElementById(id))
        .filter(Boolean);
      if (!links.length || !sections.length) return;

      if (window.__prismScrollSpyCleanup) window.__prismScrollSpyCleanup();

      const updateActiveSection = () => {
        const marker = window.innerHeight * 0.30;
        let activeId = sections[0].id;
        for (const section of sections) {
          if (section.getBoundingClientRect().top <= marker) activeId = section.id;
        }
        for (const link of links) {
          link.classList.toggle(
            "active",
            link.getAttribute("href") === `#${activeId}`
          );
        }
      };

      document.addEventListener("scroll", updateActiveSection, true);
      window.addEventListener("resize", updateActiveSection);
      window.__prismScrollSpyCleanup = () => {
        document.removeEventListener("scroll", updateActiveSection, true);
        window.removeEventListener("resize", updateActiveSection);
      };
      requestAnimationFrame(updateActiveSection);
    })();
    </script>
    """,
    unsafe_allow_javascript=True,
)
