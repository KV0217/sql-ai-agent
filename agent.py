"""
agent.py — Core SQL AI Agent using Gemini + SQLite
"""
import os
import sqlite3
import re
import time
import json
from datetime import datetime
from typing import Optional

import pandas as pd
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from google import genai

from config import (
    GEMINI_API_KEY, GEMINI_MODEL, DB_PATH,
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
    S3_BUCKET, S3_PREFIX, MAX_ROWS
)

# -- Gemini client (lazy-loaded on first use) ---------------------------------
_client = None

def get_client():
    global _client
    if _client is None:
        key = GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        _client = genai.Client(api_key=key)
    return _client


def call_gemini(prompt: str, retries: int = 3) -> str:
    """Call Gemini with automatic retry on SSL/network errors."""
    last_error = None
    for attempt in range(retries):
        try:
            response = get_client().models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            last_error = e
            err = str(e).lower()
            if any(x in err for x in ["ssl", "connection", "timeout", "network", "record layer"]):
                wait = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait)
                # Reset client on SSL error so it reconnects fresh
                _client = None
                continue
            else:
                raise  # Non-network error — raise immediately
    raise RuntimeError(f"Gemini API failed after {retries} attempts: {last_error}")


# ── Schema loader ─────────────────────────────────────────────────────────────
def get_schema() -> str:
    """Returns full schema of the superstore table as a string."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(superstore)")
    columns = cursor.fetchall()

    cursor.execute("SELECT MIN(Order_Date), MAX(Order_Date) FROM superstore")
    date_range = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM superstore")
    total_rows = cursor.fetchone()[0]

    cursor.execute("SELECT DISTINCT Region FROM superstore")
    regions = [r[0] for r in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT Category FROM superstore")
    categories = [r[0] for r in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT Segment FROM superstore")
    segments = [r[0] for r in cursor.fetchall()]

    conn.close()

    col_list = "\n".join([f"  - {col[1]} ({col[2]})" for col in columns])

    schema = f"""
DATABASE: superstore.db
TABLE: superstore
TOTAL ROWS: {total_rows:,}
DATE RANGE: {date_range[0]} to {date_range[1]}
REGIONS: {', '.join(str(r) for r in regions)}
CATEGORIES: {', '.join(str(c) for c in categories)}
SEGMENTS: {', '.join(str(s) for s in segments)}

COLUMNS:
{col_list}

VIEWS AVAILABLE:
  - regional_summary  (Region, Category, Total_Sales, Total_Profit, Avg_Discount_Pct, Orders)
  - customer_summary  (Customer_ID, Customer_Name, Segment, Total_Orders, Total_Revenue, Total_Profit)

IMPORTANT RULES:
  - Always use column names exactly as listed (underscores, not spaces)
  - For date filtering use Order_Date_Year or Order_Date_Month columns
  - Discount is stored as decimal (0.2 = 20%)
  - Profit can be negative (loss-making orders)
  - Use ROUND() for monetary values
  - Use LIMIT {MAX_ROWS} on all queries
"""
    return schema.strip()


# ── SQL generator (Gemini) ────────────────────────────────────────────────────
def generate_sql(user_question: str, schema: str) -> str:
    """Uses Gemini to generate a safe SQL query from a natural language question."""

    prompt = f"""
You are an expert SQL analyst working with a retail Superstore SQLite database.

SCHEMA:
{schema}

USER QUESTION:
{user_question}

TASK:
Generate a single, correct SQLite SQL query that answers the question.

STRICT RULES:
1. Return ONLY the SQL query — no explanation, no markdown, no code fences
2. Use exact column names from schema (with underscores)
3. Always include LIMIT {MAX_ROWS}
4. Only use SELECT statements — never INSERT, UPDATE, DELETE, DROP
5. Use ROUND(value, 2) for all monetary columns
6. For "top N" questions, use ORDER BY ... DESC LIMIT N
7. For year/month filters, use Order_Date_Year or Order_Date_Month
8. If question is ambiguous, answer the most useful interpretation

