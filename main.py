# main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
import datetime as dt
import io, base64

def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)  # close to free memory
    return img_base64


app = FastAPI(title="Shopping Mall Analytics")



# --------------------------
# Load your data (CSV)
# --------------------------
df = pd.read_csv("customer_shopping_data.csv", parse_dates=['invoice_date'])

@app.get("/")
def home():
    return {"message": "Welcome to the Shopping Mall Analytics API! Visit /docs for API docs."}

# --- figuring out which date format works the best-
def try_parse_date(s, dayfirst):
    return pd.to_datetime(s, errors='coerce', dayfirst=dayfirst)

d1 = try_parse_date(df['invoice_date'], dayfirst=False)  # assume month/day/year
d2 = try_parse_date(df['invoice_date'], dayfirst=True)   # assume day/month/year

# Count how many parsing failures (NaT = Not a Time) under each option
count_nat_d1 = d1.isna().sum()
count_nat_d2 = d2.isna().sum()

# Choose whichever gives fewer failures
if count_nat_d2 < count_nat_d1:
    df['invoice_date'] = d2
    print("Using dayfirst=True for invoice_date parsing.")
else:
    df['invoice_date'] = d1
    print("Using dayfirst=False for invoice_date parsing.")
# --------------------------
# Mall & Region performance chart endpoint
# --------------------------
import io
import base64
import matplotlib.pyplot as plt

import seaborn as sns
from fastapi.responses import HTMLResponse

