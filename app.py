
import dash
from dash import html, dcc, Input, Output, State, callback, ctx, no_update
import pandas as pd
import base64
import os
import subprocess
import sys
import re
import io
# PDF library
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from db import authenticate_or_register


def normalize_columns(df):
    rename_map = {
        "Date": "date",
        "Details": "description",
        "Description": "description",
        "Debit": "amount",
        "Credit": "amount",
        "Type": "flow",
        "Amount": "amount",
    }
    df = df.rename(columns=rename_map)
    # build flow if missing
    if "flow" not in df.columns:
        df["flow"] = df["amount"].apply(lambda x: "Expense" if x < 0 else "Income")
    # fix amount sign
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0).abs()
    return df
def build_subcategory(df):
    # use description as subcategory base
    df["sub_category"] = df["description"].astype(str)
    # clean common bank text
    df["sub_category"] = (
        df["sub_category"]
        .str.replace("UPI", "", regex=False)
        .str.replace("PAYMENT", "", regex=False)
        .str.replace("TRANSFER", "", regex=False)
        .str.replace("TO", "", regex=False)
        .str.replace("FROM", "", regex=False)
        .str.strip()
    )
    # shorten long names
    df["sub_category"] = df["sub_category"].str[:20]
    return df
# =========================
# APP SETUP
# =========================
def fix_subcategory(df):
    df["category"] = df["category"].fillna("Other")
    df["sub_category"] = df["sub_category"].fillna(df["category"])
    return df
app = dash.Dash(__name__)
app.config.suppress_callback_exceptions = True
UPLOAD_DIR = "uploads"
PDF_PATH = os.path.join(UPLOAD_DIR, "input.pdf")
CSV_PATH = os.path.join(UPLOAD_DIR, "transactions.csv")
os.makedirs(UPLOAD_DIR, exist_ok=True)
# =========================
# HELPERS (CATEGORY + CLEANING)
# =========================
def clean_desc(desc: str) -> str:
    """Make labels shorter and cleaner for graphs."""
    if desc is None:
        return "Transaction"
    s = str(desc)
    # Remove extra long UPI parts
    s = re.sub(r"UPI\s*ID\s*:\s*\S+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"UPI\s*Ref\s*No\s*:\s*\d+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bTag:\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"#\s*\w+", "", s)  # remove hashtags
    s = re.sub(r"\s{2,}", " ", s).strip()
    # keep it short
    return s[:45] + "..." if len(s) > 48 else s
def categorize(description: str, flow: str):
    """Return (category, sub_category) based on description + flow."""
    d = str(description).lower().strip()
    f = str(flow).lower().strip()
    # Income
    if f == "income":
        if "refund" in d:
            return "Income", "Refund"
        if "cashback" in d:
            return "Income", "Cashback"
        if "received from" in d:
            return "Income", "Received"
        return "Income", "Other Income"
    # Expense
    if "recharge" in d:
        return "Bills", "Mobile Recharge"
    if "electric" in d or "bill payment" in d or "bill payments" in d:
        return "Bills", "Utilities"
    if "zomato" in d or "swiggy" in d or "food" in d:
        return "Food", "Food Delivery"
    if "blinkit" in d or "zepto" in d or "grocer" in d or "mart" in d:
        return "Groceries", "Groceries"
    if "uber" in d or "ola" in d or "rapido" in d:
        return "Travel", "Cab"
    if "amazon" in d or "flipkart" in d or "myntra" in d or "meesho" in d:
        return "Shopping", "Online Shopping"
    if "movie" in d or "bookmyshow" in d:
        return "Entertainment", "Movies"
    if "money sent to" in d or "paid to" in d:
        return "Transfers", "UPI Transfer"
    return "Others", "Other Expense"
def safe_parse_date(series: pd.Series) -> pd.Series:
    """
    Your Paytm date is like '16 Aug' (no year).
    We'll parse with current year fallback.
    """
    dt = pd.to_datetime(series, errors="coerce", dayfirst=True)
    year = pd.Timestamp.now().year
    dt2 = pd.to_datetime(series.astype(str) + f" {year}", errors="coerce", dayfirst=True)
    dt = dt.fillna(dt2)
    return dt
