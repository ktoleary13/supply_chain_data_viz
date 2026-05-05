import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Supply Chain Incidents", layout="wide")

# ── Domino's Brand Color ───────────────────────────────────────────────────────
DOMINOS_BLUE = "#006491"

# ── Data ──────────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    incidents = pd.read_excel("data/restaurant_supply_chain_dashboard.xlsx", sheet_name="Incidents")
    workers   = pd.read_excel("data/restaurant_supply_chain_dashboard.xlsx", sheet_name="Workers")

    incidents["DateOpened"] = pd.to_datetime(incidents["DateOpened"], errors="coerce")
    incidents["StatusDate"] = pd.to_datetime(incidents["StatusDate"], errors="coerce")

    incidents["HoursToClose"] = (
        (incidents["StatusDate"] - incidents["DateOpened"]).dt.total_seconds() / 3600
    ).clip(lower=0)

    incidents["SLABreached"] = incidents["HoursToClose"] > incidents["SLA_Hours"]

    return incidents.merge(workers, on="EmployeeId", how="left")

df_full = load_data()

if df_full.empty:
    st.warning("No data available.")
    st.stop()

df_full["YearMonth"] = df_full["DateOpened"].dt.to_period("M")

# ── Header ────────────────────────────────────────────────────────────────────
st.title("Supply Chain Incidents")

# ── Filters ───────────────────────────────────────────────────────────────────
fc1, fc2, fc3 = st.columns(3)

with fc1:
    sel_region = st.selectbox("Region", ["All"] + sorted(df_full["RestaurantRegion"].dropna().unique()))

with fc2:
    sel_status = st.selectbox("Case Status", ["All"] + sorted(df_full["CaseStatus"].dropna().unique()))

with fc3:
    months = sorted(df_full["YearMonth"].dropna().unique(), reverse=True)
    sel_months = st.multiselect("Month", months, default=[months[0]] if months else [])

fr2_c1, fr2_c2, fr2_c3 = st.columns(3)

with fr2_c1:
    sel_category = st.selectbox("Product Category", ["All"] + sorted(df_full["ProductCategory"].dropna().unique()))

with fr2_c2:
    sel_type = st.selectbox("Incident Type", ["All"] + sorted(df_full["IncidentType"].dropna().unique()))

with fr2_c3:
    sev_options = sorted(df_full["SeverityLevel"].dropna().unique())
    sel_sev = st.multiselect("Severity Level", sev_options, default=sev_options)

# ── Apply Filters ─────────────────────────────────────────────────────────────
df = df_full.copy()

if sel_region != "All":
    df = df[df["RestaurantRegion"] == sel_region]
if sel_status != "All":
    df = df[df["CaseStatus"] == sel_status]
if sel_category != "All":
    df = df[df["ProductCategory"] == sel_category]
if sel_type != "All":
    df = df[df["IncidentType"] == sel_type]
if sel_sev:
    df = df[df["SeverityLevel"].isin(sel_sev)]
if sel_months:
    df = df[df["YearMonth"].isin(sel_months)]

st.markdown(f"Showing **{len(df):,}** incidents")

# ── Monthly baseline (UNFILTERED for MoM) ─────────────────────────────────────
monthly = (
    df_full.groupby("YearMonth")
    .agg(
        Incidents=("CaseId", "count"),
        TotalImpact=("FinancialImpact", "sum"),
        AvgHours=("HoursToClose", "mean"),
        SLABreach=("SLABreached", "mean"),
        Escalation=("EscalatedFlag", "mean"),
    )
    .sort_index()
)

monthly["ImpactPerIncident"] = monthly["TotalImpact"] / monthly["Incidents"]

def mom(series):
    return series.iloc[-1] - series.iloc[-2] if len(series) > 1 else 0

# ── KPI Delta Color Helper ─────────────────────────────────────────────────────
# For most KPIs: higher = worse → delta_color="inverse" (red for positive delta)
# For SLA Breach Rate: we want normal Streamlit behavior (also inverse — high breach = bad)
# Streamlit delta_color options: "normal" (green=up), "inverse" (red=up), "off"

# ── KPIs ──────────────────────────────────────────────────────────────────────
st.markdown("## Key Metrics")

k1, k2, k3, k4, k5, k6 = st.columns(6)

total_incidents = len(df)
total_impact = df["FinancialImpact"].sum()
impact_per_incident = total_impact / total_incidents if total_incidents else 0

sla_rate = df["SLABreached"].mean() * 100 if not df.empty else 0
avg_hours = df["HoursToClose"].mean() if not df.empty else 0
esc_rate = df["EscalatedFlag"].mean() * 100 if not df.empty else 0

# Total Incidents: more incidents = bad → inverse
k1.metric(
    "Total Incidents",
    f"{total_incidents:,}",
    delta=f"{mom(monthly['Incidents']):,.0f}",
    delta_color="inverse"
)