@app.get("/mall-region-performance", response_class=HTMLResponse)
def mall_region_performance():
    # Create net_sales column if missing
    if 'net_sales' not in df.columns:
        df['net_sales'] = df['price'] * df['quantity']

    # --------------------
    # Mall-level aggregation
    # --------------------
    mall_perf = df.groupby('shopping_mall').agg(
        total_sales=('net_sales', 'sum'),
        total_qty=('quantity', 'sum'),
        unique_customers=('customer_id', 'nunique'),
        num_invoices=('invoice_no', 'nunique')
    ).reset_index()
    mall_perf['avg_order_value'] = mall_perf['total_sales'] / mall_perf['num_invoices']

    # --------------------
    # Region mapping + aggregation
    # --------------------
    region_map = {
        'Kanyon': 'Europe',
        'Forum Istanbul': 'Europe',
        'Metrocity': 'Europe',
        'Metropol AVM': 'Asia',
        'Istinye Park': 'Europe',
        'Mall of Istanbul': 'Europe',
        'Emaar Square Mall': 'Asia',
        'Cevahir AVM': 'Europe',
        'Viaport Outlet': 'Asia',
        'Zorlu Center': 'Europe'
    }
    df['region'] = df['shopping_mall'].map(region_map)

    region_perf = df.groupby('region').agg(
        total_sales=('net_sales','sum'),
        total_qty=('quantity','sum'),
        unique_customers=('customer_id','nunique'),
        num_invoices=('invoice_no','nunique')
    ).reset_index()
    region_perf['avg_order_value'] = region_perf['total_sales'] / region_perf['num_invoices']

    # --------------------
    # Plot charts and encode
    # --------------------
    charts_html = ""

    # Mall-level chart (barplot)
    plt.figure(figsize=(10, 6))
    sns.barplot(
        data=mall_perf.sort_values('total_sales', ascending=False),
        x='shopping_mall', y='total_sales', palette='Blues_d'
    )
    plt.xticks(rotation=45)
    plt.title("Total Sales by Shopping Mall")
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close()
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    charts_html += f'<h2>Total Sales by Shopping Mall</h2><img src="data:image/png;base64,{img_base64}" /><br><br>'

    # Region-level chart (donut chart for sales share)
    plt.figure(figsize=(6, 6))
    plt.pie(
        region_perf['total_sales'],
        labels=region_perf['region'],
        autopct='%1.1f%%',
        startangle=140,
        colors=sns.color_palette("viridis", len(region_perf))
    )
    # Draw a white circle in the center to make it a donut
    centre_circle = plt.Circle((0, 0), 0.70, fc='white')
    fig = plt.gcf()
    fig.gca().add_artist(centre_circle)
    plt.title("Total Sales by Region")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close()
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    charts_html += f'<h2>Total Sales by Region</h2><img src="data:image/png;base64,{img_base64}" /><br><br>'

    # --------------------
    # Final HTML Response
    # --------------------
    html_content = f"""
    <html>
        <head>
            <title>Mall & Region Performance</title>
        </head>
        <body style="font-family: Arial; text-align: center; margin: 20px;">
            {charts_html}
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)








# --------------------------
# Repeat vs One-time endpoint
# --------------------------
@app.get("/repeat-vs-one-html", response_class=HTMLResponse)
def repeat_vs_one_html():
    # Ensure net_sales column exists
    df['net_sales'] = df['quantity'] * df['price']

    # Count number of invoices per customer
    customer_orders = df.groupby('customer_id')['invoice_no'].nunique().reset_index()
    customer_orders.rename(columns={'invoice_no': 'num_invoices'}, inplace=True)

    # Categorize customers
    customer_orders['Customer Type'] = np.where(customer_orders['num_invoices'] > 1,
                                                'Repeat Customer', 'One-time Customer')

    # Total spend per customer
    customer_spend = df.groupby('customer_id')['net_sales'].sum().reset_index()
    customer_orders = customer_orders.merge(customer_spend, on='customer_id', how='left')

    # Aggregate spend by customer type
    repeat_vs_one_df = customer_orders.groupby('Customer Type')['net_sales'].sum().reset_index()
    repeat_vs_one_df.rename(columns={'net_sales': 'Total Sales'}, inplace=True)

    # Format numbers
    repeat_vs_one_df['Total Sales'] = repeat_vs_one_df['Total Sales'].map("{:,.2f}".format)

    # Generate HTML table
    html_table = repeat_vs_one_df.to_html(index=False, classes='table table-striped', justify='left', escape=False)

    html_content = f"""
    <html>
        <head>
            <title>Repeat vs One-time Customers</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                }}
                table {{
                    border-collapse: collapse;
                    width: 50%;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #031278;
                    color: white;
                }}
                tr:nth-child(even) {{
                    background-color: #f2f2f2;
                }}
            </style>
        </head>
        <body>
            <h2>Repeat vs One-time Customers</h2>
            {html_table}
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# --------------------------
# Category insights endpoint
# --------------------------
@app.get("/category-insights-html", response_class=HTMLResponse)
def category_insights_html():
    # Ensure net_sales column exists
    df['net_sales'] = df['quantity'] * df['price']

    # Aggregate category metrics
    category_perf = df.groupby('category').agg(
        total_sales=('net_sales', 'sum'),
        total_qty=('quantity', 'sum'),
        num_customers=('customer_id', 'nunique'),
        num_invoices=('invoice_no', 'nunique')
    ).reset_index()

    # Average order value
    category_perf['avg_order_value'] = category_perf['total_sales'] / category_perf['num_invoices']

    # Format numbers: comma separated, 2 decimal places
    category_perf['total_sales'] = category_perf['total_sales'].map("{:,.2f}".format)
    category_perf['avg_order_value'] = category_perf['avg_order_value'].map("{:,.2f}".format)
    category_perf['total_qty'] = category_perf['total_qty'].map("{:,}".format)
    category_perf['num_customers'] = category_perf['num_customers'].map("{:,}".format)
    category_perf['num_invoices'] = category_perf['num_invoices'].map("{:,}".format)

    # Title case columns
    category_perf.columns = [col.replace('_', ' ').title() for col in category_perf.columns]

    # Generate HTML table
    html_table = category_perf.to_html(index=False, classes='table table-striped', justify='left', escape=False)

    html_content = f"""
    <html>
        <head>
            <title>Category Insights</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                }}
                table {{
                    border-collapse: collapse;
                    width: 80%;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #031278;
                    color: white;
                }}
                tr:nth-child(even) {{
                    background-color: #f2f2f2;
                }}
            </style>
        </head>
        <body>
            <h2>Category Insights Summary</h2>
            {html_table}
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

from fastapi.responses import HTMLResponse

# Mapping malls to regions
mall_region_map = {
    "Kanyon": "Europe",
    "Forum Istanbul": "Europe",
    "Metrocity": "Europe",
    "Istinye Park": "Europe",
    "Mall of Istanbul": "Europe",
    "Cevahir AVM": "Europe",
    "Zorlu Center": "Europe",
    "Metropol AVM": "Asia",
    "Emaar Square Mall": "Asia",
    "Viaport Outlet": "Asia"
}

@app.get("/store-region-performance-html", response_class=HTMLResponse)
def store_region_performance_html():
    # Create net_sales
    df['net_sales'] = df['quantity'] * df['price']

    # Add region column
    df['region'] = df['shopping_mall'].map(mall_region_map)

    # Aggregate metrics
    store_region_perf = df.groupby(['region', 'shopping_mall']).agg(
        total_sales=('net_sales', 'sum'),
        total_qty=('quantity', 'sum'),
        num_customers=('customer_id', 'nunique'),
        num_invoices=('invoice_no', 'nunique')
    ).reset_index()

    # Average order value
    store_region_perf['avg_order_value'] = store_region_perf['total_sales'] / store_region_perf['num_invoices']

    # Format numbers
    store_region_perf['total_sales'] = store_region_perf['total_sales'].map("{:,.2f}".format)
    store_region_perf['avg_order_value'] = store_region_perf['avg_order_value'].map("{:,.2f}".format)
    store_region_perf['total_qty'] = store_region_perf['total_qty'].map("{:,}".format)
    store_region_perf['num_customers'] = store_region_perf['num_customers'].map("{:,}".format)
    store_region_perf['num_invoices'] = store_region_perf['num_invoices'].map("{:,}".format)

    # Title case headers
    store_region_perf.columns = [col.replace('_', ' ').title() for col in store_region_perf.columns]

    # Generate HTML table
    html_table = store_region_perf.to_html(index=False, classes='table table-striped', justify='left', escape=False)

    html_content = f"""
    <html>
        <head>
            <title>Store vs Region Performance</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                }}
                table {{
                    border-collapse: collapse;
                    width: 95%;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #031278;
                    color: white;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
            </style>
        </head>
        <body>
            <h2>Store vs Region Performance Summary</h2>
            {html_table}
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# --------------------------
# Top Customers Endpoint (Charts only)
# --------------------------
import io
import base64
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from fastapi.responses import HTMLResponse, JSONResponse

@app.get("/top-customers")
def top_customers():
    try:
        # Ensure net_sales exists
        if 'net_sales' not in df.columns:
            df['net_sales'] = df['quantity'] * df['price']

        # --------------------
        # 1. Aggregate customer metrics
        # --------------------
        customer_summary = (
            df.groupby('customer_id')
            .agg(
                total_spent=('net_sales', 'sum'),
                total_qty=('quantity', 'sum'),
                num_invoices=('invoice_no', 'nunique')
            )
            .reset_index()
        )
        customer_summary['avg_order_value'] = (
            customer_summary['total_spent'] / customer_summary['num_invoices']
        )

        # --------------------
        # 2. Top 10 Customers by Spend
        # --------------------
        top_10_customers = (
            customer_summary.sort_values('total_spent', ascending=False).head(10)
        )
        plt.figure(figsize=(10, 5))
        sns.barplot(
            data=top_10_customers,
            x='customer_id',
            y='total_spent',
            palette='Blues_r'
        )
        plt.xticks(rotation=45)
        plt.title("Top 10 Customers by Total Spend")
        plt.xlabel("Customer ID")
        plt.ylabel("Total Spend")
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close()
        buf.seek(0)
        top10_img = base64.b64encode(buf.read()).decode("utf-8")

        # --------------------
        # 3. Segment: Top 10% vs Others
        # --------------------
        spend_threshold = customer_summary['total_spent'].quantile(0.90)
        customer_summary['segment'] = np.where(
            customer_summary['total_spent'] >= spend_threshold, 'Top 10%', 'Other'
        )
        segment_contribution = (
            customer_summary.groupby('segment')['total_spent'].sum()
        )
        segment_contribution_pct = (
            segment_contribution / segment_contribution.sum() * 100
        )
        plt.figure(figsize=(6, 5))
        sns.barplot(
            x=segment_contribution_pct.index,
            y=segment_contribution_pct.values,
            palette="viridis"
        )
        plt.title("Revenue Contribution by Segment (%)")
        plt.ylabel("Revenue Contribution %")
        plt.xlabel("Customer Segment")
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close()
        buf.seek(0)
        segment_img = base64.b64encode(buf.read()).decode("utf-8")

        # --------------------
        # 4. Cumulative Revenue Contribution (Pareto)
        # --------------------
        customer_sorted = (
            customer_summary.sort_values('total_spent', ascending=False)
            .reset_index(drop=True)
        )
        customer_sorted['cumulative_pct'] = (
            customer_sorted['total_spent'].cumsum()
            / customer_sorted['total_spent'].sum() * 100
        )
        plt.figure(figsize=(10, 6))
        sns.lineplot(
            data=customer_sorted,
            x=customer_sorted.index,
            y='cumulative_pct'
        )
        plt.axhline(80, color='red', linestyle='--', label="80% threshold")
        plt.title("Cumulative Revenue Contribution by Customers")
        plt.xlabel("Customers (sorted by spend)")
        plt.ylabel("Cumulative % of Revenue")
        plt.legend()
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close()
        buf.seek(0)
        cumulative_img = base64.b64encode(buf.read()).decode("utf-8")

        # --------------------
        # Final HTML
        # --------------------
        html_content = f"""
        <html>
            <head>
                <title>Top Customers Analysis</title>
            </head>
            <body style="font-family: Arial; text-align: center; margin: 20px;">
                <h2>🏆 Top 10 Customers by Spend</h2>
                <img src="data:image/png;base64,{top10_img}" /><br><br>

                <h2>📊 Revenue Contribution by Segment</h2>
                <img src="data:image/png;base64,{segment_img}" /><br><br>

                <h2>📈 Cumulative Revenue Contribution</h2>
                <img src="data:image/png;base64,{cumulative_img}" /><br><br>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

# --------------------------
# High vs Medium vs Low Value Segmentation
# --------------------------
@app.get("/value-segmentation")
def value_segmentation():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
        import io, base64
        import numpy as np

        # --- Step 0: Build customer_summary ---
        df['net_sales'] = df['quantity'] * df['price']
        customer_summary = (
            df.groupby('customer_id')
            .agg(
                total_spent=('net_sales', 'sum'),
                total_qty=('quantity', 'sum'),
                num_invoices=('invoice_no', 'nunique')
            )
            .reset_index()
        )
        customer_summary['avg_order_value'] = (
            customer_summary['total_spent'] / customer_summary['num_invoices']
        )

        # --- Step 1: Define quantile thresholds ---
        q80 = customer_summary['total_spent'].quantile(0.80)
        q30 = customer_summary['total_spent'].quantile(0.30)

        # --- Step 2: Classify customers ---
        def classify_customer(spent):
            if spent >= q80:
                return "High-value"
            elif spent >= q30:
                return "Medium-value"
            else:
                return "Low-value"

        customer_summary['value_segment'] = customer_summary['total_spent'].apply(classify_customer)

        # --- Step 3: Revenue contribution per segment ---
        segment_revenue = (
            customer_summary.groupby('value_segment')['total_spent']
            .sum()
            .sort_values(ascending=False)
        )

        # --- Step 4: Visualization ---
        plt.figure(figsize=(8,5))
        sns.barplot(x=segment_revenue.index, y=segment_revenue.values, palette="viridis")
        plt.title("Revenue Contribution by Customer Segments")
        plt.xlabel("Customer Segment")
        plt.ylabel("Total Revenue")
        plt.tight_layout()

        # Save plot to base64
        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        plt.close()
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")

        # --- Step 5: Return as HTML with embedded chart ---
        html_content = f"""
        <html>
            <head>
                <title>Value Segmentation</title>
            </head>
            <body>
                <h2>💰 Revenue Contribution by Customer Segments</h2>
                <img src="data:image/png;base64,{img_base64}" alt="Value Segmentation Chart"/>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

# --------------------------
# Seasonality Analysis (Daily, Monthly, Quarterly, Yearly Trends)
# --------------------------
@app.get("/seasonality-analysis", response_class=HTMLResponse)
def seasonality_analysis():
    import matplotlib.dates as mdates
    df_copy = df.copy()
    df_copy['invoice_date'] = pd.to_datetime(df_copy['invoice_date'], errors='coerce')
    df_copy = df_copy.dropna(subset=['invoice_date'])
    df_copy['net_sales'] = df_copy['price'] * df_copy['quantity']

    # --- Daily sales ---
    daily_sales = (
        df_copy.groupby('invoice_date')
        .agg(
            total_sales=('net_sales', 'sum'),
            total_qty=('quantity', 'sum'),
            num_invoices=('invoice_no', 'nunique')
        )
        .reset_index()
    )

    # --- Store (Mall) level daily performance ---
    store_daily_sales = (
        df_copy.groupby(['shopping_mall', 'invoice_date'])
        .agg(
            total_sales=('net_sales', 'sum'),
            total_qty=('quantity', 'sum'),
            num_invoices=('invoice_no', 'nunique')
        )
        .reset_index()
    )
    
    # Add 7-day moving average for FacetGrid plot
    store_daily_sales['sales_ma7'] = store_daily_sales.groupby('shopping_mall')['total_sales'].transform(lambda x: x.rolling(7,1).mean())

    # --- Monthly and Quarterly ---
    df_copy['year_month'] = df_copy['invoice_date'].dt.to_period('M')
    df_copy['year_quarter'] = df_copy['invoice_date'].dt.to_period('Q')

    monthly_sales = (
        df_copy.groupby('year_month')
        .agg(total_sales=('net_sales', 'sum'),
             total_qty=('quantity', 'sum'),
             num_invoices=('invoice_no', 'nunique'))
        .reset_index()
    )
    quarterly_sales = (
        df_copy.groupby('year_quarter')
        .agg(total_sales=('net_sales', 'sum'),
             total_qty=('quantity', 'sum'),
             num_invoices=('invoice_no', 'nunique'))
        .reset_index()
    )

    # --- Yearly sales ---
    df_copy['year'] = df_copy['invoice_date'].dt.year
    yearly_sales = (
        df_copy.groupby('year')
        .agg(
            total_sales=('net_sales', 'sum'),
            total_qty=('quantity', 'sum'),
            num_invoices=('invoice_no', 'nunique')
        )
        .reset_index()
    )

    # --- Plotting ---
    plots = []

    # Daily total sales
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.lineplot(data=daily_sales, x='invoice_date', y='total_sales', marker="o", ax=ax)
    ax.set_title("Daily Total Sales")
    ax.set_xlabel("Date")
    ax.set_ylabel("Total Sales")
    plt.tight_layout()
    plots.append(fig_to_base64(fig))

    # Daily invoices
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.lineplot(data=daily_sales, x='invoice_date', y='num_invoices', marker="o", color='orange', ax=ax)
    ax.set_title("Daily Number of Invoices")
    ax.set_xlabel("Date")
    ax.set_ylabel("Invoices")
    plt.tight_layout()
    plots.append(fig_to_base64(fig))

    # Store-level daily sales (FacetGrid)
    mall_rank = (
        store_daily_sales.groupby('shopping_mall')['total_sales']
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    mall_order = mall_rank['shopping_mall'].tolist()

    g = sns.FacetGrid(
        store_daily_sales,
        col="shopping_mall",
        col_wrap=4,
        height=3,
        sharey=True,
        col_order=mall_order
    )
    g.map_dataframe(sns.lineplot, x="invoice_date", y="sales_ma7")
    g.set_axis_labels("Date", "Sales (7-day avg)")
    g.set_titles("{col_name}")

    for ax in g.axes.flatten():
        if store_daily_sales['invoice_date'].notna().any():
            first_date = store_daily_sales['invoice_date'].min()
            last_date = store_daily_sales['invoice_date'].max()
            ax.set_xticks([first_date, last_date])
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax.tick_params(axis='x', rotation=45)
    plt.tight_layout()

    # Convert FacetGrid to figure
    fig = g.fig
    plots.append(fig_to_base64(fig))
    plt.close(fig)

    # Monthly sales trend
    monthly_sales['year_month'] = monthly_sales['year_month'].astype(str)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.lineplot(data=monthly_sales, x='year_month', y='total_sales', marker="o", ax=ax)
    plt.xticks(rotation=45)
    ax.set_title("Monthly Sales Trend")
    ax.set_xlabel("Month")
    ax.set_ylabel("Total Sales")
    plt.tight_layout()
    plots.append(fig_to_base64(fig))

    # Quarterly YOY comparison
    quarterly_sales['year_quarter'] = quarterly_sales['year_quarter'].astype(str)
    quarterly_sales['year'] = quarterly_sales['year_quarter'].str[:4]
    quarterly_sales['quarter'] = quarterly_sales['year_quarter'].str[-2:]

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=quarterly_sales, x='quarter', y='total_sales', hue='year', palette='viridis', ax=ax)
    ax.set_title("Quarterly Sales Comparison (YOY)")
    ax.set_xlabel("Quarter")
    ax.set_ylabel("Total Sales")
    ax.legend(title="Year")
    plt.tight_layout()
    plots.append(fig_to_base64(fig))

    # Quarterly sales trend
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=quarterly_sales, x='year_quarter', y='total_sales', palette='viridis', ax=ax)
    ax.set_title("Quarterly Sales Trend")
    ax.set_xlabel("Quarter")
    ax.set_ylabel("Total Sales")
    plt.tight_layout()
    plots.append(fig_to_base64(fig))

    # Yearly sales comparison
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=yearly_sales, x='year', y='total_sales', palette='magma', ax=ax)
    ax.set_title("Yearly Sales Comparison")
    ax.set_xlabel("Year")
    ax.set_ylabel("Total Sales")
    plt.tight_layout()
    plots.append(fig_to_base64(fig))

    # --- Build HTML ---
    html_content = "<html><head><title>Seasonality Analysis</title></head><body>"
    html_content += "<h2>📅 Seasonality Analysis</h2>"
    for img in plots:
        html_content += f"<img src='data:image/png;base64,{img}' style='max-width:100%;height:auto;'><br><br>"
    html_content += "</body></html>"

    return HTMLResponse(content=html_content)