def ensure_category_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.lower().strip() for c in df.columns]
    rename_map = {}
    for c in df.columns:
        cc = c.lower().strip()
        if cc in ["sub-category", "sub category", "subcategory"]:
            rename_map[c] = "sub_category"
        if cc in ["cat", "category name"]:
            rename_map[c] = "category"
    if rename_map:
        df = df.rename(columns=rename_map)
    if "category" not in df.columns or "sub_category" not in df.columns:
        cats = df.apply(lambda r: categorize(r["description"], r["flow"]), axis=1)
        df["category"] = [c[0] for c in cats]
        df["sub_category"] = [c[1] for c in cats]
    df["category"] = df["category"].astype(str)
    df["sub_category"] = df["sub_category"].astype(str)
    return df
def build_pdf_report(df: pd.DataFrame) -> bytes:
    styles = getSampleStyleSheet()
    buff = io.BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=A4)
    story = []
    df = df.copy()
    df.columns = [c.lower().strip() for c in df.columns]
    # Required columns check
    for col in ["flow", "amount", "description"]:
        if col not in df.columns:
            story.append(Paragraph("No valid data found for report.", styles["Title"]))
            doc.build(story)
            pdf_bytes = buff.getvalue()
            buff.close()
            return pdf_bytes
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["flow"] = df["flow"].astype(str).str.strip().str.title()
    df["description"] = df["description"].astype(str)
    df = ensure_category_columns(df)
    df = fix_subcategory(df)
    income = df[df["flow"] == "Income"]["amount"].sum()
    expense = df[df["flow"] == "Expense"]["amount"].sum()
    story.append(Paragraph("Online Transactions Analyzer App Report", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Total Income:</b> ₹{income:,.2f}", styles["Normal"]))
    story.append(Paragraph(f"<b>Total Expense:</b> ₹{expense:,.2f}", styles["Normal"]))
    story.append(Spacer(1, 12))
    # Expense by category table
    exp_df = df[df["flow"] == "Expense"].copy()
    cat_sum = exp_df.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=False)
    cat_sum["amount"] = cat_sum["amount"].round(2)
    story.append(Paragraph("Expense by Category", styles["Heading2"]))
    story.append(Spacer(1, 6))
    if not cat_sum.empty:
        cat_table_data = [["Category", "Amount (₹)"]] + cat_sum.values.tolist()
        cat_table = Table(cat_table_data, hAlign="LEFT")
        cat_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ]))
        story.append(cat_table)
    else:
        story.append(Paragraph("No expense data available.", styles["Normal"]))
    story.append(Spacer(1, 12))
    # Top 10 transactions
    top_df = df.sort_values("amount", ascending=False).head(10).copy()
    top_df["description"] = top_df["description"].apply(clean_desc)
    story.append(Paragraph("Top 10 Transactions", styles["Heading2"]))
    story.append(Spacer(1, 6))
    top_table_data = [["Date", "Description", "Flow", "Amount (₹)"]]
    for _, r in top_df.iterrows():
        top_table_data.append([
            str(r.get("date", "")),
            str(r.get("description", "")),
            str(r.get("flow", "")),
            f"{float(r.get('amount', 0)):,.2f}"
        ])
    top_table = Table(top_table_data, hAlign="LEFT", colWidths=[70, 260, 70, 80])
    top_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (3, 1), (3, -1), "RIGHT"),
    ]))
    story.append(top_table)
    doc.build(story)
    pdf_bytes = buff.getvalue()
    buff.close()
    return pdf_bytes
# =========================