# Total Financial Impact: higher cost = bad → inverse
k2.metric(
    "Total Financial Impact",
    f"${total_impact:,.0f}",
    delta=f"${mom(monthly['TotalImpact']):,.0f}",
    delta_color="inverse"
)

# Impact per Incident: higher = bad → inverse
k3.metric(
    "Impact per Incident",
    f"${impact_per_incident:,.0f}",
    delta=f"${mom(monthly['ImpactPerIncident']):,.0f}",
    delta_color="inverse"
)

# SLA Breach Rate: keep default behavior (no override — higher breach rate is bad,
# so "inverse" also applies, but the prompt says to leave this one as-is / opposite of the others)
k4.metric(
    "SLA Breach Rate",
    f"{sla_rate:.1f}%",
    delta=f"{mom(monthly['SLABreach']):.1%}",
    delta_color="normal"
)

# Avg Hours to Close: longer = bad → inverse
k5.metric(
    "Average Hours to Close",
    f"{avg_hours:.1f}",
    delta=f"{mom(monthly['AvgHours']):.1f}",
    delta_color="inverse"
)

# Escalation Rate: higher = bad → inverse
k6.metric(
    "Escalation Rate",
    f"{esc_rate:.1f}%",
    delta=f"{mom(monthly['Escalation']):.1%}",
    delta_color="inverse"
)

# ── Actionable Insight Banner ─────────────────────────────────────────────────
st.markdown("---")

if not df.empty:
    top_vendor = df.groupby("VendorName")["FinancialImpact"].sum().idxmax()
    top_vendor_impact = df.groupby("VendorName")["FinancialImpact"].sum().max()
    top_region = df.groupby("RestaurantRegion")["CaseId"].count().idxmax()
    top_incident_type = df.groupby("IncidentType")["CaseId"].count().idxmax()
    breach_pct = df["SLABreached"].mean() * 100
    top_sev = df[df["SeverityLevel"] == df["SeverityLevel"].max()] if "SeverityLevel" in df.columns else pd.DataFrame()

    insights = []

    if top_vendor:
        insights.append(f"**Vendor Risk:** **{top_vendor}** accounts for **${top_vendor_impact:,.0f}** in financial impact — consider contract review or alternate sourcing.")

    if top_region:
        region_count = df.groupby("RestaurantRegion")["CaseId"].count()[top_region]
        insights.append(f"**Regional Hotspot:** **{top_region}** leads with **{region_count:,}** incidents — prioritize field team review or supplier audit in this area.")
        
    if top_incident_type:
        type_count = df.groupby("IncidentType")["CaseId"].count()[top_incident_type]
        insights.append(f"**Recurring Pattern:** **{top_incident_type}** is the most frequent incident type (**{type_count:,}** cases) — root cause analysis recommended.")

    if insights:
        st.markdown("### Insights")
        for insight in insights:
            st.info(insight)

st.markdown("---")

# ── Trends ────────────────────────────────────────────────────────────────────
st.markdown("### Incident Trends")

monthly_plot = monthly.reset_index()
monthly_plot["Month"] = monthly_plot["YearMonth"].astype(str)

fig = make_subplots(specs=[[{"secondary_y": True}]])

fig.add_bar(
    x=monthly_plot["Month"],
    y=monthly_plot["Incidents"],
    name="Incidents",
    marker_color=DOMINOS_BLUE
)

fig.add_scatter(
    x=monthly_plot["Month"],
    y=monthly_plot["TotalImpact"],
    name="Financial Impact",
    secondary_y=True,
    line=dict(color="red", width=2),
    marker=dict(color="red")
)

st.plotly_chart(fig, use_container_width=True)

# ── Vendor + Impact ───────────────────────────────────────────────────────────
st.markdown("### Vendor and Financial Impact")

col1, col2 = st.columns(2)

# Continuous blues: light (#c6dbef) → Domino's blue (#006491) → deep navy (#003152)
BLUES_CONTINUOUS = [[0.0, "#c6dbef"], [0.5, "#006491"], [1.0, "#003152"]]

def blues_for_categories(n):
    """Return n evenly spaced hex colors sampled from the continuous blue scale."""
    import plotly.colors as pc
    if n == 1:
        return ["#006491"]
    scale_colors = ["#c6dbef", "#6baed6", "#2171b5", "#006491", "#084594", "#003152"]
    sampled = pc.sample_colorscale(
        [[i / (len(scale_colors) - 1), c] for i, c in enumerate(scale_colors)],
        [i / (n - 1) for i in range(n)]
    )
    return sampled

vendor_stacked = (
    df.groupby(["VendorName", "ProductCategory"], as_index=False)["FinancialImpact"].sum()
)

vendor_order = (
    vendor_stacked.groupby("VendorName")["FinancialImpact"]
    .sum()
    .sort_values()
    .index.tolist()
)