# --------------------------
# Payment Method Preference (Bar Chart Only)
# --------------------------
@app.get("/payment-method-preference", response_class=HTMLResponse)
def payment_method_preference():
    # --- Payment method distribution ---
    payment_dist = (
        df['payment_method']
        .value_counts(normalize=True) * 100
    ).reset_index()
    payment_dist.columns = ['payment_method', 'percentage']

    # --- Plotting ---
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(
        data=payment_dist,
        x='payment_method',
        y='percentage',
        palette='Set2',
        ax=ax
    )
    ax.set_title("Payment Method Preference (%)")
    ax.set_xlabel("Payment Method")
    ax.set_ylabel("Percentage of Transactions")
    plt.tight_layout()

    # Convert figure to base64
    img = fig_to_base64(fig)
    plt.close(fig)

    # --- Build HTML ---
    html_content = f"""
    <html>
        <head><title>Payment Method Preference</title></head>
        <body>
            <h2>💳 Payment Method Preference</h2>
            <img src="data:image/png;base64,{img}" style="max-width:100%;height:auto;">
        </body>
    </html>
    """

    return HTMLResponse(content=html_content)



# --------------------------
# RFM Analysis Endpoint
# --------------------------
@app.get("/rfm-analysis", response_class=HTMLResponse)
def rfm_analysis():
    df_copy = df.copy()
    df_copy['invoice_date'] = pd.to_datetime(df_copy['invoice_date'], errors='coerce')
    df_copy = df_copy.dropna(subset=['invoice_date'])
    df_copy['net_sales'] = df_copy['price'] * df_copy['quantity']

    # Reference date = last transaction + 1 day
    reference_date = df_copy['invoice_date'].max() + dt.timedelta(days=1)

    # Recency
    recency_df = df_copy.groupby('customer_id')['invoice_date'].max().reset_index()
    recency_df['recency'] = (reference_date - recency_df['invoice_date']).dt.days

    # Frequency
    frequency_df = df_copy.groupby('customer_id')['invoice_no'].nunique().reset_index()
    frequency_df.rename(columns={'invoice_no':'frequency'}, inplace=True)

    # Monetary
    monetary_df = df_copy.groupby('customer_id')['net_sales'].sum().reset_index()
    monetary_df.rename(columns={'net_sales':'monetary'}, inplace=True)

    # Merge
    rfm = recency_df.merge(frequency_df, on='customer_id').merge(monetary_df, on='customer_id')

    # Scores using qcut
    rfm['R_score'] = pd.qcut(rfm['recency'], 5, labels=[5,4,3,2,1])
    rfm['F_score'] = pd.qcut(rfm['frequency'].rank(method='first'), 5, labels=[1,2,3,4,5])
    rfm['M_score'] = pd.qcut(rfm['monetary'], 5, labels=[1,2,3,4,5])

    # Convert categories → int safely
    rfm['R_score'] = rfm['R_score'].astype(float).fillna(0).astype(int)
    rfm['F_score'] = rfm['F_score'].astype(float).fillna(0).astype(int)
    rfm['M_score'] = rfm['M_score'].astype(float).fillna(0).astype(int)

    # RFM Segment & Score
    rfm['RFM_Segment'] = rfm['R_score'].astype(str) + rfm['F_score'].astype(str) + rfm['M_score'].astype(str)
    rfm['RFM_Score'] = rfm['R_score'] + rfm['F_score'] + rfm['M_score']

    def segment_customer(score):
        if score >= 12:
            return 'Champions'
        elif score >= 9:
            return 'Loyal'
        elif score >= 6:
            return 'At Risk'
        else:
            return 'Lost'
    rfm['Segment'] = rfm['RFM_Score'].apply(segment_customer)

    # Repeat vs One-time customers
    customer_orders = df_copy.groupby('customer_id')['invoice_no'].nunique().reset_index()
    customer_orders.rename(columns={'invoice_no':'num_invoices'}, inplace=True)
    customer_orders['customer_type'] = np.where(customer_orders['num_invoices']>1, 'Repeat Customer','One-time Customer')
    customer_orders = customer_orders.merge(df_copy.groupby('customer_id')['net_sales'].sum().reset_index(), on='customer_id')

    repeat_vs_one = customer_orders.groupby('customer_type')['net_sales'].sum().reset_index()

    # --- Plotting ---
    plots = []

    # RFM Segments
    fig, ax = plt.subplots(figsize=(8,5))
    sns.countplot(data=rfm, x='Segment', order=rfm['Segment'].value_counts().index, palette="Set2", ax=ax)
    ax.set_title("Customer Segmentation Distribution (RFM)")
    ax.set_ylabel("Number of Customers")
    plt.tight_layout()
    plots.append(fig_to_base64(fig))

    # Build HTML
    html_content = "<html><head><title>RFM Analysis</title></head><body>"
    html_content += "<h2>📊 RFM Customer Analysis</h2>"
    for img in plots:
        html_content += f"<img src='data:image/png;base64,{img}' style='max-width:100%;height:auto;'><br><br>"
    html_content += "</body></html>"

    return HTMLResponse(content=html_content)