def login_layout():
    return html.Div(
        style={
            "height": "100vh",
            "display": "flex",
            "justifyContent": "center",
            "alignItems": "center",

            # BACKGROUND IMAGE
            "backgroundImage": "url('/assets/background.png')",
            "backgroundSize": "cover",
            "backgroundPosition": "center",
            "backgroundRepeat": "no-repeat"
        },
        children=[

            # GLASS LOGIN CARD
            html.Div(
                style={
                    "width": "500px",
                    "padding": "35px",
                    "borderRadius": "12px",

                    # GLASS EFFECT
                    "background": "rgba(255,255,255,0.15)",
                    "backdropFilter": "blur(12px)",
                    "WebkitBackdropFilter": "blur(12px)",

                    # BORDER
                    "border": "1px solid rgba(255,255,255,0.3)",

                    # SHADOW
                    "boxShadow": "0 8px 32px rgba(0,0,0,0.25)",

                    "textAlign": "center"
                },

                children=[

                    html.H2(
                        "Online Transactions Analyzer App",
                        style={
                            "fontSize": "30px",
                            "marginBottom": "25px",
                            "letterSpacing": "1px",
                            "color": "#0f172a"
                        }
                    ),

                    # USERNAME
                    dcc.Input(
                        id="login-username",
                        placeholder="Username",
                        type="text",
                        style={
                            "width": "100%",
                            "height": "45px",
                            "fontSize": "16px",
                            "padding": "8px",
                            "marginBottom": "12px",
                            "borderRadius": "6px",
                            "border": "1px solid rgba(255,255,255,0.6)",
                            "backgroundColor": "rgba(255,255,255,0.85)"
                        }
                    ),

                    # PASSWORD
                    dcc.Input(
                        id="login-password",
                        placeholder="Password",
                        type="password",
                        style={
                            "width": "100%",
                            "height": "45px",
                            "fontSize": "16px",
                            "padding": "8px",
                            "marginBottom": "18px",
                            "borderRadius": "6px",
                            "border": "1px solid rgba(255,255,255,0.6)",
                            "backgroundColor": "rgba(255,255,255,0.85)"
                        }
                    ),

                    # LOGIN BUTTON
                    html.Button(
                        "Login",
                        id="login-btn",
                        n_clicks=0,
                        style={
                            "width": "100%",
                            "height": "48px",
                            "fontSize": "18px",
                            "background": "linear-gradient(90deg,#1677ff,#5aa3ff)",
                            "color": "white",
                            "border": "none",
                            "borderRadius": "6px",
                            "cursor": "pointer"
                        }
                    ),

                    # ERROR MESSAGE
                    html.Div(
                        id="login-error",
                        style={
                            "display": "none",
                            "marginTop": "10px",
                            "fontWeight": "500",
                            "color": "white"
                        }
                    )

                ]
            )
        ]
    )

