# Delivery Hub Analysis

An analysis of courier operations across six delivery hubs using SQL, Python, and Streamlit.

## Overview

The project examines agent productivity, hub utilisation, delivery holds, returns, operating costs, and four-week staffing requirements.

It also compares hiring, internal transfers, and operational improvement scenarios under a fixed budget.

## Tools

- Python and pandas
- SQLite
- Streamlit and Plotly
- pytest

## Dashboard

Install dependencies:

    python -m pip install -r requirements.txt

Run the dashboard:

    python -m streamlit run app.py

The dashboard reads from the aggregated dashboard_data folder and does not require the original order-level files or SQLite database.

## Project Structure

- app.py - Interactive dashboard
- dashboard_data/ - Aggregated dashboard data
- sql/ - SQL analysis queries
- src/ - Data processing and analysis
- tests/ - Automated tests
- ASSUMPTIONS.md - Analysis assumptions

## Notes

The repository is based on a courier operations assessment case study. Financial projections depend on the documented staffing and operational assumptions.
