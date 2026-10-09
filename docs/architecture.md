# BoreWise System Architecture

BoreWise is a groundwater monitoring, recovery analytics, and quantile risk forecasting platform designed for agricultural cooperatives, housing societies, and borewell operators.

## Data Pipeline Flow

```
+---------------------------+       +------------------------------------+
|  Telemetry Generators     |       |  AWS Ingestion & API Layer         |
|                           |       |                                    |
| 1. Python Simulator       | ----> |  Lambda Function URL / API Gateway |
|    (Normal / Weak / Over) |       |                 |                  |
| 2. ESP32 Bench Prototype  |       |    JSON Schema Validation (400)    |
|    (Wi-Fi HTTP POST)      |       |                 |                  |
+---------------------------+       +------------------------------------+
                                                      |
                                                      v
                                        +----------------------------+
                                        |  Persistence Store         |
                                        |                            |
                                        |  AWS DynamoDB / Local      |
                                        |  (PartitionKey: well_id    |
                                        |   SortKey: timestamp)      |
                                        +----------------------------+
                                                      |
                                                      v
                                        +----------------------------+
                                        |  Streamlit Dashboard       |
                                        |                            |
                                        |  - Drawdown & Recovery     |
                                        |  - P10/P50/P90 Forecasts   |
                                        |  - Plain-English Alerts    |
                                        +----------------------------+
```

## Component Architecture

### 1. Telemetry Ingestion Layer (`backend/app.py` & `backend/schema.py`)
- **Validation Engine:** Enforces physical bounds (Depth: 0–300m, Temp: -10 to 80°C), ISO8601 timestamps, valid data source provenance tags, and strict JSON keys.
- **AWS Lambda Handler:** Stateless serverless entry point supporting CORS header responses (`OPTIONS`, `POST`, `GET`).
- **Storage Layer:** DynamoDB table (`BoreWiseTelemetry`) with fail-safe local in-memory fallback for offline demo.

### 2. Simulator & Analytical Engine (`simulator/simulator.py` & `simulator/forecast.py`)
- **Physics-Inspired Model:** Mass-balance drawdown during pumping coupled with exponential aquifer recovery $dS/dt = -k \cdot (S - S_0)$.
- **Recovery Analytics:** Calculates cycle drawdowns, post-pumping recovery percentages, and recovery rates ($m/\text{hr}$).
- **Quantile Forecasting Engine:** Stochastic trajectory simulation generating P10 (optimistic 10th percentile), P50 (median baseline), and P90 (pessimistic 90th percentile) projections over a 12–168 hour horizon.

### 3. Streamlit Executive Dashboard (`dashboard/app.py`)
- **Interactive UI:** Real-time scenario switching (`normal`, `weak_recharge`, `over_pumping`), configurable threshold controls, Plotly depth charts with pump-state shading, quantile projections, AWS API POST dispatcher, and CSV dataset export.