# Shared RFM computation
def compute_rfm(df):
    import datetime as dt
    df_copy = df.copy()
    df_copy['invoice_date'] = pd.to_datetime(df_copy['invoice_date'], errors='coerce')
    df_copy = df_copy.dropna(subset=['invoice_date'])
    df_copy['net_sales'] = df_copy['price'] * df_copy['quantity']

    reference_date = df_copy['invoice_date'].max() + dt.timedelta(days=1)

    recency_df = df_copy.groupby('customer_id')['invoice_date'].max().reset_index()
    recency_df['recency'] = (reference_date - recency_df['invoice_date']).dt.days

    frequency_df = df_copy.groupby('customer_id')['invoice_no'].nunique().reset_index()
    frequency_df.rename(columns={'invoice_no':'frequency'}, inplace=True)

    monetary_df = df_copy.groupby('customer_id')['net_sales'].sum().reset_index()
    monetary_df.rename(columns={'net_sales':'monetary'}, inplace=True)

    rfm = recency_df.merge(frequency_df, on='customer_id').merge(monetary_df, on='customer_id')

    rfm['R_score'] = pd.qcut(rfm['recency'], 5, labels=[5,4,3,2,1]).astype(float).fillna(0).astype(int)
    rfm['F_score'] = pd.qcut(rfm['frequency'].rank(method='first'), 5, labels=[1,2,3,4,5]).astype(float).fillna(0).astype(int)
    rfm['M_score'] = pd.qcut(rfm['monetary'], 5, labels=[1,2,3,4,5]).astype(float).fillna(0).astype(int)

    rfm['RFM_Score'] = rfm['R_score'] + rfm['F_score'] + rfm['M_score']

    def segment_customer(score):
        if score >= 12:
            return 'Champions'
        elif score >= 9:
            return 'Loyal'
        elif score >= 6:
            return 'At Risk'
        else:
            return 'Lost'

    rfm['Segment'] = rfm['RFM_Score'].apply(segment_customer)

    return rfm[['customer_id','Segment']]

