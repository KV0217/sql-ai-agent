"""
config.py — Central configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-3.6-flash"

# Database
DB_PATH = os.getenv("DB_PATH", "superstore.db")

# AWS S3 — query log archiving
AWS_ACCESS_KEY_ID     = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION            = os.getenv("AWS_REGION", "ap-south-1")
S3_BUCKET             = os.getenv("S3_BUCKET", "")
S3_PREFIX             = "sql-agent-logs/"

# App
APP_TITLE   = "SQL AI Agent — Superstore Analytics"
MAX_ROWS    = 500          # max rows returned per query
QUERY_TIMEOUT = 30         # seconds
