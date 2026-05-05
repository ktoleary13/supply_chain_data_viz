# Restaurant Supply Chain Dashboard

An interactive supply chain operations dashboard built with **Streamlit** and **Plotly**, analyzing 5,000 incidents across restaurant regions, vendors, and internal teams.

## Dashboard Features

| Section | Visuals |
|---|---|
| **KPIs** | Total incidents, financial impact, Avg resolution time, SLA breach %, Escalation % |
| **Trends** | Monthly incident volume + financial impact (dual-axis) |
| **Incident Breakdown** | By type, region heatmap (region × type) |
| **Data Explorer** | Filterable raw table + CSV export |

## Dataset

Two sheets from `data/restaurant_supply_chain_dashboard.xlsx`:
- **Incidents** — 5,000 rows × 18 columns (case details, financial impact, SLA, vendor, root cause …)
- **Workers** — 60 rows × 6 columns (employee ID, job title, team, region, tenure)

## Project Structure

```
supply-chain-dashboard/
├── app.py                                     # Streamlit dashboard
├── requirements.txt                           # Python dependencies
├── README.md                                  # This file
└── data/
    └── restaurant_supply_chain_dashboard.xlsx # Source dataset
```
