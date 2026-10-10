"""
BoreWise Streamlit Engineering Dashboard

Monitors groundwater drawdown, evaluates recovery metrics, and renders 
quantile-based risk forecasts (P10, P50, P90) with plain-language recommendations.
"""

import os
import sys
import json
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # run from any folder

from simulator.simulator import BorewellSimulator
from simulator.forecast import analyze_drawdown_and_recovery, forecast_water_level_risk
from backend.schema import validate_telemetry_payload

# Configure Page Layout & Styling
st.set_page_config(
    page_title="BoreWise Groundwater Monitor",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Engineering Dashboard
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .badge-simulated {
        background-color: #E0F2FE;
        color: #0369A1;
        padding: 4px 12px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        border: 1px solid #BAE6FD;
    }
    .badge-bench {
        background-color: #FEF3C7;
        color: #B45309;
        padding: 4px 12px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        border: 1px solid #FDE68A;
    }
    .badge-field {
        background-color: #DCFCE7;
        color: #15803D;
        padding: 4px 12px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        border: 1px solid #BBF7D0;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-title {
        font-size: 0.85rem;
        color: #64748B;
        font-weight: 500;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0F172A;
    }
</style>
""", unsafe_allow_html=True)


# --- Helper Data Loaders ---
@st.cache_data(ttl=60)
def load_simulated_data(scenario: str, hours: int) -> pd.DataFrame:
    sim = BorewellSimulator(well_id="BW-001", baseline_depth_m=40.0)
    return sim.generate_series(scenario=scenario, duration_hours=hours, interval_minutes=15)


def load_local_csv() -> pd.DataFrame:
    if os.path.exists("data/sample_readings.csv"):
        return pd.read_csv("data/sample_readings.csv")
    else:
        return load_simulated_data("normal", 72)


# --- Sidebar Controls ---
st.sidebar.image("https://img.icons8.com/isometric/96/water.png", width=64)
st.sidebar.title("BoreWise Controls")

data_mode = st.sidebar.radio(
    "Data Source Mode",
    ["Python Simulator", "Local Sample CSV", "AWS Endpoint / Local API"],
    index=0
)

well_id_input = st.sidebar.text_input("Borewell ID", value="BW-001")
threshold_depth = st.sidebar.number_input("Risk Threshold Depth (m)", min_value=10.0, max_value=200.0, value=55.0, step=1.0)
forecast_horizon_input = st.sidebar.slider("Forecast Horizon (Hours)", min_value=12, max_value=168, value=48, step=12)

df_telemetry = pd.DataFrame()

if data_mode == "Python Simulator":
    scenario_choice = st.sidebar.selectbox(
        "Simulation Scenario",
        ["normal", "weak_recharge", "over_pumping", "fracture", "interf", "clog", "wear", "dry", "sensor"],
        format_func=lambda x: {
            "normal": "Normal Operation (Sustainable)",
            "weak_recharge": "Weak Recharge (Slow Recovery)",
            "over_pumping": "Over-Pumping (Depleting Aquifer)",
            "fracture": "Fracture Dewatering",
            "interf": "Neighbour Interference",
            "clog": "Well Clogging",
            "wear": "Pump Wear",
            "dry": "Dry Running",
            "sensor": "Sensor Fault (false echo)",
        }[x]
    )
    sim_hours = st.sidebar.slider("Historical Data Span (Hours)", 24, 168, 72, 24)
    df_telemetry = load_simulated_data(scenario_choice, sim_hours)
    df_telemetry["well_id"] = well_id_input

elif data_mode == "Local Sample CSV":
    df_telemetry = load_local_csv()
    df_telemetry["well_id"] = well_id_input

elif data_mode == "AWS Endpoint / Local API":
    api_url = st.sidebar.text_input("API URL", value="http://localhost:8000/telemetry")
    # Streamlit reruns the script on every click, so keep fetched data in session state.
    if st.sidebar.button("Fetch Live Telemetry"):
        try:
            res = requests.get(api_url, params={"well_id": well_id_input, "limit": 1000}, timeout=10)
            if res.status_code == 200:
                items = res.json().get("telemetry", [])
                if items:
                    st.session_state["api_df"] = pd.DataFrame(items)
                    st.sidebar.success(f"Fetched {len(items)} records!")
                else:
                    st.sidebar.warning("No records returned from API. Showing the simulator instead.")
            else:
                st.sidebar.error(f"API Error {res.status_code}. Showing the simulator instead.")
        except Exception as e:
            st.sidebar.error(f"Failed to connect to API: {e}. Showing the simulator instead.")
    df_telemetry = st.session_state.get("api_df", load_simulated_data("normal", 72))

# --- Header & Overview ---
st.markdown('<div class="main-header">BoreWise: Groundwater Monitoring & Risk Analytics</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Physics-Inspired Borewell Drawdown Diagnosis, Quantile Forecasting & AWS Ingestion</div>', unsafe_allow_html=True)

if df_telemetry.empty:
    st.error("No telemetry data loaded.")
    st.stop()

# Ensure timestamp parsing
df_telemetry["timestamp"] = pd.to_datetime(df_telemetry["timestamp"])
df_telemetry = df_telemetry.sort_values("timestamp").reset_index(drop=True)

latest = df_telemetry.iloc[-1]
# While the pump runs the sounding is gated, so use the last valid depth.
_valid = df_telemetry[df_telemetry["depth_to_water_m"].notna() & (df_telemetry.get("measurement_valid", True) == True)]
current_depth = float((_valid if len(_valid) else df_telemetry)["depth_to_water_m"].dropna().iloc[-1])
current_pump = str(latest["pump_state"])
data_source_label = str(latest.get("data_source", "simulated"))

# Calculate Recovery & Risk Analysis
recovery_stats = analyze_drawdown_and_recovery(df_telemetry)
risk_forecast = forecast_water_level_risk(
    df_telemetry,
    threshold_depth_m=threshold_depth,
    forecast_hours=forecast_horizon_input
)

# Badge HTML depending on data source category
if data_source_label == "field-measured":
    source_badge = '<span class="badge-field">FIELD-MEASURED</span>'
elif data_source_label == "bench-tested":
    source_badge = '<span class="badge-bench">BENCH-TESTED</span>'
else:
    source_badge = '<span class="badge-simulated">SIMULATED (Physics Model)</span>'

# Overview Columns
col_well, col_depth, col_pump, col_risk, col_source = st.columns(5)

with col_well:
    st.markdown('<div class="metric-card"><div class="metric-title">Borewell ID</div>'
                f'<div class="metric-value">{latest["well_id"]}</div></div>', unsafe_allow_html=True)

with col_depth:
    st.markdown('<div class="metric-card"><div class="metric-title">Current Water Depth</div>'
                f'<div class="metric-value">{current_depth:.1f} m</div></div>', unsafe_allow_html=True)

with col_pump:
    pump_color = "#16A34A" if current_pump == "OFF" else "#DC2626"
    st.markdown('<div class="metric-card"><div class="metric-title">Pump Status</div>'
                f'<div class="metric-value" style="color: {pump_color}">{current_pump}</div></div>', unsafe_allow_html=True)

with col_risk:
    r_level = risk_forecast["risk_level"]
    r_color = "#16A34A" if r_level == "Normal" else ("#D97706" if r_level == "Warning" else "#DC2626")
    st.markdown('<div class="metric-card"><div class="metric-title">Risk Diagnosis</div>'
                f'<div class="metric-value" style="color: {r_color}">{r_level}</div></div>', unsafe_allow_html=True)

with col_source:
    st.markdown(f'<div class="metric-card"><div class="metric-title">Data Provenance</div>'
                f'<div style="margin-top: 10px;">{source_badge}</div></div>', unsafe_allow_html=True)

st.divider()

# --- Tabs for Detailed Views ---
tab_depth, tab_recovery, tab_forecast, tab_aws, tab_qa = st.tabs([
    "📈 Water Level Telemetry",
    "🔄 Recovery Analytics",
    "🔮 Risk Forecast (P10/P50/P90)",
    "☁️ AWS Backend Ingestion",
    "🛡️ Data Quality & Audit"
])

# TAB 1: Water Level Chart
with tab_depth:
    st.subheader("Borewell Water Level Drawdown Over Time")
    st.caption("Depth to water measured in metres from top of well casing. Lower curves (higher depth values) represent deeper water drawdown.")

    fig = go.Figure()

    # Plot depth curve
    fig.add_trace(go.Scatter(
        x=df_telemetry["timestamp"],
        y=df_telemetry["depth_to_water_m"],
        mode="lines",
        name="Depth to Water (m)",
        line=dict(color="#0284C7", width=2.5)
    ))

    # Add threshold line
    fig.add_hline(
        y=threshold_depth,
        line_dash="dash",
        line_color="#EF4444",
        annotation_text=f"Risk Threshold ({threshold_depth}m)",
        annotation_position="bottom right"
    )

    # Shading for Pumping ON periods
    pump_on_dfs = df_telemetry[df_telemetry["pump_state"] == "ON"]
    if not pump_on_dfs.empty:
        fig.add_trace(go.Scatter(
            x=pump_on_dfs["timestamp"],
            y=pump_on_dfs["depth_to_water_m"],
            mode="markers",
            name="Pump Active (ON)",
            marker=dict(color="#DC2626", size=6, symbol="circle")
        ))

    fig.update_layout(
        xaxis_title="Timestamp (UTC)",
        yaxis_title="Depth to Water (metres from top)",
        yaxis=dict(autorange="reversed"),  # Invert so baseline water surface is at top, deeper water goes down
        template="plotly_white",
        height=450,
        margin=dict(l=40, r=40, t=30, b=40)
    )

    st.plotly_chart(fig, use_container_width=True)


# TAB 2: Recovery Analytics
with tab_recovery:
    st.subheader("Aquifer Recovery & Drawdown Diagnostic Analytics")
    
    col_rec1, col_rec2, col_rec3, col_rec4 = st.columns(4)
    col_rec1.metric("Pumping Cycles Analyzed", recovery_stats["total_cycles"])
    col_rec2.metric("Avg Cycle Drawdown", f"{recovery_stats['avg_drawdown_m']} m")
    col_rec3.metric("Avg Post-Pump Recovery %", f"{recovery_stats['avg_recovery_pct']}%")
    col_rec4.metric("Avg Recovery Rate", f"{recovery_stats['avg_recovery_rate_m_per_hr']} m/hr")

    st.markdown("#### Pumping Cycle Detail Audit")
    if recovery_stats["cycle_details"]:
        df_cycles = pd.DataFrame(recovery_stats["cycle_details"])
        st.dataframe(df_cycles, use_container_width=True)
    else:
        st.info("No completed pumping and recovery cycles detected in the current time frame.")


# TAB 3: Risk Forecast & Quantiles
with tab_forecast:
    st.subheader(f"Quantile Risk Forecast Horizon ({forecast_horizon_input} Hours)")
    st.markdown("""
    * **P10 (Optimistic):** 10th percentile depth (shallower drawdown, high recharge assumption).
    * **P50 (Median):** 50th percentile projected trajectory (baseline expectation).
    * **P90 (Pessimistic):** 90th percentile depth (deepest drawdown, elevated risk scenario).
    """)

    # Render alert banner based on risk level
    if risk_forecast["risk_level"] == "High Risk":
        st.error(f"🚨 **HIGH RISK WARNING:** {risk_forecast['explanation']}")
    elif risk_forecast["risk_level"] == "Warning":
        st.warning(f"⚠️ **ELEVATED RISK ADVISORY:** {risk_forecast['explanation']}")
    else:
        st.success(f"✅ **NORMAL OPERATION:** {risk_forecast['explanation']}")

    st.info(f"💡 **Recommended Action:** {risk_forecast['recommendation']}")

    # Plot forecast trajectories
    if risk_forecast["forecast_times"]:
        fc_fig = go.Figure()

        # Last historical depth point to connect historical with forecast
        last_hist_time = df_telemetry["timestamp"].iloc[-1].strftime("%Y-%m-%dT%H:%M:%SZ")
        last_hist_depth = current_depth

        times = [last_hist_time] + risk_forecast["forecast_times"]
        p10s = [last_hist_depth] + risk_forecast["p10_series"]
        p50s = [last_hist_depth] + risk_forecast["p50_series"]
        p90s = [last_hist_depth] + risk_forecast["p90_series"]

        # P90 Pessimistic
        fc_fig.add_trace(go.Scatter(
            x=times, y=p90s, mode="lines", name="P90 (Pessimistic)",
            line=dict(color="#EF4444", dash="dot", width=2)
        ))

        # P50 Median
        fc_fig.add_trace(go.Scatter(
            x=times, y=p50s, mode="lines", name="P50 (Median)",
            line=dict(color="#3B82F6", width=3)
        ))

        # P10 Optimistic
        fc_fig.add_trace(go.Scatter(
            x=times, y=p10s, mode="lines", name="P10 (Optimistic)",
            line=dict(color="#10B981", dash="dot", width=2)
        ))

        fc_fig.add_hline(
            y=threshold_depth, line_dash="dash", line_color="#EF4444",
            annotation_text=f"Threshold ({threshold_depth}m)"
        )

        fc_fig.update_layout(
            xaxis_title="Forecast Timestamp",
            yaxis_title="Depth to Water (metres)",
            yaxis=dict(autorange="reversed"),
            template="plotly_white",
            height=420
        )

        st.plotly_chart(fc_fig, use_container_width=True)


# TAB 4: AWS Backend Ingestion
with tab_aws:
    st.subheader("AWS Cloud Ingestion & Telemetry Dispatcher")
    st.markdown("""
    Demonstrates ingestion pipeline:  
    `ESP32 / Python Simulator ➔ AWS API Gateway / Lambda Function URL ➔ Validation ➔ DynamoDB`
    """)

    col_send1, col_send2 = st.columns(2)

    with col_send1:
        st.markdown("##### Dispatch Telemetry Record")
        target_api = st.text_input("Ingestion Endpoint URL", value="http://localhost:8000/telemetry")
        
        sample_payload = {
            "well_id": well_id_input,
            "timestamp": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data_source": "simulated",
            "depth_to_water_m": current_depth,
            "temperature_c": 27.5,
            "pump_state": current_pump,
            "pump_run_minutes": 30 if current_pump == "ON" else 0,
            "measurement_valid": True,
            "pump_current_a": 5.6 if current_pump == "ON" else 0.0,
        }
        
        payload_text = st.text_area("JSON Telemetry Payload", value=json.dumps(sample_payload, indent=2), height=200)

        if st.button("🚀 Send Telemetry to Ingestion Endpoint"):
            try:
                body_json = json.loads(payload_text)
                res = requests.post(target_api, json=body_json, timeout=5)
                if res.status_code in (200, 201):
                    st.success(f"Response ({res.status_code}): {res.text}")
                else:
                    st.error(f"API Error ({res.status_code}): {res.text}")
            except Exception as e:
                st.error(f"Failed to post telemetry: {e}")

    with col_send2:
        st.markdown("##### AWS Architecture Summary")
        st.code("""
Architecture Pipeline:
- HTTP API: API Gateway (backend/template.yaml)
- Lambda: Python 3.12, one router for /telemetry, /telemetry/batch, /wells, /wells/{id}
- Persistence: DynamoDB (Partition Key: well_id, Sort Key: timestamp UTC)
- Analysis: backend/analysis.py (refill fit, dry-up forecast, findings)
- Web app: frontend/ (3D) reads GET /wells/{id}; this dashboard reads GET /telemetry
        """, language="yaml")


# TAB 5: Data Quality & Audit
with tab_qa:
    st.subheader("Telemetry Audit & Data Quality Check")

    valid_count = len(df_telemetry[df_telemetry["measurement_valid"] == True])
    invalid_count = len(df_telemetry[df_telemetry["measurement_valid"] == False])

    st.markdown(f"**Total Records:** {len(df_telemetry)} | **Valid:** {valid_count} | **Invalid/Rejected:** {invalid_count}")
    
    st.dataframe(df_telemetry.tail(20), use_container_width=True)

    csv_data = df_telemetry.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Telemetry CSV",
        data=csv_data,
        file_name=f"borewise_{well_id_input}_telemetry.csv",
        mime="text/csv"
    )
