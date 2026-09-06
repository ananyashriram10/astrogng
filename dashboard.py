from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from exoplanet_lab.cache import ResultCache
from exoplanet_lab.service import ArchiveAnalysisOptions, analyze_archive_target


st.set_page_config(
    page_title="Exoplanet Transit Lab",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(145deg, #07111f 0%, #0a1628 52%, #101936 100%); }
    [data-testid="stSidebar"] { background: #07101d; border-right: 1px solid #20304b; }
    [data-testid="stMetric"] {
        background: rgba(15, 31, 52, .78); border: 1px solid #29405f;
        border-radius: 14px; padding: 14px 18px;
    }
    .eyebrow { color: #65d9ff; letter-spacing: .16em; font-size: .75rem; font-weight: 700; }
    .hero { font-size: clamp(2rem, 5vw, 4.4rem); line-height: .98; font-weight: 750;
            letter-spacing: -.045em; margin: .25rem 0 1rem; }
    .lede { color: #aebed3; max-width: 720px; font-size: 1.04rem; }
    .candidate-card { background: rgba(14, 29, 49, .76); border: 1px solid #29405f;
                      border-radius: 16px; padding: 18px; margin: 12px 0; }
    .planet-like { color: #61e4bd; font-weight: 700; }
    .likely-false-positive { color: #ff9b7b; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_target(name: str):
    result = ResultCache().load(name)
    if result is None:
        raise ValueError(f"Unknown demo target: {name}")
    return result


def light_curve_figure(time, flux, title: str, color: str) -> go.Figure:
    figure = go.Figure(
        go.Scattergl(
            x=time,
            y=flux,
            mode="markers",
            marker={"size": 2.8, "color": color, "opacity": 0.72},
            hovertemplate="Day %{x:.3f}<br>Flux %{y:.6f}<extra></extra>",
        )
    )
    figure.update_layout(
        title=title,
        xaxis_title="Time (days)",
        yaxis_title="Normalized flux",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,14,27,.6)",
        margin={"l": 48, "r": 18, "t": 58, "b": 45},
        height=390,
    )
    return figure


def folded_figure(candidate) -> go.Figure:
    figure = go.Figure(
        go.Scatter(
            x=candidate.phase,
            y=candidate.folded_flux,
            mode="markers",
            marker={
                "size": 5,
                "color": candidate.phase,
                "colorscale": [[0, "#7467f0"], [1, "#42d8c3"]],
                "opacity": 0.85,
            },
            hovertemplate="Phase %{x:.4f}<br>Flux %{y:.6f}<extra></extra>",
        )
    )
    width = candidate.duration_hours / 24 / candidate.period_days / 2
    figure.add_vrect(
        x0=-width,
        x1=width,
        fillcolor="#61e4bd",
        opacity=0.12,
        line_width=0,
        annotation_text="transit window",
        annotation_position="top left",
    )
    figure.update_layout(
        xaxis_title="Orbital phase",
        yaxis_title="Normalized flux",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,14,27,.6)",
        margin={"l": 48, "r": 18, "t": 35, "b": 45},
        height=330,
    )
    return figure


cache = ResultCache()
available = cache.list_targets()
names = [item["target"] for item in available]

with st.sidebar:
    st.markdown("### ✦ Transit Lab")
    st.caption("ANALYSIS CONTROL PANEL")
    source_mode = st.radio("Data source", ["Offline demo", "Real MAST light curve"], index=0)
    selected = st.selectbox("Stellar target", names)
    archive_result = None
    if source_mode == "Real MAST light curve":
        st.caption("Enter a KOI (e.g. K00752.01), KIC ID, or a resolvable target name.")
        real_target = st.text_input("MAST target", placeholder="KIC 11904151")
        mission = st.selectbox("Mission", ["Kepler", "TESS"], index=0)
        max_files = st.slider("Products to stitch", min_value=1, max_value=15, value=4)
        use_period_hint = st.checkbox(
            "Use NASA KOI period hint (confirmation mode)",
            value=True,
            help="Narrows the search around the catalog period when the input is a KOI. Uncheck for blind discovery.",
        )
        if st.button("Fetch + analyze", type="primary", use_container_width=True):
            if not real_target.strip():
                st.error("Enter a KOI, KIC, or object name first.")
            else:
                try:
                    with st.spinner("Resolving identifier, downloading MAST data, and searching transits…"):
                        st.session_state["archive_result"] = analyze_archive_target(
                            real_target,
                            ArchiveAnalysisOptions(
                                mission=mission,
                                max_files=max_files,
                                use_catalog_period_hint=use_period_hint,
                                require_trained_model=True,
                            ),
                        )
                except (RuntimeError, LookupError, ValueError, OSError) as exc:
                    st.error(str(exc))
        archive_result = st.session_state.get("archive_result")
    st.divider()
    st.markdown("**Pipeline**")
    st.caption("✓ Quality filtering")
    st.caption("✓ Robust detrending")
    st.caption("✓ Iterative BLS search")
    st.caption("✓ Candidate vetting")
    st.caption("✓ Confidence ranking")
    st.divider()
    st.info("Demo mode is offline. Real mode uses MAST via Lightkurve and the trained KOI model.")

result = archive_result if source_mode == "Real MAST light curve" and archive_result else load_target(selected)
st.markdown('<div class="eyebrow">EXOPLANET SIGNAL INTELLIGENCE</div>', unsafe_allow_html=True)
st.markdown(f'<div class="hero">Inside {result.target}</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="lede">Repeated shadows reveal worlds. Explore the cleaned light curve, '
    "phase-folded transit signatures, and the evidence behind each ranking.</div>",
    unsafe_allow_html=True,
)

metric_cols = st.columns(4)
metric_cols[0].metric("Signals found", len(result.candidates))
metric_cols[1].metric("Mission", result.mission)
metric_cols[2].metric("System", "Multi-planet" if result.is_multi_planet else "Single signal")
best = max((item.confidence for item in result.candidates), default=0)
metric_cols[3].metric("Top confidence", f"{best:.0%}")

raw_tab, clean_tab = st.tabs(["Raw light curve", "Detrended light curve"])
with raw_tab:
    st.plotly_chart(
        light_curve_figure(
            result.raw_light_curve.time, result.raw_light_curve.flux, "Observed flux", "#7189ff"
        ),
        use_container_width=True,
    )
with clean_tab:
    st.plotly_chart(
        light_curve_figure(
            result.detrended_light_curve.time,
            result.detrended_light_curve.flux,
            "Detrended flux",
            "#61e4bd",
        ),
        use_container_width=True,
    )

st.markdown("## Candidate signals")
st.caption("Each view stacks repeated events at the detected period. A coherent central dip is the key signature.")

for candidate in result.candidates:
    status_class = candidate.disposition.replace(" ", "-")
    st.markdown(
        f'<div class="candidate-card"><span class="{status_class}">{candidate.disposition.upper()}</span>'
        f"<h3>{candidate.candidate_id}</h3></div>",
        unsafe_allow_html=True,
    )
    details, chart = st.columns([1, 2.25], vertical_alignment="center")
    with details:
        st.metric("Confidence", f"{candidate.confidence:.0%}")
        left, right = st.columns(2)
        left.metric("Period", f"{candidate.period_days:.3f} d")
        right.metric("Duration", f"{candidate.duration_hours:.2f} h")
        left.metric("Depth", f"{candidate.depth_ppm:,.0f} ppm")
        right.metric("Observed", candidate.num_transits_observed)
        st.caption(f"SNR {candidate.snr:.1f} · symmetry {candidate.transit_shape_symmetry:.0%}")
    with chart:
        st.plotly_chart(folded_figure(candidate), use_container_width=True)

with st.expander("Data provenance and caveats"):
    st.write(result.source)
    for note in result.notes:
        st.write(f"• {note}")
