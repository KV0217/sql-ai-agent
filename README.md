# 🤖 SQL AI Agent — Natural Language to SQL

> Ask business questions in plain English. Gemini AI writes the SQL, runs it against real data, and gives you a business insight — all in seconds.

## Live Deployments
| | URL |
|--|--|
| **REST API** | https://sql-ai-agent-kv.onrender.com |
| **API Docs** | https://sql-ai-agent-kv.onrender.com/docs |
| **Streamlit App** | https://sql-ai-agent-kv.streamlit.app |

> ⚡ Free tier — first request may take 30s to wake up

---

## 🎯 What It Does

```
User: "Which region had the highest profit in 2023?"
         ↓
Agent writes:  SELECT Region, ROUND(SUM(Profit),2) AS Total_Profit
               FROM superstore
               WHERE Order_Date_Year = 2023
               GROUP BY Region ORDER BY Total_Profit DESC LIMIT 10
         ↓
Executes query → Returns data table + bar chart
         ↓
AI Insight: "The West region generated the highest profit at $87,214
             in 2023, outperforming the East by 23%..."
         ↓
Logs query + result → AWS S3 (audit trail)
```

---

## 📊 Dataset

**Superstore Sales** — 9,994 orders × 21 features
- Sales, Profit, Discount, Quantity
- Category, Sub-Category, Region, State, Segment
- Order Date (2021–2024)

---

## 🔥 What Makes This Different

- **Gen AI + SQL** — LLM generates and validates SQL from plain English
- **Real execution** — not mock data, actual query runs on SQLite
- **Business insights** — Gemini explains what the numbers mean
- **AWS S3 logging** — every query archived with timestamp, SQL, and results
- **Production API** — FastAPI with `/query`, `/schema`, `/examples` endpoints
- **Auto chart** — bar, line, or scatter based on result shape
- **Safety layer** — blocks all write operations (INSERT/UPDATE/DELETE/DROP)

---

## 🏗️ Architecture

```
┌──────────────────┐    ┌────────────────────┐    ┌─────────────────┐
│   Streamlit UI   │───▶│   Agent Pipeline   │───▶│  Gemini 1.5     │
│  (app.py)        │    │  (agent.py)        │    │  Flash (LLM)    │
└──────────────────┘    └────────────────────┘    └─────────────────┘
         │                       │                         │
         ▼                       ▼                         ▼
┌──────────────────┐    ┌────────────────────┐    ┌─────────────────┐
│   FastAPI REST   │    │   SQLite Database  │    │   AWS S3        │
│   (api.py)       │    │   (superstore.db)  │    │   Query Logs    │
└──────────────────┘    └────────────────────┘    └─────────────────┘
```

---

## ⚡ Quick Start

```bash
# 1. Clone
git clone https://github.com/KV0217/sql-ai-agent.git
cd sql-ai-agent

# 2. Install
pip install -r requirements.txt

# 3. Add your Gemini API key (free at aistudio.google.com)
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# 4. Build database
python setup_db.py

# 5. Run Streamlit app
streamlit run app.py

# OR run FastAPI
uvicorn api:app --reload
```

---

## 🔌 API Usage

```python
import requests

response = requests.post(
    "https://sql-ai-agent-kv.onrender.com/query",
    json={"question": "Which sub-category has the highest average discount?"}
)
print(response.json())
```

**Response:**
```json
{
  "status": "success",
  "question": "Which sub-category has the highest average discount?",
  "sql": "SELECT Sub_Category, ROUND(AVG(Discount)*100,1) AS Avg_Discount_Pct FROM superstore GROUP BY Sub_Category ORDER BY Avg_Discount_Pct DESC LIMIT 10",
  "rows_returned": 10,
  "insight": "Binders have the highest average discount at 42.3%, nearly double the dataset average of 15.6%. This excessive discounting likely contributes to their negative profit margins.",
  "chart_type": "bar",
  "elapsed_seconds": 1.84,
  "s3_status": "✅ Logged to s3://kv-sql-agent/sql-agent-logs/20240817_121530.json",
  "data": [...]
}
```

---

## 💬 Example Questions You Can Ask

| Question | Type |
|----------|------|
| Which region had the highest profit? | Aggregation |
| Show top 10 customers by revenue | Ranking |
| Which sub-categories are loss-making? | Filter |
| Monthly sales trend in 2023 | Time series |
| What is the impact of discount on profit? | Correlation |
| Compare segments: Consumer vs Corporate | Comparison |
| Which states have the most orders? | Geographic |
| Year-over-year sales growth | Growth |

---

## 🛡️ Safety

- Only `SELECT` queries allowed — all write operations blocked
- Input sanitisation before SQL execution
- Query timeout: 30 seconds
- Max rows returned: 500

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Google Gemini 1.5 Flash |
| Database | SQLite (via Pandas + sqlite3) |
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit + Plotly |
| Cloud | AWS S3 (Boto3) |
| Deploy | Render (API) + Streamlit Cloud (App) |
| Container | Docker |

---

## 👨‍💻 Author

**Kavin Venkat** — Data Analyst / Junior Data Scientist
- 📧 kavinvenkat1980@gmail.com
- 🔗 [LinkedIn](https://www.linkedin.com/in/kvsherly17100210)
- 🐙 [GitHub](https://github.com/KV0217)
