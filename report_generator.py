import psycopg2
import pandas as pd
from datetime import datetime, timedelta
import os

# ------------------------------------------------------
# DATABASE CONNECTION
# ------------------------------------------------------
def get_connection():
    return psycopg2.connect(
        host="localhost",
        port=5433,
        database="onlineapp",
        user="postgres",
        password="aparna"
    )

# ------------------------------------------------------
# CREATE REPORTS TABLE IF NOT EXISTS
# ------------------------------------------------------
def create_reports_table():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            report_id VARCHAR(100) UNIQUE,
            user_id VARCHAR(50),
            report_type VARCHAR(20),
            start_date DATE,
            end_date DATE,
            total_income FLOAT DEFAULT 0,
            total_expense FLOAT DEFAULT 0,
            net_balance FLOAT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✔ reports table ready")
    print("finished")

# ------------------------------------------------------
# FETCH TRANSACTIONS FROM BOTH TABLES
# ------------------------------------------------------
def fetch_transactions(start_date, end_date):
    conn = get_connection()

    query = """
        SELECT date, description, amount, flow, category, merchant 
        FROM gpay_transactions
        WHERE date >= %s AND date <= %s
        
        UNION ALL
        
        SELECT date, description, amount, flow, category, merchant 
        FROM paytm_transactions
        WHERE date >= %s AND date <= %s;
    """

    df = pd.read_sql(query, conn, params=[start_date, end_date, start_date, end_date])
    conn.close()
    return df


# ------------------------------------------------------
# GENERATE REPORT FOR A GIVEN PERIOD
# ------------------------------------------------------
def generate_report(period):
    today = datetime.today().date()

    # ------------ PERIOD CALCULATION ------------
    if period == "daily":
        start = today
        end = today

    elif period == "weekly":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)

    elif period == "monthly":
        start = today.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = next_month - timedelta(days=1)

    elif period == "yearly":
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)

    print(f"\n--- Generating {period} report ---")

    # ------------ FETCH COMBINED TRANSACTIONS ------------
    df = fetch_transactions(start, end)

    total_income = df[df["flow"] == "Income"]["amount"].sum()
    total_expense = df[df["flow"] == "Expense"]["amount"].sum()
    net_balance = total_income - total_expense

    # ------------ SAVE CSV REPORT ------------
    os.makedirs("reports", exist_ok=True)
    csv_path = f"reports/{period}_report.csv"
    df.to_csv(csv_path, index=False)

    print(f"✔ {period.capitalize()} CSV saved:", csv_path)

    # ------------ REPORT ID FORMAT (Simple) ------------
    report_id = f"{period}-{today}"

    # ------------ INSERT REPORT INTO DATABASE ------------
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reports
        (report_id, user_id, report_type, start_date, end_date,
         total_income, total_expense, net_balance)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        report_id,
        "user001",      # FIXED USER ID
        period,
        start,
        end,
        total_income,
        total_expense,
        net_balance
    ))

    conn.commit()
    cur.close()
    conn.close()

    print(f"✔ {period.capitalize()} report inserted into DB")


# ------------------------------------------------------
# RUN ALL REPORTS
# ------------------------------------------------------
def run_all_reports():
    for p in ["daily", "weekly", "monthly", "yearly"]:
        generate_report(p)


# ------------------------------------------------------
# MAIN
# ------------------------------------------------------
if __name__ == "__main__":
    create_reports_table()
    run_all_reports()
