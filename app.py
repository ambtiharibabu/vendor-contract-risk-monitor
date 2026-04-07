# =============================================================
# app.py
# Vendor Contract Renewal Risk Monitor — Streamlit Dashboard
# Run with: streamlit run app.py
# =============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import io
from risk_engine import load_contracts, calculate_risk

# ------------------------------------------------------------------
# PAGE CONFIG — must be the very first Streamlit call in the file
# ------------------------------------------------------------------

st.set_page_config(
    page_title="Vendor Risk Monitor",
    page_icon="⚠️",
    layout="wide"          # uses full browser width instead of narrow centered column
)

# ------------------------------------------------------------------
# LOAD + ENRICH DATA
# ------------------------------------------------------------------

# st.cache_data tells Streamlit: "don't reload from disk on every interaction,
# reuse the result unless the underlying data changes" — keeps the app fast
@st.cache_data
def get_data():
    df = load_contracts()   # load_contracts now handles missing .db itself
    df = calculate_risk(df)
    return df

df = get_data()

# ------------------------------------------------------------------
# HEADER
# ------------------------------------------------------------------

st.title("⚠️ Vendor Contract Renewal Risk Monitor")
st.caption("Tracks contract expiration risk, vendor SLA performance, and renewal action priority.")
st.divider()

# ------------------------------------------------------------------
# SIDEBAR FILTERS
# ------------------------------------------------------------------

st.sidebar.header("🔍 Filters")

# Multi-select: user can pick one or more service types to drill down
service_filter = st.sidebar.multiselect(
    "Service Type",
    options=sorted(df["service_type"].unique()),
    default=sorted(df["service_type"].unique())    # all selected by default
)

region_filter = st.sidebar.multiselect(
    "Region",
    options=sorted(df["region"].unique()),
    default=sorted(df["region"].unique())
)

# Dropdown for risk tier — "All" means no filtering on tier
tier_filter = st.sidebar.selectbox(
    "Risk Tier",
    options=["All", "High", "Medium", "Low"]
)

window_filter = st.sidebar.selectbox(
    "Expiry Window",
    options=["All", "30 Days", "60 Days", "90 Days", "Expired", "OK"]
)

# -- Apply all filters to the dataframe --
filtered = df[
    df["service_type"].isin(service_filter) &
    df["region"].isin(region_filter)
]

if tier_filter != "All":
    filtered = filtered[filtered["risk_tier"] == tier_filter]

if window_filter != "All":
    filtered = filtered[filtered["expiry_window"] == window_filter]

# ------------------------------------------------------------------
# SECTION 1 — KPI CARDS
# ------------------------------------------------------------------

st.subheader("📊 Summary KPIs")

# st.columns(n) creates n side-by-side panels — like merged cells across a row in Excel
k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Total Contracts",     len(filtered))
k2.metric("Expiring in 30 Days", len(filtered[filtered["expiry_window"] == "30 Days"]))
k3.metric("Expiring in 60 Days", len(filtered[filtered["expiry_window"] == "60 Days"]))
k4.metric("Expiring in 90 Days", len(filtered[filtered["expiry_window"] == "90 Days"]))
k5.metric("Avg SLA Score",       f"{filtered['sla_score'].mean():.1f}")

st.divider()

# ------------------------------------------------------------------
# SECTION 2 — RISK ANALYTICS (charts)
# ------------------------------------------------------------------

st.subheader("📈 Risk Analytics")

chart_left, chart_right = st.columns(2)