# LAYOUT
# =========================
def main_app_layout():
    return html.Div(

    [
    dcc.Store(id="transaction-store"),
    dcc.Store(id="source-lock"),
    dcc.Interval(id="csv-poller", interval=5000, n_intervals=0),

    # Downloads
    dcc.Download(id="download-csv"),
    dcc.Download(id="download-pdf"),

    html.H2("Online Transactions Analyzer App"),

    dcc.Tabs(
        id="page-tabs",
        value="upload",
        children=[
            dcc.Tab(label="📤 Upload", value="upload"),
            dcc.Tab(label="📊 Dashboard", value="dashboard"),
            dcc.Tab(label="📄 Report", value="report"),
        ]
    ),
    # =========================
    # UPLOAD PAGE
    # =========================
    html.Div(
        id="upload-page",
        children=[
            html.Div([
                html.H4("Select PDF Type"),
                dcc.Dropdown(
                    id="pdf-type",
                    options=[
                        {"label": "GPay PDF", "value": "gpay"},
                        {"label": "Paytm PDF", "value": "paytm"},
                    ],
                    value="gpay",
                    clearable=False,
                    style={"width": "50%"}
                ),
            ], style={"margin": "20px"}),
            html.Div([
                html.Div([
                    dcc.Upload(
                        id="upload-pdf",
                        children=html.Div("📄 Upload PDF"),
                        style={
                            "width": "100%",
                            "height": "80px",
                            "lineHeight": "80px",
                            "border": "1px dashed",
                            "textAlign": "center",
                        },
                        multiple=False
                    )
                ], style={"width": "48%", "display": "inline-block"}),
                html.Div([
                    dcc.Upload(
                        id="upload-csv",
                        children=html.Div("📊 Upload CSV File"),
                        style={
                            "width": "100%",
                            "height": "80px",
                            "lineHeight": "80px",
                            "border": "1px dashed",
                            "textAlign": "center",
                        },
                        multiple=False
                    )
                ], style={"width": "48%", "display": "inline-block", "float": "right"}),
            ], style={"margin": "20px"}),
            html.Div(id="upload-status")
        ]
    ),
    # =========================
    # DASHBOARD PAGE
    # =========================
    # =========================
# DASHBOARD PAGE
# =========================
html.Div(
    id="dashboard-page",
    style={"display": "none"},
    children=[
        html.Div([
            html.H4("Filters"),
            dcc.Dropdown(id="filter-category", placeholder="Select Category"),
            html.Button("Reset Filter", id="reset-filter"),
            dcc.Store(id="dashboard-filter"),
        ], style={"marginBottom": "20px"}),
        html.Div([
            html.Div([
                html.H4("Income"),
                html.H2(id="income-value", children="₹0.00"),
            ], style={"width": "45%", "display": "inline-block"}),
            html.Div([
                html.H4("Expense"),
                html.H2(id="expense-value", children="₹0.00"),
            ], style={"width": "45%", "display": "inline-block"}),
        ]),
        html.Div([
    html.Div([
        dcc.Graph(id="bar-chart")
    ], style={"width": "48%", "display": "inline-block", "padding": "10px"}),
    html.Div([
        dcc.Graph(id="income-expense-pie")
    ], style={"width": "48%", "display": "inline-block", "padding": "10px"}),
]),
html.Div([
    html.Div([
        dcc.Graph(id="daily-expense-line")
    ], style={"width": "48%", "display": "inline-block", "padding": "10px"}),
    html.Div([
        dcc.Graph(id="category-pie")
    ], style={"width": "48%", "display": "inline-block", "padding": "10px"}),
]),
    ]
),
    
    # =========================
    # REPORT PAGE
    # =========================
        html.Div(
        id="report-page",
        style={"display": "none"},
        children=[
            html.H3("📄 Report Download"),
            html.P("Download your report in CSV or PDF format."),
            html.Div([
                html.Button("⬇️ Download CSV", id="btn-download-csv", n_clicks=0,
                            style={"padding": "12px", "marginRight": "10px"}),
                html.Button("⬇️ Download PDF", id="btn-download-pdf", n_clicks=0,
                            style={"padding": "12px"}),
            ], style={"marginTop": "15px"}),
            html.Div(id="report-status", style={"marginTop": "15px"})
        ]
    ),

],
style={
    "backgroundImage": "url('/assets/dashboard_bg.png')",
    "backgroundSize": "cover",
    "backgroundPosition": "center",
    "backgroundRepeat": "no-repeat",
    "minHeight": "100vh",
    "padding": "20px"
}
)
# =========================
# TAB VISIBILITY
# =========================
@callback(
    Output("upload-page", "style"),
    Output("dashboard-page", "style"),
    Output("report-page", "style"),
    Input("page-tabs", "value"),
)
def switch_pages(tab):
    if tab == "upload":
        return {}, {"display": "none"}, {"display": "none"}
    if tab == "dashboard":
        return {"display": "none"}, {}, {"display": "none"}
    return {"display": "none"}, {"display": "none"}, {}
@callback(
    Output("filter-category", "options"),
    Input("transaction-store", "data"),
)
def populate_filters(data):

    if not data:
        return []

    df = pd.DataFrame(data)
    df = normalize_columns(df)
    df = ensure_category_columns(df)

    cat_opts = [
        {"label": c, "value": c}
        for c in sorted(df["category"].unique())
    ]

    return cat_opts

@callback(
    Output("dashboard-filter", "data"),
    Input("filter-category", "value"),
    Input("reset-filter", "n_clicks"),
    prevent_initial_call=True
)
def update_filter(cat, reset):
    if ctx.triggered_id == "reset-filter":
        return {}
    return {"category": cat}
