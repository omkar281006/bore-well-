# 💧 BoreWise: Groundwater Monitoring & Risk Analytics MVP

BoreWise is an IoT-enabled groundwater monitoring, drawdown diagnosis, and quantile risk forecasting platform designed for agricultural cooperatives, housing societies, and borewell operators.

## 🎯 Project Overview & MVP Scope

BoreWise converts borewell telemetry into actionable pumping recommendations following a 5-step pipeline:

$$\text{Measure} \longrightarrow \text{Diagnose} \longrightarrow \text{Predict} \longrightarrow \text{Protect} \longrightarrow \text{Explain}$$

1. **Measure:** Collect telemetry via simulated physics-inspired time-series or ESP32 bench-tested prototype.
2. **Diagnose:** Calculate water drawdown depth during pumping and post-pumping exponential aquifer recovery.
3. **Predict:** Compute stochastic P10, P50, and P90 quantile forecast trajectories to estimate threshold crossing horizons.
4. **Protect:** Issue risk level diagnoses (`Normal`, `Warning`, `High Risk`) to prevent dry-pump damage and aquifer depletion.
5. **Explain:** Translate risk metrics into plain-language diagnostic explanations and actionable pump management advice.

---

## 🏗️ Repository Architecture

```text
borewise/
├── simulator/
│   ├── __init__.py
│   ├── simulator.py     # Physics-inspired mass balance drawdown & recovery simulator
│   └── forecast.py      # Drawdown analytics & P10/P50/P90 quantile risk forecaster
├── backend/
│   ├── __init__.py
│   ├── schema.py        # Shared telemetry schema & JSON boundary validation logic
│   ├── app.py           # AWS Lambda handler & local HTTP ingestion server
│   └── requirements.txt
├── dashboard/
│   └── app.py           # Streamlit engineering dashboard & interactive UI
├── firmware/
│   └── esp32/
│       ├── main.cpp     # ESP32 C++ Arduino firmware for Wi-Fi HTTP telemetry dispatch
│       └── README.md
├── tests/
│   ├── test_simulator.py
│   ├── test_forecast.py
│   └── test_backend.py
├── docs/
│   ├── architecture.md     # Pipeline flow & component breakdown
│   ├── telemetry-schema.md # Data field dictionary & boundary constraints
│   └── limitations.md     # R&D assessment & honest field vs bench evaluation
├── data/
│   └── sample_readings.csv # Default 72-hour simulated telemetry dataset
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 📊 Implementation & Component Status Matrix

| Component | Status | Implementation Details |
|---|---|---|
| **Physics Simulator** | ✅ Implemented & Tested | Supports 3 scenarios (`normal`, `weak_recharge`, `over_pumping`) |
| **Recovery Analytics** | ✅ Implemented & Tested | Computes cycle drawdown, recovery %, and recovery rate ($m/\text{hr}$) |
| **Risk Forecasting** | ✅ Implemented & Tested | Stochastic P10 (optimistic), P50 (median), P90 (pessimistic) quantiles |
| **Ingestion Backend API** | ✅ Implemented & Tested | AWS Lambda handler + local HTTP server with strict schema validation |
| **Streamlit Dashboard** | ✅ Implemented & Tested | Plotly charts, threshold controls, risk badges & AWS dispatcher |
| **ESP32 Firmware** | ✅ Implemented Prototype | Wi-Fi HTTP POST telemetry client for bench-testing |
| **AWS DynamoDB Integration**| ✅ Implemented | AWS boto3 table integration with local in-memory fallback |
| **Automated Tests** | ✅ 9/9 Passed | Unit tests for simulation, schema validation, analytics, & API |

---

## 🚀 Quick Start & Local Execution

### 1. Prerequisites & Installation

Ensure Python 3.10+ is installed. Clone the repository and install dependencies:

```bash
git clone https://github.com/omkarbachhav24-ux/borewise.git
cd borewise
pip install -r requirements.txt
```

### 2. Generate Sample Telemetry Dataset

```bash
python simulator/simulator.py
```
*Output: Generates 72 hours of simulated 15-minute resolution telemetry in `data/sample_readings.csv`.*

### 3. Run Ingestion API Backend (Optional Local Server)

```bash
python backend/app.py
```
*Runs ingestion API at `http://localhost:8000/telemetry` accepting POST telemetry and GET queries.*

### 4. Launch Streamlit Engineering Dashboard

```bash
streamlit run dashboard/app.py
```
*Opens interactive dashboard at `http://localhost:8501`.*

### 5. Run Automated Test Suite

```bash
python -m pytest tests/ -v
```

---

## 🎬 Hackathon Demonstration Walkthrough

1. **Dashboard Overview:** Launch dashboard at `http://localhost:8501`. Observe default `BW-001` well status and data source provenance badge (`SIMULATED`).
2. **Scenario Switching:**
   - Select **Normal Operation**: Water level drawdowns during pumping and fully recovers. Risk status displays `Normal`.
   - Select **Weak Recharge**: Recovery rate slows, leaving cumulative residual drawdown. Risk status shifts to `Warning`.
   - Select **Over-Pumping**: Continuous pump runs cause severe drawdown. Risk status triggers `High Risk` with P90 threshold breach warning.
3. **AWS Ingestion Test:**
   - Navigate to **AWS Backend Ingestion** tab in dashboard.
   - Click **Send Telemetry**. Confirm HTTP 201 success response.
   - Modify payload depth to `999.0m` (out of bounds) and click Send. Confirm HTTP 400 rejection with validation error details.

---

## 👥 Team Task Allocation

- **Member 1 (Simulation & Forecast):** `simulator/simulator.py`, `simulator/forecast.py`, stochastic quantile models.
- **Member 2 (AWS Backend):** `backend/app.py`, `backend/schema.py`, AWS Lambda handler & DynamoDB persistence.
- **Member 3 (Dashboard & UX):** `dashboard/app.py`, Plotly telemetry charts, recovery analytics & risk UI.
- **Member 4 (Hardware & QA):** `firmware/esp32/`, automated pytest suite (`tests/`), documentation & field assessment.