# ---- Root Cause Tag Bar Chart ----
with chart_left:
    st.markdown("**Root Cause Tag Frequency**")

    # Each row can have multiple comma-separated tags — split and count individually
    tag_series = (
        filtered["root_cause_tags"]
        .str.split(", ")      # "SLA Breach, Data Issues" → ["SLA Breach", "Data Issues"]
        .explode()            # one tag per row so value_counts works correctly
        .value_counts()
        .reset_index()
    )
    tag_series.columns = ["Tag", "Count"]

    fig_bar = px.bar(
        tag_series,
        x="Count", y="Tag",
        orientation="h",               # horizontal — easier to read long tag names
        color="Count",
        color_continuous_scale="Reds", # darker bar = higher count = more urgent
        text="Count"
    )
    fig_bar.update_layout(
        showlegend=False,
        yaxis=dict(categoryorder="total ascending"),  # tallest bar at top
        margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ---- Risk Tier Pie Chart ----
with chart_right:
    st.markdown("**Risk Tier Distribution**")

    tier_counts = filtered["risk_tier"].value_counts().reset_index()
    tier_counts.columns = ["Tier", "Count"]

    fig_pie = px.pie(
        tier_counts,
        names="Tier",
        values="Count",
        color="Tier",
        color_discrete_map={"High": "#ff4d4d", "Medium": "#ff9900", "Low": "#28a745"}
    )
    fig_pie.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# ------------------------------------------------------------------
# SECTION 3 — CONTRACT EXPIRY TIMELINE (scatter)
# ------------------------------------------------------------------

st.subheader("📅 Contract Expiry Timeline")

fig_timeline = px.scatter(
    filtered,
    x="contract_end",
    y="risk_score",
    color="expiry_window",
    hover_data=["vendor_name", "service_type", "root_cause_tags"],  # tooltip on hover
    color_discrete_map={
        "30 Days": "#ff4d4d",
        "60 Days": "#ff9900",
        "90 Days": "#ffd700",
        "Expired": "#8b0000",
        "OK":      "#28a745"
    },
    labels={"contract_end": "Contract End Date", "risk_score": "Risk Score"}
)
fig_timeline.update_layout(margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig_timeline, use_container_width=True)

st.divider()

# ------------------------------------------------------------------
# SECTION 4 — VENDOR CONTRACT RISK TABLE
# ------------------------------------------------------------------

st.subheader("📋 Vendor Contract Risk Table")

# Only the columns an analyst needs — avoids overwhelming the view
display_cols = [
    "vendor_name", "service_type", "region",
    "contract_end", "days_to_expiry", "expiry_window",
    "sla_score", "data_issue_flags", "risk_score", "risk_tier", "root_cause_tags"
]

display_df = filtered[display_cols].copy()

# Highest risk + soonest expiry floats to the top
display_df = display_df.sort_values(
    by=["risk_score", "days_to_expiry"],
    ascending=[False, True]
)

# Returns a CSS color string for a given expiry window value
def color_window(val):
    colors = {
        "30 Days": "background-color: #ff4d4d; color: white;",
        "60 Days": "background-color: #ff9900; color: white;",
        "90 Days": "background-color: #ffd700; color: black;",
        "Expired": "background-color: #8b0000; color: white;",
        "OK":      "background-color: #28a745; color: white;",
    }
    return colors.get(val, "")

# Returns a CSS color string for a given risk tier value
def color_tier(val):
    colors = {
        "High":   "background-color: #ff4d4d; color: white;",
        "Medium": "background-color: #ff9900; color: white;",
        "Low":    "background-color: #28a745; color: white;",
    }
    return colors.get(val, "")

# .style.map applies color functions cell-by-cell to the specified columns only
styled = display_df.style \
    .map(color_window, subset=["expiry_window"]) \
    .map(color_tier,   subset=["risk_tier"]) \
    .format({"risk_score": "{:.1f}", "contract_end": lambda x: x.strftime("%Y-%m-%d")})

st.dataframe(styled, use_container_width=True, height=400)

st.divider()

# ------------------------------------------------------------------
# SECTION 5 — EXPORT BUTTON (Excel)
# ------------------------------------------------------------------

st.subheader("📤 Export Renewal Action Report")

export_cols = [
    "vendor_id", "vendor_name", "service_type", "region",
    "contract_start", "contract_end", "renewal_due_date",
    "days_to_expiry", "expiry_window", "renewal_lead_days",
    "sla_score", "data_issue_flags", "cert_expiry_date",
    "risk_score", "risk_tier", "root_cause_tags", "status"
]

export_df = filtered[export_cols].copy()

export_df = export_df.sort_values(
    by=["risk_score", "days_to_expiry"],
    ascending=[False, True]
)

# BytesIO acts as a virtual file in memory — no temp file written to disk
buffer = io.BytesIO()

with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    export_df.to_excel(writer, sheet_name="All Contracts", index=False)

    # Separate sheet for high-risk only — quick action list for the analyst
    high_risk = export_df[export_df["risk_tier"] == "High"]
    high_risk.to_excel(writer, sheet_name="High Risk Only", index=False)

    # Separate sheet for contracts expiring within 90 days
    urgent = export_df[export_df["expiry_window"].isin(["30 Days", "60 Days", "90 Days"])]
    urgent.to_excel(writer, sheet_name="Expiring in 90 Days", index=False)

# Rewind buffer to start so Streamlit can read it for the download
buffer.seek(0)

st.download_button(
    label="⬇️ Download Excel Report",
    data=buffer,
    file_name="vendor_renewal_action_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.caption(f"Showing {len(filtered)} of {len(df)} contracts based on current filters.")