categories = sorted(vendor_stacked["ProductCategory"].dropna().unique())
cat_colors = blues_for_categories(len(categories))
color_map = {cat: cat_colors[i] for i, cat in enumerate(categories)}

with col1:
    fig_vendor = px.bar(
        vendor_stacked,
        x="FinancialImpact",
        y="VendorName",
        color="ProductCategory",
        orientation="h",
        category_orders={"VendorName": vendor_order},
        color_discrete_map=color_map,
        labels={"FinancialImpact": "Financial Impact", "VendorName": "Vendor", "ProductCategory": "Product Category"},
        title="Financial Impact by Vendor & Product Category"
    )
    st.plotly_chart(fig_vendor, use_container_width=True)

with col2:
    fig_hist = px.histogram(
        df,
        x="FinancialImpact",
        labels={"FinancialImpact": "Financial Impact"},
        title="Financial Impact Distribution"
    )
    fig_hist.update_traces(marker_color=DOMINOS_BLUE)
    st.plotly_chart(fig_hist, use_container_width=True)

# ── Heatmap ───────────────────────────────────────────────────────────────────
st.markdown("### Incidents by Region and Type")

heat = (
    df.groupby(["RestaurantRegion", "IncidentType"])
    .agg(
        Count=("CaseId", "count"),
        AvgImpact=("FinancialImpact", "mean")
    )
    .reset_index()
)

pivot_impact = heat.pivot(index="RestaurantRegion", columns="IncidentType", values="AvgImpact").fillna(0)
pivot_count  = heat.pivot(index="RestaurantRegion", columns="IncidentType", values="Count").fillna(0)

# Build custom hover text: avg impact + incident count
hover_text = []
for region in pivot_impact.index:
    row = []
    for itype in pivot_impact.columns:
        avg_imp = pivot_impact.loc[region, itype]
        cnt = int(pivot_count.loc[region, itype]) if region in pivot_count.index and itype in pivot_count.columns else 0
        row.append(f"Region: {region}<br>Type: {itype}<br>Avg Impact: ${avg_imp:,.0f}<br>Incidents: {cnt:,}")
    hover_text.append(row)

fig_heat = px.imshow(
    pivot_impact,
    color_continuous_scale="RdBu_r",
    aspect="auto",
    labels=dict(
        x="Incident Type",
        y="Restaurant Region",
        color="Average Financial Impact"
    ),
    title="Average Financial Impact by Region & Incident Type"
)

fig_heat.update_traces(
    customdata=pivot_count.values,
    hovertemplate=(
        "<b>%{y}</b> — %{x}<br>"
        "Avg Financial Impact: $%{z:,.0f}<br>"
        "Incidents: %{customdata:,}<extra></extra>"
    )
)

st.plotly_chart(fig_heat, use_container_width=True)

# ── Resolution (stacked) ──────────────────────────────────────────────────────
st.markdown("### Hours to Close by Incident Type")

stack = (
    df.groupby(["IncidentType", "Team"])["HoursToClose"]
    .mean()
    .reset_index()
)

teams = sorted(stack["Team"].dropna().unique())
team_colors = blues_for_categories(len(teams))
team_color_map = {team: team_colors[i] for i, team in enumerate(teams)}

fig_stack = px.bar(
    stack,
    x="HoursToClose",
    y="IncidentType",
    color="Team",
    orientation="h",
    color_discrete_map=team_color_map,
    labels={
        "HoursToClose": "Average Hours to Close",
        "IncidentType": "Incident Type",
        "Team": "Team"
    },
    title="Average Resolution Time by Incident Type & Team"
)

st.plotly_chart(fig_stack, use_container_width=True)

# ── Escalation Rate by Severity ───────────────────────────────────────────────
st.markdown("### Escalation Rate by Severity Level")

esc_sev = (
    df.groupby("SeverityLevel")
    .agg(
        EscalationRate=("EscalatedFlag", "mean"),
        Incidents=("CaseId", "count")
    )
    .reset_index()
)
esc_sev["EscalationRate"] = esc_sev["EscalationRate"] * 100
esc_sev = esc_sev.sort_values("SeverityLevel")

fig_esc = px.bar(
    esc_sev,
    x="SeverityLevel",
    y="EscalationRate",
    color="EscalationRate",
    color_continuous_scale=BLUES_CONTINUOUS,
    labels={"EscalationRate": "Escalation Rate (%)", "SeverityLevel": "Severity Level"},
    title="Escalation Rate by Severity — Are High-Severity Cases Being Properly Routed?",
    hover_data={"Incidents": True}
)
fig_esc.update_coloraxes(showscale=False)
st.plotly_chart(fig_esc, use_container_width=True)

# ── Raw Data ──────────────────────────────────────────────────────────────────
st.markdown("### Raw Data")

with st.expander("View Data"):
    st.dataframe(df, use_container_width=True)