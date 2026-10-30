"""CarryBee operations dashboard. Runs solely on the validated aggregate snapshot."""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.dashboard_data import load_snapshot, dashboard_source_zip

st.set_page_config(page_title="CarryBee | Operations intelligence", page_icon="🐝", layout="wide")

TEAL, INK, AMBER, RED, MUTED = "#087F79", "#143638", "#E7A44C", "#C95545", "#718789"
PALETTE = [TEAL, AMBER, "#5C85A5", "#956B9C", "#86A45C", "#CF7B6B"]
st.markdown("""<style>
.stApp {background:#F4F7F6;color:#143638;}
.block-container {padding-top:4.5rem;padding-bottom:2rem;max-width:1500px;}
h1,h2,h3 {font-family:Inter,Segoe UI,sans-serif;letter-spacing:-.035em;color:#143638;}
h1 {font-size:2.5rem;font-weight:750;line-height:1.15;}
h3 {font-size:1.15rem;}
[data-testid="stSidebar"] {background:#143638;}
[data-testid="stSidebar"] * {color:#E6F0ED;}
[data-testid="stSidebar"] [data-baseweb="select"] * {color:#143638;}
[data-testid="stSidebar"] input {color:#143638;}
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button * {color:#143638!important;}
[data-testid="stMetric"] {background:white;border:1px solid #DCE6E2;border-radius:14px;padding:18px 20px;}
[data-testid="stMetricValue"] {color:#143638;font-variant-numeric:tabular-nums;}
[data-testid="stMetricLabel"] {color:#52706B;font-weight:600;}
[data-testid="stPlotlyChart"] {border-radius:14px;overflow:hidden;}
.eyebrow {font-size:.72rem;font-weight:750;letter-spacing:.13em;color:#087F79;margin-bottom:.65rem;}
.lede {font-size:1rem;color:#5A7470;margin:-.3rem 0 1.35rem;max-width:900px;}
.brand {font-size:1.65rem;font-weight:800;letter-spacing:-.05em;margin:.3rem 0 0;}
.brand-sub {font-size:.72rem;letter-spacing:.14em;color:#9FBFB7!important;margin-bottom:2rem;}
.footnote {font-size:.8rem;color:#718789;border-top:1px solid #DCE6E2;padding-top:1rem;margin-top:2rem;}
[data-testid="stDataFrame"] {border-radius:10px;}
@media(min-width:701px) and (max-width:1300px) {[data-testid="stMetricValue"]{font-size:1.15rem!important;} [data-testid="stMetric"]{padding:12px 10px;}}
@media(max-width:700px) {h1{font-size:1.9rem;} .block-container{padding:4.5rem 1rem 1rem;} [data-testid="stMetric"]{padding:12px;}}
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def data():
    return load_snapshot()


def chart(fig, height=340):
    fig.update_layout(template="plotly_white", font=dict(family="Segoe UI, sans-serif", size=12, color=INK),
                      paper_bgcolor="white", plot_bgcolor="white", margin=dict(l=20, r=20, t=70, b=35),
                      height=height, legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, title=None),
                      hoverlabel=dict(bgcolor="white"))
    fig.update_xaxes(gridcolor="#EEF2F0", zeroline=False)
    fig.update_yaxes(gridcolor="#EEF2F0", zeroline=False)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]})


def section(title, subtitle):
    st.markdown(title)
    st.caption(subtitle)


def money(amount):
    return f"BDT {amount:,.0f}"


def table(frame, percent=(), currency=()):
    config = {col: st.column_config.Column(col.replace("_", " ").title()) for col in frame.columns}
    config.update({col: st.column_config.NumberColumn(col.replace("_", " ").title(), format="percent") for col in percent})
    config.update({col: st.column_config.NumberColumn(col.replace("_", " ").title(), format="BDT %.2f") for col in currency})
    st.dataframe(frame, hide_index=True, width="stretch", column_config=config, height=min(36 * (len(frame) + 1) + 3, 600))


try:
    tables, meta = data()
except (OSError, ValueError, KeyError) as error:
    st.error(f"Validated dashboard snapshot unavailable: {error}")
    st.info("Project owner: run python -m src.scenario_analysis, then python -m src.prepare_dashboard_data, and redeploy the aggregate snapshot.")
    st.stop()

with st.sidebar:
    st.markdown('<div class="brand">carrybee<span style="color:#E7A44C">.</span></div><div class="brand-sub">OPERATIONS INTELLIGENCE</div>', unsafe_allow_html=True)
    pages = ["Executive Overview", "Hub Diagnostics", "Forecast and Budget"]
    route = {"overview": 0, "hubs": 1, "forecast": 2}.get(st.query_params.get("view", "overview"), 0)
    page = st.radio("Workspace", pages, index=route, key="page")
    st.divider()
    cluster_options = tables["hubs"].cluster.unique().tolist()
    clusters = st.multiselect("Clusters", cluster_options, default=cluster_options, key="clusters")
    period = st.selectbox("Historical period", ["Both weeks", "Week 1 · 13–19 Oct", "Week 2 · 20–26 Oct"], key="period")
    st.caption("Historical filters affect observed metrics. Forecasts cover all four weeks. Network budgets stay network-wide.")
    st.divider()
    st.caption("OBSERVED  ·  13–26 OCT 2026\n\nPROJECTED  ·  27 OCT–23 NOV 2026")
    st.caption("Validated snapshot · no raw order records")
    st.download_button("Download dashboard source", data=dashboard_source_zip(),
                       file_name="CarryBee-Phase2-dashboard-source.zip", mime="application/zip")

if not clusters:
    st.info("Select at least one cluster to view operations.")
    st.stop()
hub_scope = tables["hubs"].query("cluster in @clusters")
hub_ids = hub_scope.hub_id.tolist()
weeks = [1, 2] if period == "Both weeks" else ([1] if period.startswith("Week 1") else [2])
history = tables["historical_hub_week"].query("hub_id in @hub_ids and week in @weeks").copy()
daily = tables["daily_hub"].query("hub_id in @hub_ids and week in @weeks").copy()
reasons = tables["hold_reasons"].query("hub_id in @hub_ids and week in @weeks").copy()


if page == "Executive Overview":
    st.markdown('<div class="eyebrow">01 / OBSERVED OPERATIONS</div>', unsafe_allow_html=True)
    st.title("Operations overview")
    st.markdown('<div class="lede">Delivery performance, operating costs and the hubs under pressure.</div>', unsafe_allow_html=True)
    orders = int(history.orders.sum())
    attempts = int(history.attempts.sum())
    cards = st.columns(4)
    cards[0].metric("Orders created", f"{orders:,}")
    cards[1].metric("Final delivery rate", f"{history.delivered_final.sum()/orders:.1%}")
    cards[2].metric("Final return rate", f"{history.returned_final.sum()/orders:.1%}")
    cards[3].metric("Hold events / attempts", f"{history.holds.sum()/attempts:.1%}")
    st.caption("Delivery and return rates use the created-order cohort's final status at 26 October. Hold rate uses event counts / Assigned attempts; an order can be held more than once.")
    col1, col2 = st.columns([1.1, 1])
    with col1:
        section("### Hub workload", "Assigned attempts / (eligible agent-days × 40). The planning target is 85%.")
        plot = history.assign(Week=history.week.map({1: "Week 1", 2: "Week 2"}))
        fig = px.bar(plot, x="utilisation", y="hub_name", color="Week", barmode="group", orientation="h",
                     color_discrete_map={"Week 1": "#A7C9C1", "Week 2": TEAL}, labels={"hub_name": "", "utilisation": "Utilisation"})
        fig.add_vline(x=.85, line_dash="dash", line_color=AMBER, annotation_text="85% target", annotation_position="top right")
        fig.update_xaxes(tickformat=".0%", range=[0, max(1.05, history.utilisation.max()*1.1)])
        fig.update_yaxes(autorange="reversed")
        chart(fig, 350)
    with col2:
        section("### Cost per delivered order", "BDT · fixed pay, allowances, hold and return charges; all eligible days paid.")
        fig = px.bar(plot, x="cost_per_delivered_order_bdt", y="hub_name", color="Week", barmode="group", orientation="h",
                     color_discrete_map={"Week 1": "#E4CFAC", "Week 2": AMBER}, labels={"hub_name": "", "cost_per_delivered_order_bdt": "BDT / delivered order"})
        fig.update_yaxes(autorange="reversed")
        chart(fig, 350)
    col1, col2 = st.columns([1.6, 1])
    with col1:
        section("### Week-to-week movement", "Counts use their stated grain. Costs and workload follow event dates.")
        comparison = history.groupby("week", as_index=False).agg(orders=("orders", "sum"), attempts=("attempts", "sum"),
            delivered=("delivered", "sum"), holds=("holds", "sum"), returned=("returned", "sum"),
            operating_cost_bdt=("operating_cost_bdt", "sum"), agent_days=("available_agent_days", "sum"))
        comparison["utilisation"] = comparison.attempts / (comparison.agent_days * 40)
        comparison["cost_per_delivery_bdt"] = comparison.operating_cost_bdt / comparison.delivered
        table(comparison[["week", "orders", "attempts", "delivered", "holds", "returned", "utilisation", "cost_per_delivery_bdt"]],
              percent=["utilisation"], currency=["cost_per_delivery_bdt"])
        if len(comparison) == 2:
            growth = comparison.iloc[1].attempts / comparison.iloc[0].attempts - 1
            st.caption(f"Assigned workload changed {growth:+.1%} from Week 1 to Week 2 in the selected clusters.")
    with col2:
        section("### Management signals", "Calculated from the current historical selection.")
        latest = history.loc[history.week.eq(history.week.max())]
        overloaded = latest.query("utilisation > .85").hub_name.tolist()
        if overloaded:
            st.warning("Above 85%: " + ", ".join(overloaded))
        else:
            st.success("All selected hubs are at or below the 85% target.")
        agent_holds = int(reasons.loc[reasons.agent_side, "hold_events"].sum())
        total_holds = int(reasons.hold_events.sum())
        st.info(f"Agent-side causes account for {agent_holds:,} of {total_holds:,} holds ({agent_holds/total_holds:.1%}).")
        st.caption("Recent order cohorts have less time to resolve. Read final-status rates alongside attempt events, not as a causal week-on-week comparison.")

elif page == "Hub Diagnostics":
    st.markdown('<div class="eyebrow">02 / OBSERVED HUB PERFORMANCE</div>', unsafe_allow_html=True)
    st.title("Hub diagnostics")
    selected_hub = st.selectbox("Select hub", hub_scope.hub_name.tolist(), key="hub")
    hub_id = hub_scope.loc[hub_scope.hub_name.eq(selected_hub), "hub_id"].iloc[0]
    hd = daily.query("hub_id == @hub_id")
    hh = history.query("hub_id == @hub_id")
    hr = reasons.query("hub_id == @hub_id")
    total_holds = hr.hold_events.sum()
    agent_holds = hr.loc[hr.agent_side, "hold_events"].sum()
    metrics = st.columns(4)
    metrics[0].metric("Assigned attempts", f"{hd.attempts.sum():,}")
    metrics[1].metric("Deliveries / agent-day", f"{hd.delivered.sum()/hd.agent_days.sum():.1f}")
    metrics[2].metric("Agent-side hold share", f"{agent_holds/total_holds:.1%}" if total_holds else "n/a")
    metrics[3].metric("Returned outcomes", f"{hd.returned.sum():,}")
    st.caption("Each Assigned event is an attempt. Agent-days include joining/departure eligibility and zero-activity days.")
    left, right = st.columns([1.3, 1])
    with left:
        section("### Daily throughput and workload", "Actual event counts · 13–26 October 2026")
        melted = hd.melt(id_vars="day", value_vars=["attempts", "delivered", "returned"], var_name="Metric", value_name="Events")
        fig = px.line(melted, x="day", y="Events", color="Metric", markers=True,
                      color_discrete_map={"attempts": INK, "delivered": TEAL, "returned": RED}, labels={"day": ""})
        chart(fig, 350)
    with right:
        section("### Reasons behind holds", "Agent-side reasons are highlighted. Ranking uses event counts.")
        hold_plot = hr.groupby(["hold_reason", "agent_side"], as_index=False).hold_events.sum().sort_values("hold_events")
        hold_plot["Cause"] = hold_plot.agent_side.map({True: "Agent-side", False: "Customer-side"})
        fig = px.bar(hold_plot, x="hold_events", y="hold_reason", color="Cause", orientation="h",
                     color_discrete_map={"Agent-side": AMBER, "Customer-side": "#92B8B0"}, labels={"hold_events": "Hold events", "hold_reason": ""})
        chart(fig, 350)
    left, right = st.columns([1.3, 1])
    with left:
        section("### Agent productivity", "Anonymised agents · totals for the selected weeks; eligible days include zero activity.")
        agents = tables["agent_productivity"].query("hub_id == @hub_id and week in @weeks")
        agents = agents.groupby("agent", as_index=False)[["eligible_days", "attempts", "delivered", "holds", "returned"]].sum()
        agents["deliveries_per_day"] = agents.delivered / agents.eligible_days
        agents["return_ratio"] = agents.returned / agents.attempts.replace(0, float("nan"))
        table(agents.sort_values("deliveries_per_day", ascending=False), percent=["return_ratio"])
    with right:
        section("### High-return review · Q5", "Full 14-day screen: tenure >30 days and Returned attempts / Assigned attempts >15%.")
        flagged = tables["high_return_agents"].query("hub_id == @hub_id")
        if len(flagged):
            table(flagged[["agent", "attempts", "returned_attempts", "return_ratio"]], percent=["return_ratio"])
        else:
            st.info("No agents in this hub meet the full-period Q5 screening criteria.")
        section("### Final outcomes of ever-held orders", "Distinct orders, counted once even after repeated holds. Full historical period.")
        held = tables["held_orders"].query("hub_id == @hub_id").iloc[0]
        st.write(f"**{held.ever_held_orders:,}** distinct orders were held at least once.")
        st.write(f"Delivered **{held.delivered_share:.1%}** · Returned **{held.returned_share:.1%}** · Still held **{held.still_held_share:.1%}**")

else:
    st.markdown('<div class="eyebrow">03 / PROJECTED STAFFING & BUDGET</div>', unsafe_allow_html=True)
    st.title("Plan the next four weeks")
    st.markdown('<div class="lede">Compare staffing choices against the service target and a BDT 70,000 incremental budget.</div>', unsafe_allow_html=True)
    scenarios = tables["scenario_comparison"]
    recommended = meta["recommended"]["name"]
    selected = st.selectbox("Scenario", scenarios.scenario.tolist(), index=scenarios.scenario.tolist().index(recommended), key="scenario")
    score = scenarios.query("scenario == @selected").iloc[0]
    plan = tables["weekly_staffing_plan"].query("scenario == @selected and hub_id in @hub_ids")
    metrics = st.columns(4)
    metrics[0].metric("Network budget reserved", money(score.budget_reserved_bdt))
    metrics[1].metric("Network budget remaining", money(score.remaining_budget_bdt))
    metrics[2].metric("Projected hold-charge savings", money(score.direct_hold_cost_savings_bdt))
    metrics[3].metric("Net incremental cash cost", money(score.total_incremental_cash_cost_bdt))
    st.caption("Financial cards are network-wide and use 28 paid days. Savings are projected and do not increase the authorised budget. No incremental revenue is booked.")
    if not score.budget_feasible:
        st.error("This scenario exceeds BDT 70,000 using the payroll reserve. It is a comparison, not an executable budget plan.")
    elif selected == recommended:
        st.success("Recommended: move 2 fixed-salary agents from Lakeview to Greenfield; hire 2 fixed-salary agents at Hillcrest; launch Riverside's hold programme.")
    left, right = st.columns([1.2, 1])
    with left:
        section("### Workload versus target capacity", "Selected clusters · network totals. Surplus in one hub cannot automatically serve another.")
        sums = plan.groupby("week_start", as_index=False)[["baseline_attempts", "required_attempts_after_programme", "baseline_target_capacity", "target_capacity"]].sum()
        labels = {"baseline_attempts": "Baseline attempts", "required_attempts_after_programme": "Attempts after programme",
                  "baseline_target_capacity": "Baseline 85% capacity", "target_capacity": "Scenario 85% capacity"}
        long = sums.rename(columns=labels).melt(id_vars="week_start", var_name="Series", value_name="Attempts")
        fig = px.line(long, x="week_start", y="Attempts", color="Series", markers=True,
                      color_discrete_sequence=[MUTED, TEAL, "#C6B696", AMBER], labels={"week_start": "Week starting"})
        chart(fig, 350)
    with right:
        section("### Where the pressure remains", "Projected attempts / effective standard capacity. New staff start at 60% for seven days.")
        heat = plan.pivot(index="hub_name", columns="forecast_week", values="projected_utilisation")
        fig = go.Figure(go.Heatmap(z=heat.to_numpy()*100, x=[f"Week {w}" for w in heat.columns], y=heat.index,
                                  text=[[f"{v:.1%}" for v in row] for row in heat.to_numpy()],
                                  texttemplate="%{text}", colorscale=[[0, "#DDEEE5"], [.7, "#84B5A3"], [.85, "#EAC482"], [1, "#D46A58"]],
                                  zmin=0, zmax=110, colorbar=dict(title="%"), hovertemplate="%{y} · %{x}<br>%{z:.1f}% utilisation<extra></extra>"))
        chart(fig, 350)
    left, right = st.columns([1.2, 1])
    with left:
        section("### Four-week staffing actions", "Roster counts are whole people; effective capacity includes the initial learning period.")
        actions = plan.groupby("hub_name", as_index=False).agg(existing=("existing_agents", "first"),
                    net_transfers=("net_transfers", "first"), hires=("new_hires", "first"), roster=("roster_agents", "first"), programme=("programme", "first"))
        table(actions)
    with right:
        section("### Budget allocation", "Network-wide one-time costs and new-agent payroll; existing payroll is outside this incremental budget.")
        if selected == recommended:
            allocation = tables["budget_allocation"]
            table(allocation[["item", "amount_bdt"]], currency=["amount_bdt"])
        else:
            table(pd.DataFrame({"item": ["One-time interventions", "New payroll reserve", "Remaining budget"],
                                "amount_bdt": [score.one_time_cost_bdt, score.new_payroll_reserve_bdt, score.remaining_budget_bdt]}), currency=["amount_bdt"])
    section("### Compare the alternatives", "Network service objective: minimise daily hub queues under a strict 85% planning cap. This is separate from the 100% workload limit.")
    display_scenarios = scenarios.assign(priority=scenarios.scenario.map(lambda name: 0 if name == selected else (1 if name.startswith("Baseline") else 2))).sort_values(["priority", "budget_reserved_bdt"])
    table(display_scenarios[["scenario", "budget_feasible", "budget_reserved_bdt", "direct_hold_cost_savings_bdt", "planning_backlog_attempt_days", "end_planning_backlog", "end_hard_backlog"]],
          currency=["budget_reserved_bdt", "direct_hold_cost_savings_bdt"])
    with st.expander("Weekly hub detail and forecast orders"):
        table(plan[["hub_name", "week_start", "forecast_orders", "baseline_attempts", "required_attempts_after_programme", "target_capacity", "projected_utilisation", "target_gap", "planning_backlog_week_end", "hard_backlog_week_end"]], percent=["projected_utilisation"])
    with st.expander("Payroll, ramp and downside sensitivities"):
        st.write("These cases apply to the recommended plan unless explicitly marked re-optimised. Base: 28 paid days; zero programme benefit for 14 days, then 50% of agent-side holds removed. Avoided retries affect the following day.")
        table(tables["sensitivity_analysis"][["sensitivity", "budget_reserved_bdt", "remaining_budget_bdt", "direct_hold_cost_savings_bdt", "end_planning_backlog", "end_hard_backlog", "direct_cash_roi"]], percent=["direct_cash_roi"], currency=["budget_reserved_bdt", "remaining_budget_bdt", "direct_hold_cost_savings_bdt"])
    with st.expander("First-14-day risk controls"):
        table(tables["risk_register"][["risk", "kpi", "threshold", "frequency", "owner", "mitigation"]])
    st.info("Service investment, not a proven revenue uplift. Avoided hold charges are counted once. Freed attempts are capacity, not a second cash saving. Daily demand is assumed uniform within each forecast week; no extra revenue, return savings or overtime is booked.")

st.markdown('<div class="footnote">CarryBee Express · Assessment snapshot · BDT throughout · Historical results independently validated; intervention benefits are projections.</div>', unsafe_allow_html=True)
