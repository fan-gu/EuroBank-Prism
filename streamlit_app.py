"""User-facing Streamlit dashboard for all 23 EURO STOXX Banks constituents."""

from pathlib import Path
from datetime import date, datetime
import base64
import importlib
import json
import os
import subprocess
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from app import dashboard_visuals as dashboard_visuals_module
from app import investment_groups as investment_groups_module
from app import language_signals as language_signals_module
from app import semantic_search as semantic_search_module

# Streamlit Cloud can hot-rerun this entry point without restarting imported
# modules. Reload the small deterministic helpers before binding their symbols
# so a newly added function is never requested from a stale in-memory module.
dashboard_visuals_module = importlib.reload(dashboard_visuals_module)
investment_groups_module = importlib.reload(investment_groups_module)
language_signals_module = importlib.reload(language_signals_module)
semantic_search_module = importlib.reload(semantic_search_module)
layout_signal_labels = dashboard_visuals_module.layout_signal_labels
market_bubble_diameter = dashboard_visuals_module.market_bubble_diameter
padded_domain = dashboard_visuals_module.padded_domain
signal_logo_layout = dashboard_visuals_module.signal_logo_layout
GROUP_META = investment_groups_module.GROUP_META
GROUP_ORDER = investment_groups_module.GROUP_ORDER
evidence_status = investment_groups_module.evidence_status
investment_group = investment_groups_module.investment_group
derive_group_thresholds = investment_groups_module.derive_group_thresholds
comparable_history = language_signals_module.comparable_history
period_sort_key = language_signals_module.period_sort_key
SemanticIndex = semantic_search_module.SemanticIndex
answer_semantic_question = semantic_search_module.answer_question
create_gemini_client = semantic_search_module.create_client

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent
LOGO_DIR = BASE_DIR / "assets" / "bank_logos"
SEMANTIC_FILES = (
    BASE_DIR / "semantic_corpus.json",
    BASE_DIR / "semantic_embeddings.npz",
    BASE_DIR / "semantic_index_metadata.json",
)


def bank_logo_uri(ticker):
    """Return a local bank logo as an embeddable data URI."""
    logo_path = LOGO_DIR / f"{ticker}.png"
    if not logo_path.exists():
        return None
    encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