# --------------------------
# Category Insights Endpoint
# --------------------------
@app.get("/category-insights", response_class=HTMLResponse)
def category_insights():
    df_copy = df.copy()
    df_copy['net_sales'] = df_copy['price'] * df_copy['quantity']

    
    # Compute RFM segments
    rfm_segments = compute_rfm(df_copy)
    
    # Merge segment info
    df_with_segments = df_copy.merge(rfm_segments, on='customer_id', how='left')
    
    # Category-wise aggregation
    category_perf = (
        df_with_segments.groupby('category')
        .agg(
            total_sales=('net_sales', 'sum'),
            total_qty=('quantity', 'sum'),
            num_customers=('customer_id', 'nunique'),
            num_invoices=('invoice_no', 'nunique')
        )
        .reset_index()
    )
    category_perf['avg_order_value'] = category_perf['total_sales'] / category_perf['num_invoices']
    
    # Category × RFM Segment performance
    cat_segment_perf = (
        df_with_segments.groupby(['category','Segment'])
        .agg(total_sales=('net_sales','sum'))
        .reset_index()
    )
    cat_segment_perf['pct_within_category'] = (
        cat_segment_perf.groupby('category')['total_sales']
        .transform(lambda x: x / x.sum() * 100)
    )
    
    # --- Plotting ---
    plots = []

    # 1️⃣ Total Sales by Category
    fig, ax = plt.subplots(figsize=(10,6))
    sns.barplot(
        data=category_perf.sort_values('total_sales', ascending=False),
        x='category', y='total_sales', palette='viridis', ax=ax
    )
    ax.set_title("Total Sales by Category")
    ax.set_xlabel("Category")
    ax.set_ylabel("Total Sales")
    ax.tick_params(axis='x', rotation=45)
    plt.tight_layout()
    plots.append(fig_to_base64(fig))

    # 2️⃣ Average Order Value by Category
    fig, ax = plt.subplots(figsize=(10,6))
    sns.barplot(
        data=category_perf.sort_values('avg_order_value', ascending=False),
        x='category', y='avg_order_value', palette='coolwarm', ax=ax
    )
    ax.set_title("Average Order Value by Category")
    ax.set_xlabel("Category")
    ax.set_ylabel("Average Order Value")
    ax.tick_params(axis='x', rotation=45)
    plt.tight_layout()
    plots.append(fig_to_base64(fig))

    # 3️⃣ Category Preferences by Customer Segment (Heatmap)
    pivot_table = cat_segment_perf.pivot(index='category', columns='Segment', values='pct_within_category').fillna(0)
    fig, ax = plt.subplots(figsize=(10,6))
    sns.heatmap(pivot_table, annot=True, fmt=".1f", cmap="YlGnBu", ax=ax)
    ax.set_title("Category Preferences by Customer Segment (%)")
    ax.set_xlabel("Customer Segment")
    ax.set_ylabel("Category")
    plt.tight_layout()
    plots.append(fig_to_base64(fig))

    # --- Build HTML ---
    html_content = "<html><head><title>Category Insights</title></head><body>"
    html_content += "<h2>📊 Category-wise Insights</h2>"
    for img in plots:
        html_content += f"<img src='data:image/png;base64,{img}' style='max-width:100%;height:auto;'><br><br>"
    html_content += "</body></html>"

    return HTMLResponse(content=html_content)