# =========================
# DATA INGESTION (PDF + CSV)
# =========================
@callback(
    Output("transaction-store", "data"),
    Output("upload-status", "children"),
    Output("source-lock", "data"),
    Input("upload-pdf", "contents"),
    Input("upload-csv", "contents"),
    Input("csv-poller", "n_intervals"),
    State("source-lock", "data"),
    State("pdf-type", "value"),
    prevent_initial_call=True
)
def handle_data(pdf_contents, csv_contents, n, source, pdf_type):
    trigger = ctx.triggered_id
    # ==========================
    # PDF UPLOAD
    # ==========================
    if trigger == "upload-pdf" and pdf_contents:
        print("📄 PDF uploaded")
        # ❗ CLEAR OLD CSV (VERY IMPORTANT)
        if os.path.exists(CSV_PATH):
            try:
                os.remove(CSV_PATH)
            except Exception:
                pass
        # save uploaded PDF
        _, content_string = pdf_contents.split(",")
        with open(PDF_PATH, "wb") as f:
            f.write(base64.b64decode(content_string))
        # choose correct script
        script = "gpay_pdf_to_csv.py" if pdf_type == "gpay" else "paytm_pdf_to_csv.py"
        subprocess.Popen(
            [sys.executable, script],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        # lock source so poller starts
        return no_update, "⏳ Processing PDF…", "pdf"
    # ==========================
    # CSV POLLER (FROM PDF)
    # ==========================
    if trigger == "csv-poller" and source == "pdf":
        # CSV not created yet
        if not os.path.exists(CSV_PATH):
            return no_update, no_update, no_update
        try:
            df = pd.read_csv(CSV_PATH)
            # CSV exists but still empty / incomplete
            if df.empty or "amount" not in df.columns:
                return no_update, no_update, no_update
        except Exception:
            # file still being written
            return no_update, no_update, no_update
        print("✅ CSV ready → dashboard update")
        # IMPORTANT: source-lock reset to stop poller
        return df.to_dict("records"), "✅ PDF processed!", None
    # ==========================
    # CSV UPLOAD (MANUAL)
    # ==========================
    if trigger == "upload-csv" and csv_contents:
        _, content_string = csv_contents.split(",")
        df = pd.read_csv(
            pd.io.common.BytesIO(base64.b64decode(content_string))
        )
        return df.to_dict("records"), "📊 CSV uploaded!", "csv"
    # ==========================
    # DEFAULT
    # ==========================
    return no_update, no_update, no_update
# =========================
# DISABLE OTHER UPLOAD
# =========================
@callback(
    Output("upload-pdf", "disabled"),
    Output("upload-csv", "disabled"),
    Input("source-lock", "data"),
)
def toggle_uploads(source):
    if source == "pdf":
        return False, True
    if source == "csv":
        return True, False
    return False, False
# =========================
# DASHBOARD UPDATE
# =========================
@callback(
    Output("income-value", "children"),
    Output("expense-value", "children"),
    Output("bar-chart", "figure"),
    Output("income-expense-pie", "figure"),
    Output("daily-expense-line", "figure"),
    Output("category-pie", "figure"),
    Input("transaction-store", "data"),
    Input("dashboard-filter", "data"),
)
def update_dashboard(data, filters):
    if not data:
        return "₹0.00", "₹0.00", {}, {}, {}, {}
    df = pd.DataFrame(data)
    df.columns = [c.lower().strip() for c in df.columns]
    for col in ["flow", "amount", "description"]:
        if col not in df.columns:
            return "₹0.00", "₹0.00", {}, {}, {}, {}
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["flow"] = df["flow"].astype(str).str.strip().str.title()
    df["description"] = df["description"].astype(str)
    df = normalize_columns(df)
    df = ensure_category_columns(df)
    df = build_subcategory(df)
    df = fix_subcategory(df)
    if "date" in df.columns:
        df["date_dt"] = safe_parse_date(df["date"])
    else:
        df["date_dt"] = pd.NaT
    # APPLY FILTERS
    if filters:
        if filters.get("category"):
            df = df[df["category"] == filters["category"]]
    income = df[df["flow"] == "Income"]["amount"].sum()
    expense = df[df["flow"] == "Expense"]["amount"].sum()
    # BAR CHART
    # BAR CHART (use sub-category instead of description)
    top_df = df.sort_values("amount", ascending=False).head(10)
    bar_fig = {
    "data": [{
        "x": top_df["amount"],
        "y": top_df["sub_category"],
        "type": "bar",
        "orientation": "h",
    }],
    "layout": {
        "title": "Top Transactions by Sub-category",
        "margin": {"l": 200, "r": 20, "t": 40, "b": 40},
        "yaxis": {"automargin": True}
    }
}
    
    # PIE
    summary = df.groupby("flow")["amount"].sum().reset_index()
    pie_fig = {
        "data": [{
            "labels": summary["flow"],
            "values": summary["amount"],
            "type": "pie",
        }],
        "layout": {"title": "Income vs Expense"}
    }
    # TREND
    daily = df[df["flow"] == "Expense"].dropna(subset=["date_dt"])
    daily = daily.groupby(daily["date_dt"].dt.date)["amount"].sum().reset_index()
    trend_fig = {
        "data": [{
            "x": daily["date_dt"],
            "y": daily["amount"],
            "type": "scatter",
            "mode": "lines+markers"
        }],
        "layout": {"title": "Daily Trend"}
    }
    # TOP 5 CATEGORY
    exp_df = df[df["flow"] == "Expense"]
    top5 = exp_df.groupby("category")["amount"].sum().nlargest(5).reset_index()
    # TOP 5 CATEGORY
    top5_fig = {
    "data": [{
        "labels": top5["category"],
        "values": top5["amount"],
        "type": "pie",
        "hole": 0.55,
        "textinfo": "percent",
        "textposition": "inside",
        "hovertemplate": "%{label}<br>₹%{value:,.0f}<extra></extra>",
        "insidetextorientation": "radial"
    }],
    "layout": {
        "title": "Top 5 Categories",
        "showlegend": True,
        "margin": {"l": 20, "r": 20, "t": 50, "b": 20}
    }
}
    return (
        f"₹{income:,.2f}",
        f"₹{expense:,.2f}",
        bar_fig,
        pie_fig,
        trend_fig,
        top5_fig
    )
# =========================
@callback(
    Output("login-state", "data"),
    Output("login-error", "children"),
    Output("login-error", "style"),
    Input("login-btn", "n_clicks"),
    Input("login-username", "value"),
    Input("login-password", "value"),
    prevent_initial_call=True
)
def handle_login(n_clicks, username, password):

    base_style = {
        "display": "none",
        "marginTop": "10px",
        "fontWeight": "500"
    }

    trigger = ctx.triggered_id

    # Hide error while typing
    if trigger in ("login-username", "login-password"):
        return no_update, "", base_style

    if not username or not password:
        return (
            {"logged_in": False},
            "❌ Enter username and password",
            {**base_style, "display": "block", "color": "red"}
        )

    status, user = authenticate_or_register(username, password)

    # ❌ Username exists but password wrong
    if status == "PASSWORD_WRONG":
        return (
            {"logged_in": False},
            "❌ Wrong password for this user",
            {**base_style, "display": "block", "color": "red"}
        )

    # ❌ Username already exists (trying different password)
    if status == "USERNAME_EXISTS":
        return (
            {"logged_in": False},
            "❌ User with this name already exists. Try a different username.",
            {**base_style, "display": "block", "color": "red"}
        )

    # ✅ Login or auto-register success
    return (
        {
            "logged_in": True,
            "user": {
                "id": user[0],
                "username": user[1],
                "name": user[2],
                "email": user[3],
            }
        },
        "",
        base_style
    )



@callback(
    Output("root", "children"),
    Input("login-state", "data"),
)
def render_app(state):
    if state.get("logged_in"):
        return main_app_layout()

    # key forces Dash to rebuild login layout fresh
    return html.Div(login_layout(), key="login-page")



# ONE CALLBACK: DOWNLOAD CSV + PDF
# =========================
@callback(
    Output("download-csv", "data"),
    Output("download-pdf", "data"),
    Output("report-status", "children"),
    Input("btn-download-csv", "n_clicks"),
    Input("btn-download-pdf", "n_clicks"),
    State("transaction-store", "data"),
    prevent_initial_call=True
)
def download_reports(n_csv, n_pdf, data):
    if not data:
        return no_update, no_update, "❌ No data available. Upload PDF/CSV first."
    df = pd.DataFrame(data)
    triggered = ctx.triggered_id
    if triggered == "btn-download-csv":
        return (
            dcc.send_data_frame(df.to_csv, "Online Transactions Analyzer App_Report.csv", index=False),
            no_update,
            "✅ CSV downloaded!"
        )
    if triggered == "btn-download-pdf":
        pdf_bytes = build_pdf_report(df)
        return (
            no_update,
            dcc.send_bytes(pdf_bytes, "Online Transactions Analyzer App_Report.pdf"),
            "✅ PDF downloaded!"
        )
    return no_update, no_update, no_update




app.layout = html.Div(
    children=[
        dcc.Store(
            id="login-state",
            data={"logged_in": False, "user": None}
        ),
        html.Div(id="root")
    ]
)

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True)


