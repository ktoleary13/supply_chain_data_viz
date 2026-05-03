import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="Supply Chain Incident Breakdown",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Palette ───────────────────────────────────────────────────────────────────
BLUE  = "#0078AC"
RED   = "#D2112C"
RED2  = "#E61838"
WHITE = "#FFFFFF"

SEV_COLORS = {
    1: "#cce8f4",
    2: "#80c5e8",
    3: BLUE,
    4: "#8c0a1c",
    5: RED,
}

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    .section-header {{
        font-size: 17px; font-weight: 700; color: {BLUE};
        border-left: 4px solid {RED}; padding-left: 10px;
        margin: 24px 0 12px 0;
    }}
    div[data-testid="stMetric"] {{
        background: #f2f8fc; border-radius: 10px; padding: 12px 16px;
        border-top: 3px solid {BLUE};
    }}
</style>
""", unsafe_allow_html=True)


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    incidents = pd.read_excel("data/restaurant_supply_chain_dashboard.xlsx", sheet_name="Incidents")
    workers   = pd.read_excel("data/restaurant_supply_chain_dashboard.xlsx", sheet_name="Workers")

    incidents["DateOpened"]   = pd.to_datetime(incidents["DateOpened"])
    incidents["StatusDate"]   = pd.to_datetime(incidents["StatusDate"])
    incidents["SLABreached"]  = incidents["HoursOpen"] > incidents["SLA_Hours"]

    # Hours open = time between DateOpened and StatusDate
    incidents["HoursToClose"] = (
        (incidents["StatusDate"] - incidents["DateOpened"]).dt.total_seconds() / 3600
    ).clip(lower=0)

    merged = incidents.merge(workers, on="EmployeeId", how="left")
    return incidents, workers, merged


incidents, workers, merged = load_data()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# Supply Chain Incident Breakdown")
st.markdown("---")

# ── Top-of-page filters ───────────────────────────────────────────────────────

# ── Top-of-page filters ───────────────────────────────────────────────────────
st.markdown('<div class="section-header">Filters</div>', unsafe_allow_html=True)

# Row 1: Region, Case Status, Date Range, Trend Aggregation
fc1, fc2, fc3, fc4 = st.columns([1.5, 1.5, 2, 1.5])

with fc1:
    regions = ["All"] + sorted(incidents["RestaurantRegion"].dropna().unique())
    sel_region = st.selectbox("Region", regions)

with fc2:
    statuses = ["All"] + sorted(incidents["CaseStatus"].dropna().unique())
    sel_status = st.selectbox("Case Status", statuses)

with fc3:
    date_min = incidents["DateOpened"].min().date()
    date_max = incidents["DateOpened"].max().date()
    sel_dates = st.date_input("Date Range", value=(date_min, date_max),
                              min_value=date_min, max_value=date_max)

with fc4:
    sel_agg = st.selectbox("Trend Aggregation", ["Week", "Month", "Quarter"], index=1)

# Row 2: Product Category, Incident Type, Severity
fr2_c1, fr2_c2, fr2_c3 = st.columns([1.5, 1.5, 1.5])

with fr2_c1:
    categories = ["All"] + sorted(incidents["ProductCategory"].dropna().unique())
    sel_category = st.selectbox("Product Category", categories)

with fr2_c2:
    incident_types = ["All"] + sorted(incidents["IncidentType"].dropna().unique())
    sel_type = st.selectbox("Incident Type", incident_types)

with fr2_c3:
    severities = sorted(incidents["SeverityLevel"].dropna().unique())
    sel_sev = st.multiselect("Severity Level", severities, default=list(severities))

st.markdown("---")

# ── Apply filters ─────────────────────────────────────────────────────────────
df = merged.copy()
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
if len(sel_dates) == 2:
    df = df[(df["DateOpened"].dt.date >= sel_dates[0]) &
            (df["DateOpened"].dt.date <= sel_dates[1])]

st.markdown(f"Showing **{len(df):,}** incidents · Data through **{df['DateOpened'].max().strftime('%b %Y') if not df.empty else 'N/A'}**")

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)

total_incidents = len(df)
total_impact    = df["FinancialImpact"].sum()
avg_hrs_close   = df["HoursToClose"].mean() if not df.empty else 0
sla_breach_rate = df["SLABreached"].mean() * 100 if not df.empty else 0
escalation_rate = df["EscalatedFlag"].mean() * 100 if not df.empty else 0

with k1:
    st.metric("Total Incidents", f"{total_incidents:,}")
with k2:
    st.metric("Total Financial Impact", f"${total_impact / 1_000_000:.1f}M")
with k3:
    st.metric("Avg Hours Open", f"{avg_hrs_close:.0f} hrs")
with k4:
    st.metric("SLA Breach Rate", f"{sla_breach_rate:.1f}%")
with k5:
    st.metric("Escalation Rate", f"{escalation_rate:.1f}%")

st.markdown("---")


# ── Row 1: Stacked trend + Incident Type breakdown ────────────────────────────
st.markdown('<div class="section-header">Incident Trends</div>', unsafe_allow_html=True)
col1, col2 = st.columns([3, 2])

with col1:
    if sel_agg == "Week":
        df["PeriodKey"] = df["DateOpened"].dt.to_period("W").apply(lambda p: str(p.start_time.date()))
        xlabel = "Week Starting"
    elif sel_agg == "Quarter":
        df["PeriodKey"] = df["DateOpened"].dt.to_period("Q").astype(str)
        xlabel = "Quarter"
    else:
        df["PeriodKey"] = df["DateOpened"].dt.strftime("%Y-%m")
        xlabel = "Month"

    sev_trend = (
        df.groupby(["PeriodKey", "SeverityLevel"])
        .size()
        .reset_index(name="Count")
        .sort_values(["PeriodKey", "SeverityLevel"])
    )
    period_totals = sev_trend.groupby("PeriodKey")["Count"].sum().reset_index(name="Total")

    impact_trend = (
        df.groupby("PeriodKey")["FinancialImpact"].sum().reset_index()
        .sort_values("PeriodKey")
    )

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    for sev in sorted(df["SeverityLevel"].unique()):
        sub = sev_trend[sev_trend["SeverityLevel"] == sev].merge(period_totals, on="PeriodKey")
        fig.add_trace(
            go.Bar(
                x=sub["PeriodKey"],
                y=sub["Count"],
                name=f"Severity {sev}",
                marker_color=SEV_COLORS.get(sev, BLUE),
                customdata=sub[["Total"]],
                hovertemplate=(
                    f"<b>Severity {sev}</b><br>"
                    "%{x}<br>"
                    "Severity Count: %{y}<br>"
                    "Period Total: %{customdata[0]}<extra></extra>"
                ),
            ),
            secondary_y=False,
        )

    fig.add_trace(
        go.Scatter(
            x=impact_trend["PeriodKey"],
            y=impact_trend["FinancialImpact"],
            name="Financial Impact ($)",
            line=dict(color=RED2, width=2),
            mode="lines+markers",
            hovertemplate="%{x}<br>Impact: $%{y:,.0f}<extra></extra>",
        ),
        secondary_y=True,
    )

    fig.update_layout(
        title=f"{sel_agg}ly Incidents & Financial Impact",
        barmode="stack",
        height=360,
        plot_bgcolor=WHITE,
        paper_bgcolor=WHITE,
        legend=dict(orientation="h", y=1.14),
        xaxis=dict(tickangle=-45, title=xlabel),
    )
    fig.update_yaxes(title_text="# Incidents", secondary_y=False)
    fig.update_yaxes(title_text="Financial Impact ($)", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    sev_type = (
        df.groupby(["IncidentType", "SeverityLevel"])["FinancialImpact"]
        .sum()
        .reset_index()
        .sort_values(["IncidentType", "SeverityLevel"])
    )
    type_totals = sev_type.groupby("IncidentType")["FinancialImpact"].sum().reset_index(name="TypeTotal")
    sev_type = sev_type.merge(type_totals, on="IncidentType").sort_values("TypeTotal", ascending=True)

    fig2 = go.Figure()
    for sev in sorted(sev_type["SeverityLevel"].unique()):
        sub = sev_type[sev_type["SeverityLevel"] == sev]
        fig2.add_trace(go.Bar(
            x=sub["FinancialImpact"],
            y=sub["IncidentType"],
            name=f"Severity {sev}",
            orientation="h",
            marker_color=SEV_COLORS.get(sev, BLUE),
            customdata=sub[["TypeTotal"]],
            hovertemplate=(
                f"<b>Severity {sev}</b><br>"
                "%{y}<br>"
                "Severity Impact: $%{x:,.0f}<br>"
                "Type Total: $%{customdata[0]:,.0f}<extra></extra>"
            ),
        ))

    fig2.update_layout(
        barmode="stack",
        title="Financial Impact by Incident Type",
        height=360,
        plot_bgcolor=WHITE,
        paper_bgcolor=WHITE,
        legend=dict(orientation="h", y=1.12, font=dict(size=10)),
        xaxis=dict(title="Total Impact ($)", tickprefix="$", tickformat=",.0f"),
        yaxis=dict(title=""),
    )
    st.plotly_chart(fig2, use_container_width=True)


# ── Row 2: Region heatmap ─────────────────────────────────────────────────────
st.markdown('<div class="section-header">Incidents by Region</div>', unsafe_allow_html=True)
heat_data  = df.groupby(["RestaurantRegion", "IncidentType"]).size().reset_index(name="Count")
heat_pivot = heat_data.pivot(index="RestaurantRegion", columns="IncidentType", values="Count").fillna(0)
fig3 = px.imshow(
    heat_pivot, text_auto=True, aspect="auto",
    color_continuous_scale=[[0, WHITE], [0.5, "#80c5e8"], [1, BLUE]],
    title="Incident Count: Region x Type",
)
fig3.update_layout(height=300, plot_bgcolor=WHITE, paper_bgcolor=WHITE)
st.plotly_chart(fig3, use_container_width=True)


# ── Row 3: Vendor — Top 5 and Bottom 5 ───────────────────────────────────────
st.markdown('<div class="section-header">Vendor Performance</div>', unsafe_allow_html=True)
col5, col6 = st.columns(2)

vendor_all = (
    df.groupby("VendorName")
    .agg(Count=("CaseId", "count"), TotalLoss=("FinancialImpact", "sum"))
    .reset_index()
    .sort_values("TotalLoss", ascending=False)
)

with col5:
    top5 = vendor_all.head(5).sort_values("TotalLoss", ascending=True)
    fig5 = px.bar(
        top5, x="TotalLoss", y="VendorName", orientation="h",
        title="Top 5 Vendors by Total Loss",
        color="TotalLoss",
        color_continuous_scale=[[0, "#cce8f4"], [0.5, BLUE], [1, "#004d70"]],
        labels={"TotalLoss": "Total Loss ($)", "VendorName": ""},
        text="TotalLoss",
    )
    fig5.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
    fig5.update_layout(height=320, plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                       coloraxis_showscale=False)
    st.plotly_chart(fig5, use_container_width=True)

with col6:
    bot5 = vendor_all.tail(5).sort_values("TotalLoss", ascending=True)
    fig6 = px.bar(
        bot5, x="TotalLoss", y="VendorName", orientation="h",
        title="Bottom 5 Vendors by Total Loss",
        color="TotalLoss",
        color_continuous_scale=[[0, "#fce8eb"], [0.5, RED2], [1, "#8c0a1c"]],
        labels={"TotalLoss": "Total Loss ($)", "VendorName": ""},
        text="TotalLoss",
    )
    fig6.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
    fig6.update_layout(height=320, plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                       coloraxis_showscale=False)
    st.plotly_chart(fig6, use_container_width=True)


# ── Row 4: Avg Hours Open by Incident Type ────────────────────────────────────
st.markdown('<div class="section-header">Resolution Time</div>', unsafe_allow_html=True)

avg_hours = (
    df.groupby("IncidentType")["HoursToClose"]
    .mean()
    .reset_index()
    .rename(columns={"HoursToClose": "AvgHoursOpen"})
    .sort_values("AvgHoursOpen", ascending=True)
)
fig_hrs = px.bar(
    avg_hours, x="AvgHoursOpen", y="IncidentType", orientation="h",
    title="Avg Hours Open by Incident Type",
    color="AvgHoursOpen",
    color_continuous_scale=[[0, "#cce8f4"], [0.5, BLUE], [1, "#004d70"]],
    labels={"AvgHoursOpen": "Avg Hours Open", "IncidentType": ""},
    text="AvgHoursOpen",
)
fig_hrs.update_traces(texttemplate="%{text:.0f} hrs", textposition="outside")
fig_hrs.update_layout(height=340, plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                      coloraxis_showscale=False)
st.plotly_chart(fig_hrs, use_container_width=True)


# ── Row 5: Team / Worker performance ─────────────────────────────────────────
st.markdown('<div class="section-header">Team & Worker Performance</div>', unsafe_allow_html=True)
col8, col9 = st.columns(2)

with col8:
    team_perf = df.groupby("Team").agg(
        Incidents=("CaseId", "count"),
        AvgHours=("HoursToClose", "mean"),
        EscalationRate=("EscalatedFlag", "mean"),
    ).reset_index()

    fig8 = go.Figure()
    for m, c in zip(["Incidents", "AvgHours", "EscalationRate"], [BLUE, "#80c5e8", RED]):
        norm = (team_perf[m] - team_perf[m].min()) / (team_perf[m].max() - team_perf[m].min() + 1e-9)
        fig8.add_trace(go.Bar(name=m, x=team_perf["Team"], y=norm,
                              marker_color=c, opacity=0.9))
    fig8.update_layout(
        barmode="group", title="Team KPIs (normalised)",
        height=320, plot_bgcolor=WHITE, paper_bgcolor=WHITE,
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig8, use_container_width=True)

with col9:
    top_workers = (
        df.groupby(["EmployeeName", "JobTitle"])
        .agg(Incidents=("CaseId", "count"), TotalImpact=("FinancialImpact", "sum"))
        .reset_index()
        .sort_values("TotalImpact", ascending=False)
        .head(10)
    )
    top_workers["TotalImpact"] = top_workers["TotalImpact"].map("${:,.0f}".format)

    st.markdown("**Top 10 Employees by Cases Handled (Financial Impact)**")
    st.dataframe(
        top_workers.rename(columns={
            "EmployeeName": "Employee", "JobTitle": "Title",
            "Incidents": "# Cases", "TotalImpact": "Total Impact",
        }),
        hide_index=True, use_container_width=True, height=295,
    )


# ── Raw data explorer ─────────────────────────────────────────────────────────
with st.expander("Raw Data Explorer"):
    st.dataframe(
        df[["CaseId", "DateOpened", "IncidentType", "RestaurantRegion", "CaseStatus",
            "SeverityLevel", "FinancialImpact", "HoursOpen", "HoursToClose",
            "SLABreached", "VendorName", "ProductCategory", "RootCause",
            "EscalatedFlag", "EmployeeName", "Team"]]
        .sort_values("DateOpened", ascending=False),
        hide_index=True, use_container_width=True, height=350,
    )
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download filtered CSV", csv, "filtered_incidents.csv", "text/csv")

st.markdown("---")
st.caption("Restaurant Supply Chain Dashboard · Built with Streamlit & Plotly")
