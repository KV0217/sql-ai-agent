"""
setup_db.py - Downloads Superstore data and loads it into SQLite
Run once before starting the app: python setup_db.py
"""
import sqlite3
import pandas as pd
import numpy as np
import os

DB_PATH = "superstore.db"


def create_database():
    print("[*] Loading Superstore dataset...")

    csv_path = "Sample - Superstore.csv"

    if not os.path.exists(csv_path):
        url = "https://raw.githubusercontent.com/KV0217/RETAIL-SALES-ANALYSIS/main/Sample%20-%20Superstore.csv"
        try:
            df = pd.read_csv(url, encoding="latin-1")
            df.to_csv(csv_path, index=False)
            print(f"[+] Downloaded dataset: {len(df)} rows")
        except Exception as e:
            print(f"[!] Could not download ({e}). Generating synthetic data...")
            np.random.seed(42)
            n = 9994
            categories = ["Furniture", "Office Supplies", "Technology"]
            sub_cats = {
                "Furniture": ["Chairs", "Tables", "Bookcases", "Furnishings"],
                "Office Supplies": ["Binders", "Paper", "Storage", "Art", "Labels", "Fasteners", "Envelopes", "Supplies"],
                "Technology": ["Phones", "Accessories", "Machines", "Copiers"],
            }
            segments = ["Consumer", "Corporate", "Home Office"]
            regions = ["East", "West", "Central", "South"]
            states = {
                "East": ["New York", "Pennsylvania", "Ohio", "New Jersey"],
                "West": ["California", "Washington", "Oregon", "Colorado"],
                "Central": ["Texas", "Illinois", "Michigan", "Wisconsin"],
                "South": ["Florida", "North Carolina", "Virginia", "Georgia"],
            }
            ship_modes = ["Standard Class", "Second Class", "First Class", "Same Day"]

            rows = []
            for i in range(n):
                cat = np.random.choice(categories)
                sub_cat = np.random.choice(sub_cats[cat])
                region = np.random.choice(regions)
                state = np.random.choice(states[region])
                segment = np.random.choice(segments)
                ship_mode = np.random.choice(ship_modes, p=[0.6, 0.2, 0.15, 0.05])
                quantity = int(np.random.randint(1, 14))
                base_price = float(np.random.uniform(10, 3000))
                discount = float(np.random.choice(
                    [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
                    p=[0.4, 0.15, 0.15, 0.1, 0.08, 0.05, 0.03, 0.02, 0.02]
                ))
                sales = round(base_price * quantity * (1 - discount), 2)
                profit_margin = float(np.random.uniform(-0.2, 0.4)) - discount * 0.5
                profit = round(sales * profit_margin, 2)
                order_year = int(np.random.choice([2021, 2022, 2023, 2024], p=[0.15, 0.25, 0.35, 0.25]))
                order_month = int(np.random.randint(1, 13))
                order_day = int(np.random.randint(1, 29))
                order_date = f"{order_year}-{order_month:02d}-{order_day:02d}"
                rows.append({
                    "Order_ID": f"CA-{2020+i//2000}-{100000+i}",
                    "Order_Date": order_date,
                    "Ship_Mode": ship_mode,
                    "Customer_ID": f"CU-{10000 + i % 793}",
                    "Customer_Name": f"Customer_{i % 793}",
                    "Segment": segment,
                    "State": state,
                    "Region": region,
                    "Product_ID": f"PRD-{1000 + i % 1850}",
                    "Category": cat,
                    "Sub_Category": sub_cat,
                    "Sales": sales,
                    "Quantity": quantity,
                    "Discount": discount,
                    "Profit": profit,
                    "Order_Year": order_year,
                    "Order_Month": order_month,
                })
            df = pd.DataFrame(rows)
            df.to_csv(csv_path, index=False)
            print(f"[+] Generated synthetic dataset: {len(df)} rows")
    else:
        df = pd.read_csv(csv_path, encoding="latin-1")
        print(f"[+] Loaded existing CSV: {len(df)} rows")

    # Clean column names
    df.columns = (
        df.columns.str.strip()
        .str.replace(" ", "_")
        .str.replace("-", "_")
        .str.replace("/", "_")
        .str.replace(".", "", regex=False)
    )

    # Parse dates
    date_cols = [c for c in df.columns if "date" in c.lower()]
    for col in date_cols:
        try:
            parsed = pd.to_datetime(df[col], dayfirst=False, errors="coerce")
            df[col + "_Year"]    = parsed.dt.year.astype("Int64")
            df[col + "_Month"]   = parsed.dt.month.astype("Int64")
            df[col + "_Quarter"] = parsed.dt.quarter.astype("Int64")
            df[col] = parsed.dt.strftime("%Y-%m-%d").fillna("")
        except Exception:
            pass

    # Write to SQLite
    conn = sqlite3.connect(DB_PATH)
    df.to_sql("superstore", conn, if_exists="replace", index=False)

    # Create views
    conn.execute("""
        CREATE VIEW IF NOT EXISTS regional_summary AS
        SELECT Region, Category,
               ROUND(SUM(Sales),2)     AS Total_Sales,
               ROUND(SUM(Profit),2)    AS Total_Profit,
               ROUND(AVG(Discount)*100,1) AS Avg_Discount_Pct,
               COUNT(*)                AS Orders
        FROM superstore
        GROUP BY Region, Category
    """)
    conn.execute("""
        CREATE VIEW IF NOT EXISTS customer_summary AS
        SELECT Customer_ID, Customer_Name, Segment,
               COUNT(DISTINCT Order_ID)    AS Total_Orders,
               ROUND(SUM(Sales),2)         AS Total_Revenue,
               ROUND(SUM(Profit),2)        AS Total_Profit
        FROM superstore
        GROUP BY Customer_ID, Customer_Name, Segment
    """)
    conn.commit()

    # Print schema
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(superstore)")
    cols = cursor.fetchall()
    print(f"\n[+] Table 'superstore' - {len(cols)} columns:")
    for col in cols:
        print(f"    {col[1]} ({col[2]})")

    cursor.execute("SELECT COUNT(*) FROM superstore")
    total = cursor.fetchone()[0]
    print(f"\n[+] Total rows loaded: {total:,}")
    print(f"[+] Database ready: {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    create_database()