# --------------------------
# Campaign Simulation endpoint
# --------------------------
@app.get("/campaign-simulation", response_class=HTMLResponse)
def campaign_simulation():
    """
    Campaign Simulation: Target top 10% customers with 10% discount
    Model ROI based on response rate and uplift in spend
    """
    df_copy = df.copy()
    
    # Ensure net_sales exists
    df_copy['net_sales'] = df_copy['price'] * df_copy['quantity']
    
    # Summarize total spent per customer
    customer_summary = (
        df_copy.groupby('customer_id')['net_sales']
        .sum()
        .reset_index()
        .rename(columns={'net_sales': 'total_spent'})
    )
    
    # Identify top 10% customers by spend
    customer_summary_sorted = customer_summary.sort_values('total_spent', ascending=False)
    top_10_cutoff = int(len(customer_summary_sorted) * 0.1)
    top_customers = customer_summary_sorted.head(top_10_cutoff)
    
    # Baseline revenue from top 10% customers
    baseline_revenue = top_customers['total_spent'].sum()
    
    # Campaign parameters
    discount_rate = 0.10  # 10% discount
    
    # Simulate different scenarios
    response_rates = np.arange(0.05, 0.55, 0.05)   # 5% to 50% response rate
    uplift_levels  = np.arange(0.05, 0.55, 0.05)   # 5% to 50% uplift in spend
    
    # ROI Calculation for each scenario
    results = []
    for response_rate in response_rates:
        for uplift in uplift_levels:
            # Number of customers who respond
            responding_customers = top_10_cutoff * response_rate
            
            # Revenue from responding customers
            avg_spend_per_customer = baseline_revenue / top_10_cutoff
            
            # Additional revenue from uplift (responding customers spend more)
            additional_revenue = responding_customers * avg_spend_per_customer * uplift
            
            # Cost of campaign: discount given to all responding customers
            # They get 10% off on their increased spending
            new_spend_per_customer = avg_spend_per_customer * (1 + uplift)
            discount_cost = responding_customers * new_spend_per_customer * discount_rate
            
            # Net gain/loss
            net_gain = additional_revenue - discount_cost
            
            # ROI = (Net Gain / Cost) * 100
            roi = (net_gain / discount_cost * 100) if discount_cost > 0 else 0
            
            results.append([response_rate, uplift, roi])
    
    # Create DataFrame and pivot for heatmap
    results_df = pd.DataFrame(results, columns=['ResponseRate', 'Uplift', 'ROI'])
    roi_pivot = results_df.pivot(index='ResponseRate', columns='Uplift', values='ROI')
    
    # Plot heatmap
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(roi_pivot, cmap="RdYlGn", aspect="auto", origin="lower", vmin=-100, vmax=300)
    
    ax.set_title("ROI Simulation: 10% Discount Campaign on Top 10% Customers", fontsize=14, fontweight='bold')
    ax.set_xlabel("Uplift in Spend (%)", fontsize=12)
    ax.set_ylabel("Response Rate (%)", fontsize=12)
    
    # Set ticks
    ax.set_xticks(np.arange(len(uplift_levels)))
    ax.set_xticklabels([f"{u*100:.0f}%" for u in uplift_levels], rotation=45)
    ax.set_yticks(np.arange(len(response_rates)))
    ax.set_yticklabels([f"{r*100:.0f}%" for r in response_rates])
    
    # Add colorbar
    cbar = fig.colorbar(im, label="ROI (%)")
    
    # Add annotations for key values
    for i in range(len(response_rates)):
        for j in range(len(uplift_levels)):
            text = ax.text(j, i, f"{roi_pivot.iloc[i, j]:.0f}",
                          ha="center", va="center", color="black", fontsize=8)
    
    plt.tight_layout()
    
    # Convert figure to base64
    import io, base64
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    
    # Summary statistics
    best_roi_idx = results_df['ROI'].idxmax()
    best_scenario = results_df.loc[best_roi_idx]
    
    # Build HTML with summary
    html_content = f"""
    <html>
        <head>  
            <title>Campaign Simulation</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                }}
                .summary {{
                    background-color: #f0f8ff;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .metric {{
                    font-weight: bold;
                    color: #031278;
                }}
            </style>
        </head>
        <body>
            <h2>💰 Campaign Simulation: ROI Analysis</h2>
            
            <div class="summary">
                <h3>Campaign Details</h3>
                <p><span class="metric">Target Audience:</span> Top 10% customers ({top_10_cutoff:,} customers)</p>
                <p><span class="metric">Baseline Revenue (Top 10%):</span> ${baseline_revenue:,.2f}</p>
                <p><span class="metric">Discount Offered:</span> 10%</p>
                <p><span class="metric">Average Spend per Customer:</span> ${baseline_revenue/top_10_cutoff:,.2f}</p>
            </div>
            
            <div class="summary">
                <h3>Best Case Scenario</h3>
                <p><span class="metric">Response Rate:</span> {best_scenario['ResponseRate']*100:.0f}%</p>
                <p><span class="metric">Uplift in Spend:</span> {best_scenario['Uplift']*100:.0f}%</p>
                <p><span class="metric">Projected ROI:</span> {best_scenario['ROI']:.1f}%</p>
            </div>
            
            <img src="data:image/png;base64,{img_base64}" style="max-width:100%;height:auto;">
            
            <div style="margin-top: 20px;">
                <h3>Key Insights</h3>
                <ul>
                    <li>The campaign becomes profitable when uplift exceeds ~10% (breaking even on discount cost)</li>
                    <li>Higher response rates amplify both gains and costs</li>
                    <li>ROI is maximized at high response rates with high uplift in customer spending</li>
                    <li>Negative ROI (blue zones) occurs when uplift is insufficient to cover discount costs</li>
                </ul>
            </div>
        </body>
    </html>
    """
    

    return HTMLResponse(content=html_content)