SQL QUERY:
"""

    raw = call_gemini(prompt)

    # Clean up any accidental markdown fencing
    raw = re.sub(r"```sql|```", "", raw, flags=re.IGNORECASE).strip()

    # Safety check — block write operations
    forbidden = ["insert", "update", "delete", "drop", "alter", "create", "truncate"]
    if any(kw in raw.lower() for kw in forbidden):
        raise ValueError("⛔ Generated SQL contains forbidden operation. Blocked.")

    return raw


# ── SQL executor ──────────────────────────────────────────────────────────────
def execute_sql(sql: str) -> pd.DataFrame:
    """Executes the SQL and returns a DataFrame."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(sql, conn)
        return df
    except Exception as e:
        raise RuntimeError(f"SQL Execution Error: {e}\n\nSQL:\n{sql}")
    finally:
        conn.close()


# ── Insight generator (Gemini) ────────────────────────────────────────────────
def generate_insight(user_question: str, sql: str, df: pd.DataFrame) -> str:
    """Uses Gemini to generate a business insight from the results."""

    if df.empty:
        return "⚠️ The query returned no results. Try rephrasing your question."

    # Summarise the data for the prompt (avoid huge payloads)
    sample = df.head(10).to_string(index=False)
    stats = f"Rows returned: {len(df)}"

    prompt = f"""
You are a senior data analyst. A business user asked a question and you ran a SQL query.
Provide a concise, insightful answer in 2-4 sentences. Be specific with numbers.
Use business language — avoid technical jargon.

USER QUESTION: {user_question}

SQL RESULT ({stats}):
{sample}

BUSINESS INSIGHT:
"""

    return call_gemini(prompt)


# ── Chart type recommender ────────────────────────────────────────────────────
def recommend_chart(df: pd.DataFrame) -> str:
    """Heuristically recommends best chart type based on data shape."""
    if df.empty or len(df.columns) < 2:
        return "table"

    num_rows = len(df)
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(exclude="number").columns.tolist()

    if len(num_cols) == 0:
        return "table"
    if len(cat_cols) >= 1 and len(num_cols) >= 1:
        if num_rows <= 10:
            return "bar"
        elif num_rows <= 30:
            return "line"
        else:
            return "scatter"
    return "table"


# ── AWS S3 logger ──────────────────────────────────────────────────────────────
def log_to_s3(payload: dict) -> str:
    """Archives query log to S3. Returns status message."""
    if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET]):
        return "S3 logging skipped (credentials not configured)"

    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        )
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        key = f"{S3_PREFIX}{ts}.json"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(payload, indent=2, default=str),
            ContentType="application/json",
        )
        return f"✅ Logged to s3://{S3_BUCKET}/{key}"
    except NoCredentialsError:
        return "⚠️ S3: Invalid credentials"
    except ClientError as e:
        return f"⚠️ S3 Error: {e.response['Error']['Message']}"
    except Exception as e:
        return f"⚠️ S3 Error: {str(e)}"


# ── Main agent pipeline ───────────────────────────────────────────────────────
def run_agent(user_question: str) -> dict:
    """
    Full pipeline:
    1. Load schema
    2. Generate SQL via Gemini
    3. Execute SQL
    4. Generate business insight via Gemini
    5. Log to S3
    6. Return everything
    """
    start = time.time()
    timestamp = datetime.utcnow().isoformat()

    try:
        # Step 1: Schema
        schema = get_schema()

        # Step 2: Generate SQL
        sql = generate_sql(user_question, schema)

        # Step 3: Execute
        df = execute_sql(sql)

        # Step 4: Insight
        insight = generate_insight(user_question, sql, df)

        # Step 5: Chart recommendation
        chart_type = recommend_chart(df)

        elapsed = round(time.time() - start, 2)

        result = {
            "status": "success",
            "question": user_question,
            "sql": sql,
            "rows_returned": len(df),
            "insight": insight,
            "chart_type": chart_type,
            "elapsed_seconds": elapsed,
            "timestamp": timestamp,
            "dataframe": df,
        }

        # Step 6: Log to S3
        log_payload = {k: v for k, v in result.items() if k != "dataframe"}
        log_payload["sample_rows"] = df.head(5).to_dict(orient="records")
        s3_status = log_to_s3(log_payload)
        result["s3_status"] = s3_status

        return result

    except Exception as e:
        elapsed = round(time.time() - start, 2)
        error_result = {
            "status": "error",
            "question": user_question,
            "error": str(e),
            "elapsed_seconds": elapsed,
            "timestamp": timestamp,
            "sql": locals().get("sql", ""),
            "dataframe": pd.DataFrame(),
            "insight": "",
            "chart_type": "table",
            "s3_status": "",
        }
        # Still log errors to S3
        log_to_s3({k: v for k, v in error_result.items() if k != "dataframe"})
        return error_result
