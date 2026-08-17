"""
api.py — FastAPI REST backend for the SQL AI Agent
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

from agent import run_agent, get_schema

app = FastAPI(
    title="SQL AI Agent — Superstore Analytics",
    description="Ask business questions in plain English. The AI writes and runs the SQL.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Which region had the highest profit in 2023?"
            }
        }


class QueryResponse(BaseModel):
    status: str
    question: str
    sql: str
    rows_returned: int
    insight: str
    chart_type: str
    elapsed_seconds: float
    timestamp: str
    s3_status: str
    data: list


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "app": "SQL AI Agent",
        "status": "running",
        "docs": "/docs",
        "endpoints": ["/query", "/schema", "/health", "/examples"],
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


@app.get("/schema", tags=["Database"])
def schema():
    """Returns the full database schema used by the agent."""
    try:
        return {"schema": get_schema()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/examples", tags=["Query"])
def examples():
    """Sample questions you can ask the agent."""
    return {
        "example_questions": [
            "Which region had the highest profit in 2023?",
            "Show top 10 customers by total revenue",
            "Which sub-category has the highest average discount?",
            "Compare monthly sales across all 4 regions",
            "Which products are loss-making (negative profit)?",
            "What is the profit margin by category?",
            "Show me year-over-year sales growth",
            "Which segment (Consumer/Corporate/Home Office) is most profitable?",
            "What is the impact of discount levels on profit?",
            "Top 5 states by total orders",
        ]
    }


@app.post("/query", response_model=QueryResponse, tags=["Query"])
def query(req: QueryRequest):
    """
    Ask any business question in plain English.
    The agent generates SQL, runs it, and returns results + AI insight.
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    result = run_agent(req.question)

    if result["status"] == "error":
        raise HTTPException(status_code=422, detail=result["error"])

    # Convert DataFrame to list of dicts for JSON response
    df: pd.DataFrame = result["dataframe"]
    data = df.to_dict(orient="records")

    return QueryResponse(
        status=result["status"],
        question=result["question"],
        sql=result["sql"],
        rows_returned=result["rows_returned"],
        insight=result["insight"],
        chart_type=result["chart_type"],
        elapsed_seconds=result["elapsed_seconds"],
        timestamp=result["timestamp"],
        s3_status=result["s3_status"],
        data=data,
    )
