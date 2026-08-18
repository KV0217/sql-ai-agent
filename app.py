"""
app.py — Streamlit frontend for the SQL AI Agent
"""
import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import sqlite3
import json
from datetime import datetime

from config import APP_TITLE, DB_PATH

# Auto-create DB if missing
if not os.path.exists(DB_PATH):
    import setup_db
    setup_db.create_database()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SQL AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Dark gradient background */
.stApp { background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%); }

/* Main header */
.main-header {
    background: linear-gradient(135deg, #1a1f35 0%, #0f1629 100%);
    border: 1px solid #30363d;
    border-radius: 16px;
    padding: 2rem;
    margin-bottom: 2rem;
    text-align: center;
}
.main-header h1 { font-size: 2.2rem; font-weight: 700; color: #e6edf3; margin: 0; }
.main-header p  { color: #8b949e; margin: 0.5rem 0 0 0; font-size: 1rem; }

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #161b22, #1f2937);
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    text-align: center;
}
.metric-label { color: #8b949e; font-size: 0.8rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
.metric-value { color: #58a6ff; font-size: 1.8rem; font-weight: 700; margin-top: 0.3rem; }

/* SQL box */
.sql-box {
    background: #0d1117;
    border: 1px solid #30363d;
    border-left: 4px solid #58a6ff;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 0.85rem;
    color: #79c0ff;
    white-space: pre-wrap;
    margin: 1rem 0;
}

/* Insight box */
.insight-box {
    background: linear-gradient(135deg, #0e2a1f, #0d1f2d);
    border: 1px solid #238636;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    color: #3fb950;
    font-size: 1rem;
    line-height: 1.7;
    margin: 1rem 0;
}
.insight-icon { font-size: 1.2rem; margin-right: 0.5rem; }

/* Question pill */
.question-pill {
    display: inline-block;
    background: #1f6feb22;
    border: 1px solid #1f6feb;
    border-radius: 20px;
    padding: 0.3rem 1rem;
    color: #58a6ff;
    font-size: 0.85rem;
    margin: 0.2rem;
    cursor: pointer;
}

/* Status badge */
.badge-success { background: #1a3d2d; color: #3fb950; border-radius: 6px; padding: 0.2rem 0.6rem; font-size: 0.8rem; font-weight: 600; }
.badge-error   { background: #3d1a1a; color: #f85149; border-radius: 6px; padding: 0.2rem 0.6rem; font-size: 0.8rem; font-weight: 600; }

/* Hide Streamlit branding */
#MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")

    # Read from environment first — no input needed on Render/production
    env_api_key = os.environ.get("GEMINI_API_KEY", "")

    if env_api_key:
        api_key = env_api_key
        st.success("✅ Gemini API Key loaded from environment")
    else:
        api_key = st.text_input("🔑 Gemini API Key", type="password",
                                 help="Get free key at aistudio.google.com")

    # AWS — also read from env first
    aws_bucket = os.environ.get("S3_BUCKET", "") or st.text_input("🪣 AWS S3 Bucket (optional)")
    aws_key    = os.environ.get("AWS_ACCESS_KEY_ID", "")
    aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")


    st.divider()

    st.markdown("## 💡 Example Questions")
    examples = [
        "Which region had highest profit?",
        "Top 10 customers by revenue",
        "Which sub-category loses money?",
        "Monthly sales trend for 2023",
        "Impact of discount on profit",
        "Best performing product category",
        "State with most orders",
        "Which segment is most profitable?",
        "Year over year sales growth",
        "Average order value by region",
    ]
    selected_example = None
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            selected_example = ex

    st.divider()
    st.markdown("## 📜 Query History")
    if st.session_state.history:
        for i, h in enumerate(reversed(st.session_state.history[-10:])):
            st.markdown(f"`{i+1}.` {h['question'][:40]}...")
    else:
        st.caption("No queries yet")

    if st.button("🗑️ Clear History", use_container_width=True):
        st.session_state.history = []
        st.rerun()


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🤖 SQL AI Agent</h1>
    <p>Ask any business question in plain English → AI writes SQL → instant answer + chart</p>
    <p style="color:#58a6ff; font-size:0.85rem; margin-top:0.5rem;">
        Powered by Gemini 1.5 Flash · Superstore Dataset · AWS S3 Logging
    </p>
</div>
""", unsafe_allow_html=True)

# ── DB stats ──────────────────────────────────────────────────────────────────
try:
    conn = sqlite3.connect(DB_PATH)
    total_rows    = pd.read_sql("SELECT COUNT(*) AS n FROM superstore", conn).iloc[0]["n"]
    total_revenue = pd.read_sql("SELECT ROUND(SUM(Sales),0) AS n FROM superstore", conn).iloc[0]["n"]
    total_profit  = pd.read_sql("SELECT ROUND(SUM(Profit),0) AS n FROM superstore", conn).iloc[0]["n"]
    total_orders  = pd.read_sql("SELECT COUNT(DISTINCT Order_ID) AS n FROM superstore", conn).iloc[0]["n"]
    conn.close()

    c1, c2, c3, c4 = st.columns(4)
    for col, label, val in [
        (c1, "📦 Total Records",   f"{int(total_rows):,}"),
        (c2, "💰 Total Revenue",   f"${int(total_revenue):,}"),
        (c3, "📈 Total Profit",    f"${int(total_profit):,}"),
        (c4, "🛒 Unique Orders",   f"{int(total_orders):,}"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{val}</div>
            </div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
except Exception:
    st.warning("⚠️ Database not found. Please run `python setup_db.py` first.")


# ── Main input ────────────────────────────────────────────────────────────────
default_q = selected_example if selected_example else ""
question = st.text_input(
    "💬 Ask your question",
    value=default_q,
    placeholder="e.g. Which region had the highest profit in 2023?",
    key="main_question",
)

run_btn = st.button("🚀 Run Query", type="primary", use_container_width=True)


# ── Agent runner (direct, no HTTP) ───────────────────────────────────────────
def run_query_direct(question: str, api_key: str, aws_bucket: str = "",
                     aws_key: str = "", aws_secret: str = "") -> dict:
    """Runs the agent directly using env vars (already set)."""
    import os
    # Set env vars in case they came from the sidebar
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
    if aws_bucket:
        os.environ["S3_BUCKET"] = aws_bucket
    if aws_key:
        os.environ["AWS_ACCESS_KEY_ID"] = aws_key
    if aws_secret:
        os.environ["AWS_SECRET_ACCESS_KEY"] = aws_secret

    import agent as ag
    from google import genai as genai_sdk
    ag._client = genai_sdk.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

    return ag.run_agent(question)



# ── Results ───────────────────────────────────────────────────────────────────
if run_btn and question.strip():
    if not api_key:
        st.error("❌ Please enter your Gemini API Key in the sidebar.")
    else:
        with st.spinner("🧠 Generating SQL and running query..."):
            result = run_query_direct(question, api_key, aws_bucket, aws_key, aws_secret)
            st.session_state.last_result = result
            st.session_state.history.append({
                "question": question,
                "status": result["status"],
                "timestamp": result["timestamp"],
            })

# Display last result
result = st.session_state.last_result
if result:
    st.divider()

    if result["status"] == "error":
        st.error(f"❌ {result['error']}")
        if result.get("sql"):
            st.markdown("**Generated SQL:**")
            st.code(result["sql"], language="sql")
    else:
        # ── Metadata row
        col_q, col_t, col_r, col_s = st.columns([4, 1.5, 1.5, 2])
        with col_q:
            st.markdown(f"**Question:** {result['question']}")
        with col_t:
            st.markdown(f"⏱️ `{result['elapsed_seconds']}s`")
        with col_r:
            st.markdown(f"📋 `{result['rows_returned']} rows`")
        with col_s:
            s3 = result.get("s3_status", "")
            if "✅" in s3:
                st.markdown('<span class="badge-success">✅ Logged to S3</span>', unsafe_allow_html=True)
            else:
                st.caption(s3[:40] if s3 else "")

        # ── AI Insight
        st.markdown(f"""
        <div class="insight-box">
            <span class="insight-icon">💡</span><strong>AI Insight:</strong><br>
            {result['insight']}
        </div>
        """, unsafe_allow_html=True)

        # ── Generated SQL
        with st.expander("🔍 View Generated SQL", expanded=False):
            st.code(result["sql"], language="sql")

        # ── Chart + Table
        df: pd.DataFrame = result["dataframe"]
        if not df.empty:
            tab_chart, tab_table = st.tabs(["📊 Chart", "📋 Data Table"])

            with tab_chart:
                num_cols = df.select_dtypes(include="number").columns.tolist()
                cat_cols = df.select_dtypes(exclude="number").columns.tolist()

                if num_cols and cat_cols:
                    x_col = cat_cols[0]
                    y_col = num_cols[0]
                    chart_type = result["chart_type"]

                    if chart_type == "bar" or len(df) <= 15:
                        fig = px.bar(
                            df, x=x_col, y=y_col,
                            color=y_col,
                            color_continuous_scale="Blues",
                            template="plotly_dark",
                            title=f"{y_col} by {x_col}",
                        )
                    elif chart_type == "line":
                        fig = px.line(
                            df, x=x_col, y=y_col,
                            markers=True,
                            template="plotly_dark",
                            title=f"{y_col} over {x_col}",
                        )
                    else:
                        fig = px.scatter(
                            df, x=x_col, y=y_col,
                            color=y_col,
                            template="plotly_dark",
                            title=f"{y_col} vs {x_col}",
                        )

                    fig.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#e6edf3"),
                        margin=dict(l=20, r=20, t=50, b=20),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                elif len(num_cols) >= 2:
                    fig = px.scatter(
                        df, x=num_cols[0], y=num_cols[1],
                        template="plotly_dark",
                        title=f"{num_cols[1]} vs {num_cols[0]}",
                    )
                    fig.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#e6edf3"),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Chart not available for this result shape. See Data Table.")

            with tab_table:
                st.dataframe(
                    df,
                    use_container_width=True,
                    height=min(400, 40 + len(df) * 38),
                )
                # Download
                csv = df.to_csv(index=False)
                st.download_button(
                    "⬇️ Download CSV",
                    data=csv,
                    file_name=f"query_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )
        else:
            st.info("Query returned no results.")


# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown("""
<div style="text-align:center; color:#484f58; font-size:0.8rem; padding:1rem">
    Built by <strong style="color:#58a6ff">Kavin Venkat</strong> ·
    Gemini 1.5 Flash · SQLite · AWS S3 · FastAPI · Streamlit ·
    <a href="https://github.com/KV0217" style="color:#58a6ff">GitHub</a>
</div>
""", unsafe_allow_html=True)