BANK_LOGOS = {
    path.stem: bank_logo_uri(path.stem)
    for path in LOGO_DIR.glob("*.png")
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


def semantic_index_version():
    """Fingerprint the offline index so Streamlit reloads only when it changes."""
    if not all(path.exists() for path in SEMANTIC_FILES):
        return None
    return tuple((path.name, path.stat().st_size, path.stat().st_mtime_ns) for path in SEMANTIC_FILES)


@st.cache_resource(max_entries=2)
def load_semantic_index(index_version):
    del index_version
    return SemanticIndex.load(*SEMANTIC_FILES)


@st.cache_resource(max_entries=4)
def gemini_client(api_key):
    return create_gemini_client(api_key)


def configured_gemini_api_key():
    """Read cloud secrets first and fall back to the local environment."""
    try:
        key = st.secrets.get("GEMINI_API_KEY")
    except (FileNotFoundError, KeyError):
        key = None
    return key or os.getenv("GEMINI_API_KEY", "")


def percent(value):
    return f"{value:.1%}" if isinstance(value, (int, float)) else "Not available"


def multiple(value):
    return f"{value:.2f}x" if isinstance(value, (int, float)) else "Not available"


def decimal(value):
    return f"{value:.2f}" if isinstance(value, (int, float)) else "Not available"


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
        logo = BANK_LOGOS.get(row["Ticker"])
        if logo:
            logo_layout = signal_logo_layout(
                row,
                x_domain,
                y_domain,
                width=1_150,
                height=385,
            )
            if logo_layout["placement"] == "outside":
                figure.add_shape(
                    type="line",
                    x0=row["Language score"], y0=row["Numeric score"],
                    x1=logo_layout["x"], y1=logo_layout["y"],
                    line={"color": "rgba(210,220,235,0.38)", "width": 1},
                )
            figure.add_layout_image(
                source=logo,
                x=logo_layout["x"],
                y=logo_layout["y"],
                xref="x",
                yref="y",
                xanchor="center",
                yanchor="middle",
                sizex=logo_layout["sizex"],
                sizey=logo_layout["sizey"],
                sizing="contain",
                opacity=0.96,
                layer="above",
            )
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
        "Language alerts": row.get("alerts", []),
        "Language warning evidence": row.get("warning_evidence", []),
        "Language drift": row.get("language_drift_score"),
        "Directional reversal": row.get("directional_reversal"),
    }
    for row in signal_rows
    if row.get("numeric_score") is not None
    and row.get("language_score") is not None
    and market_by_ticker.get(row["ticker"], {}).get(
        "price_confirmation_score",
        market_by_ticker.get(row["ticker"], {}).get("market_confirmation_score"),
    ) is not None
]

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
    .prism-group {border-left:4px solid var(--group-color);padding:.15rem .5rem;min-height:8rem;}
    .prism-group-name {font-weight:700;font-size:1rem;text-align:center;margin-bottom:.4rem;}
    .prism-signal-line {display:flex;flex-direction:column;font-size:.78rem;line-height:1.5;margin-bottom:.5rem;}
    .prism-bank-list {display:flex;gap:.35rem;flex-wrap:wrap;justify-content:center;}
    .prism-bank-token {display:inline-flex;align-items:center;gap:.25rem;font-size:.7rem;font-weight:700;}
    .prism-bank-logo {width:1.2rem;height:1.2rem;object-fit:contain;background:white;border-radius:50%;}
    .prism-nav a {display:block;color:#aeb8c7;text-decoration:none;padding:.31rem .2rem;border-left:2px solid #28364b;padding-left:.75rem;font-size:.91rem;}
    .prism-nav a:hover {color:#f4f6fb;border-left-color:#4fa3ff;}
    .prism-nav a.active {color:#ffffff;border-left-color:#4fa3ff;background:linear-gradient(90deg,#4fa3ff18,transparent);font-weight:700;}
    .prism-legend {display:flex;gap:.3rem;align-items:center;flex-wrap:wrap;margin:.2rem 0 .42rem;padding-bottom:.1rem;}
    .prism-chip {display:inline-flex;align-items:center;gap:.3rem;border:1px solid #2c3545;border-radius:999px;padding:.2rem .42rem;color:#dce3ee;font-size:.70rem;white-space:nowrap;}
    .prism-dot {width:.62rem;height:.62rem;border-radius:50%;display:inline-block;}
    div[data-testid="stDataFrame"] {font-size:.70rem;}
    div[data-testid="stDataFrame"] * {font-size:.70rem;}
    section[data-testid="stSidebar"] h2 {font-size:2.72rem;line-height:.98;margin-bottom:.16rem;letter-spacing:-.05em;white-space:nowrap;}
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {overflow-y:hidden !important;}
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.32rem;}
    section[data-testid="stMain"] h2,
    section[data-testid="stMain"] h3,
    section[data-testid="stMain"] h4 {font-family:inherit;font-size:1.5rem;font-weight:700;text-align:center;letter-spacing:-.02em;}
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
          <a href="#research-triage">Research triage</a>
          <a href="#semantic-research">Semantic research</a>
          <a href="#bank-research">Bank research</a>
          <a href="#sources-evidence">Sources &amp; evidence</a>
          <a href="#methodology">Methodology</a>
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
st.header("Signal map")
if plotted_rows:
    st.plotly_chart(
        build_signal_map(plotted_rows),
        width="stretch",
        height=430,
        key="front_page_signal_map",
        config={"displaylogo": False, "scrollZoom": True},
    )
    group_columns = st.columns(3, gap="medium")
    for index, group_name in enumerate(GROUP_ORDER):
        meta = GROUP_META[group_name]
        members = sorted(row["Ticker"] for row in plotted_rows if row["Investment group"] == group_name)
        member_tokens = "".join(
            f"<span class='prism-bank-token'><img class='prism-bank-logo' src='{BANK_LOGOS.get(ticker, '')}' alt=''>{ticker}</span>"
            for ticker in members
        )
        signal_lines = "".join(f"<span>{line}</span>" for line in meta["signals"])
        with group_columns[index % 3].container(border=True):
            st.markdown(
                f"<div class='prism-group' style='--group-color:{meta['color']}'>"
                f"<div class='prism-group-name'>{group_name} · {len(members)}</div>"
                f"<div class='prism-signal-line'>{signal_lines}</div>"
                f"<div class='prism-bank-list'>{member_tokens or 'No bank assigned'}</div></div>",
                unsafe_allow_html=True,
            )

else:
    st.info("Complete three-signal coverage is not yet available.")

st.markdown("<div id='research-triage'></div>", unsafe_allow_html=True)
st.header("Research triage")
st.caption(
    "Full queue, sorted by absolute fundamentals-versus-language gap. "
    "A large gap is a research prompt, not a trading signal."
)
opportunity_groups = {"Conviction Leaders", "Strong Signals, Weak Price", "Cautious Value"}
left_queue, right_queue = st.columns(2, gap="large")
for column, title, is_opportunity in (
    (left_queue, "Research opportunities", True),
    (right_queue, "Risk / verification queue", False),
):
    queue = sorted(
        (row for row in plotted_rows if (row["Investment group"] in opportunity_groups) == is_opportunity),
        key=lambda row: abs(row["Gap"]), reverse=True,
    )
    with column:
        st.subheader(title)
        for row in queue:
            with st.container(border=True):
                st.markdown(f"**{row['Ticker']}** · {row['Investment group']} · Gap **{row['Gap']:+.1f}**")
        if not queue:
            st.caption("No banks currently in this queue.")

language_warning_rows = sorted(
    (row for row in plotted_rows if row["Language alerts"]),
    key=lambda row: (len(row["Language alerts"]), row["Negative pressure"] or 0),
    reverse=True,
)
st.markdown("#### Management-language warnings")
st.caption(
    "Every triggered language warning is listed here independently of its investment group. "
    "All remain review items, not trading signals."
)
if not language_warning_rows:
    st.success("No management-language warning crossed the current peer-relative review gates.")
else:
    language_documents_by_ticker = {
        ticker: sorted(
            (
                document for document in language_signals.get("documents", [])
                if document["ticker"] == ticker
            ),
            key=lambda document: period_sort_key(document["period"]),
        )
        for ticker in (row["Ticker"] for row in language_warning_rows)
    }
    for row in language_warning_rows:
        documents = language_documents_by_ticker.get(row["Ticker"], [])
        latest_document = documents[-1] if documents else {}
        with st.container(border=True):
            st.markdown(f"**{row['Ticker']} · {row['Bank']}**")
            for alert in row["Language alerts"]:
                st.markdown(f"- ⚠️ {alert['message']}")
            if row["Language warning evidence"]:
                with st.expander("Review cited management wording"):
                    for item in row["Language warning evidence"]:
                        st.markdown(
                            f"**Page {item['page']}** — {item['sentence']}"
                        )
                    if latest_document.get("source_url"):
                        st.link_button(
                            "Open official source",
                            latest_document["source_url"],
                            icon=":material/open_in_new:",
                        )

st.markdown("<div id='semantic-research'></div>", unsafe_allow_html=True)
st.header("Semantic research")
st.caption(
    "Ask across the filtered official-report archive. Gemini retrieves and explains cited evidence; it cannot change any Prism score."
)
semantic_version = semantic_index_version()
if semantic_version is None:
    st.info(
        "The semantic index is not deployed yet. Run `python build_semantic_index.py` and redeploy the generated artifacts."
    )
else:
    with st.form("semantic_research_form", border=False):
        semantic_question = st.text_input(
            "Research question",
            placeholder="Which banks sound cautious about net interest income, and why?",
            key="semantic_question",
        )
        semantic_scope = st.selectbox(
            "Bank scope",
            ["All 23 banks"] + [row["ticker"] for row in universe],
            key="semantic_scope",
        )
        semantic_submitted = st.form_submit_button(
            "Search official reports",
            icon=":material/search:",
        )

    if semantic_submitted:
        if not semantic_question.strip():
            st.warning("Enter a research question first.")
        else:
            api_key = configured_gemini_api_key()
            if not api_key:
                st.warning(
                    "Gemini is not configured. Add `GEMINI_API_KEY` to Streamlit Secrets or the local `.env` file."
                )
            else:
                try:
                    with st.spinner("Searching official reports and grounding the answer..."):
                        semantic_index = load_semantic_index(semantic_version)
                        semantic_results = semantic_index.search(
                            gemini_client(api_key),
                            semantic_question[:500],
                            top_k=6,
                            tickers=(
                                None
                                if semantic_scope == "All 23 banks"
                                else {semantic_scope}
                            ),
                        )
                        semantic_answer = answer_semantic_question(
                            gemini_client(api_key),
                            semantic_question[:500],
                            semantic_results,
                        )
                    st.markdown("#### Evidence-grounded answer")
                    st.markdown(semantic_answer)
                    st.markdown("#### Retrieved evidence")
                    for evidence_number, result in enumerate(semantic_results, start=1):
                        row = result.record
                        with st.expander(
                            f"E{evidence_number} · {row['ticker']} · {row['period']} · page {row['page']} · similarity {result.score:.3f}",
                            icon=":material/description:",
                        ):
                            st.write(row["text"])
                            source_url = row.get("source_url") or row.get("official_page")
                            if source_url:
                                st.link_button(
                                    "Open official report",
                                    source_url,
                                    icon=":material/open_in_new:",
                                )
                except Exception as exc:
                    st.error(
                        f"Semantic request failed ({type(exc).__name__}). Check the Gemini key, quota and model availability."
                    )

boilerplate_pages = sum(
    document.get("excluded_boilerplate_pages", 0)
    for document in language_signals.get("documents", [])
)
boilerplate_passages = sum(
    document.get("excluded_boilerplate_passages", 0)
    for document in language_signals.get("documents", [])
)
pollution_totals = {
    "risk": sum(document.get("masked_neutral_risk_spans", 0) for document in language_signals.get("documents", [])),
    "duplicates": sum(document.get("deduplicated_repeats", 0) for document in language_signals.get("documents", [])),
    "negation": sum(document.get("negated_hits_dropped", 0) for document in language_signals.get("documents", [])),
    "prior": sum(document.get("excluded_prior_period_passages", 0) for document in language_signals.get("documents", [])),
    "procedural": sum(document.get("excluded_procedural_condition_passages", 0) for document in language_signals.get("documents", [])),
    "procedural_spans": sum(document.get("masked_procedural_condition_spans", 0) for document in language_signals.get("documents", [])),
    "standardized": sum(document.get("excluded_standardized_footnote_passages", 0) for document in language_signals.get("documents", [])),
    "standardized_spans": sum(document.get("masked_standardized_footnote_spans", 0) for document in language_signals.get("documents", [])),
}
details_section = st.container()
evidence_section = st.container()
methodology_section = st.container()

with details_section:
    st.markdown("<div id='bank-research'></div>", unsafe_allow_html=True)
    st.header("Bank research")
    selected = st.selectbox("Select a bank", [row["ticker"] for row in universe])
    bank = banks[selected]
    score = next((row for row in scores if row["ticker"] == selected), {"score": None, "components": {}})
    st.subheader(f"{bank['bank_name']} ({selected})")
    st.write(f"Country: **{bank['country']}** · market ticker: **{bank['market_ticker']}**")
    metrics = bank.get("metrics", {})
    prudential = bank.get("prudential_metrics", {})
    market = market_by_ticker.get(selected, {})
    cols = st.columns(3)
    cols[0].metric("Screening score", score["score"] if score["score"] is not None else "N/A")
    cols[1].metric("Share price", f"{metrics.get('price'):.2f}" if metrics.get("price") else "N/A")
    price_confirmation = market.get("price_confirmation_score", market.get("market_confirmation_score"))
    cols[2].metric("Price confirmation", price_confirmation if price_confirmation is not None else "N/A")
    st.markdown(f"**Verified prudential overlay:** CET1 {percent(prudential.get('cet1_ratio'))} · RoTE {percent(prudential.get('rote'))}")
    st.markdown("#### Score contribution")
    st.dataframe([
        {"Metric": metric.replace("_", " ").title(), "Raw value": detail["raw_value"], "Percentile score": detail["percentile_score"], "Weight": f"{detail['weight']:.0%}"}
        for metric, detail in score.get("components", {}).items()
    ], width="stretch", hide_index=True)
    with st.expander("Additional equity-research metrics", icon=":material/analytics:"):
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
    bank_language_documents = [
        document for document in language_signals.get("documents", []) if document["ticker"] == selected
    ]
    bank_language_documents.sort(key=lambda document: period_sort_key(document["period"]))
    continuous_language_documents = comparable_history(bank_language_documents)
    st.markdown("#### Management-language history")
    if len(continuous_language_documents) < 4:
        st.info(
            f"{len(bank_language_documents)} report(s) are archived, but only "
            f"{len(continuous_language_documents)} form the latest uninterrupted comparable sequence. "
            "Four are needed for a preliminary trend."
        )
    else:
        history_frame = pd.DataFrame(
            {
                "Period": [document["period"] for document in continuous_language_documents[-4:]],
                "Absolute language score": [document["features"]["absolute_language_score"] for document in continuous_language_documents[-4:]],
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
            st.caption(
                "v2.4.3 filter audit · "
                f"{latest_language_document.get('masked_neutral_risk_spans', 0)} neutral risk labels · "
                f"{latest_language_document.get('deduplicated_repeats', 0)} repeats · "
                f"{latest_language_document.get('negated_hits_dropped', 0)} negated hits · "
                f"{latest_language_document.get('excluded_prior_period_passages', 0)} technical prior-period passages · "
                f"{latest_language_document.get('excluded_procedural_condition_passages', 0)} routine procedural footnotes · "
                f"{latest_language_document.get('excluded_standardized_footnote_passages', 0)} calculation footnotes"
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

with evidence_section:
    st.markdown("<div id='sources-evidence'></div>", unsafe_allow_html=True)
    with st.expander(
        "Official report directory · 23 banks",
        icon=":material/menu_book:",
    ):
        st.caption("Official issuer links for the latest annual and quarterly / interim reporting.")
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
            height=610,
            row_height=24,
            column_config={
                "Annual report": st.column_config.LinkColumn("Latest annual report", display_text="Open annual reports"),
                "Quarterly / interim": st.column_config.LinkColumn("Latest quarterly / interim", display_text="Open results"),
            },
        )

with methodology_section:
    st.markdown("<div id='methodology'></div>", unsafe_allow_html=True)
    with st.expander("Methodology and research limits", icon=":material/info:"):
        st.markdown("#### Scoring")
        st.write(
            "The numeric score peer-ranks P/B, P/E, profitability, yield and growth. "
            "Period-aligned prudential metrics are an evidence overlay; the selected bank's component weights are shown above."
        )
        st.markdown("#### Filters")
        st.write(
            "Management language is independently calibrated against the 23-bank cohort. "
            "v2.4.3 removes legal boilerplate, routine approval conditions, standardized rounding notes, technical prior-period notes and duplicate text. "
            f"Current audit: {boilerplate_pages} boilerplate page(s), {boilerplate_passages} boilerplate passage(s), "
            f"{pollution_totals['procedural']} procedural footnote(s), and {pollution_totals['standardized']} rounding footnote(s) excluded."
        )
        st.markdown("#### Gates")
        st.write(
            "Groups use each axis's own peer distribution. Four adjacent comparable reports enable an early language trend; "
            "eight periods, cited review and an out-of-sample backtest are required before drift becomes validated research. "
            "Semantic answers use only retrieved, page-cited report excerpts and never alter scores or groups."
        )
        st.markdown("#### Scope")
        st.write(
            "EuroBank Prism is an educational research screen, not personalised investment advice. "
            "Verify every observation against its official source before making an investment decision."
        )
st.html(
    """
    <script>
    (() => {
      const sectionIds = [
        "core-signal-map",
        "research-triage",
        "semantic-research",
        "bank-research",
        "sources-evidence",
        "methodology"
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
