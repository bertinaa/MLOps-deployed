# app_combined.py - Run FastAPI backend within Streamlit
import streamlit as st
import requests
from bs4 import BeautifulSoup
import base64
from io import BytesIO
from PIL import Image
import threading
import uvicorn
import time

# Import the FastAPI app
from main import app as fastapi_app

# FastAPI server URL
API_BASE_URL = "http://localhost:8000"

# Function to run FastAPI in background
def run_fastapi():
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000, log_level="error")

# Start FastAPI server in a background thread (only once)
if 'fastapi_started' not in st.session_state:
    st.session_state.fastapi_started = True
    thread = threading.Thread(target=run_fastapi, daemon=True)
    thread.start()
    time.sleep(3)  # Give FastAPI time to start

# Configure Streamlit page
st.set_page_config(
    page_title="Shopping Mall Analytics Dashboard",
    page_icon="🛍️",
    layout="wide"
)

def fetch_html_content(endpoint):
    """Fetch HTML content from FastAPI endpoint"""
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from {endpoint}: {str(e)}")
        return None

def extract_images_from_html(html_content):
    """Extract base64 images from HTML content"""
    if not html_content:
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    images = []
    
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if 'data:image/png;base64,' in src:
            base64_str = src.split('data:image/png;base64,')[1]
            images.append(base64_str)
    
    return images

def display_base64_image(base64_str):
    """Display base64 encoded image"""
    try:
        img_data = base64.b64decode(base64_str)
        img = Image.open(BytesIO(img_data))
        st.image(img, use_container_width=True)
    except Exception as e:
        st.error(f"Error displaying image: {str(e)}")

def extract_tables_from_html(html_content):
    """Extract tables from HTML content"""
    if not html_content:
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.find_all('table')

# Title
st.title("🛍️ Shopping Mall Analytics Dashboard")
st.markdown("---")

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Select Analysis:",
    [
        "Home",
        "Mall & Region Performance",
        "Repeat vs One-time Customers",
        "Category Insights",
        "Top Customers Analysis",
        "Value Segmentation",
        "Seasonality Analysis",
        "Payment Method Preference",
        "RFM Analysis",
        "Campaign Simulation"
    ]
)

# Home Page
if page == "Home":
    st.header("Welcome to Shopping Mall Analytics")
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=5)
        if response.status_code == 200:
            st.success("✅ API Connected Successfully")
        else:
            st.error("Unable to connect to API")
    except:
        st.warning("⏳ Starting API server... Please refresh in a moment.")
    
    st.markdown("""
    ### Available Analytics:
    - **Mall & Region Performance**: Visual comparison of sales across malls and regions
    - **Repeat vs One-time Customers**: Customer retention analysis
    - **Category Insights**: Product category performance metrics and charts
    - **Top Customers Analysis**: Identify and analyze high-value customers
    - **Value Segmentation**: Customer segmentation by spending patterns
    - **Seasonality Analysis**: Time-based sales trends (daily, monthly, quarterly, yearly)
    - **Payment Method Preference**: Payment method distribution
    - **RFM Analysis**: Recency, Frequency, Monetary customer segmentation
    - **Campaign Simulation**: ROI simulation for targeted campaigns
    
    Use the sidebar to navigate between different analytics views.
    """)

# Mall & Region Performance
elif page == "Mall & Region Performance":
    st.header("Mall & Region Performance")
    html_content = fetch_html_content("/mall-region-performance")
    
    if html_content:
        images = extract_images_from_html(html_content)
        if images:
            for idx, img in enumerate(images):
                if idx == 0:
                    st.subheader("Total Sales by Shopping Mall")
                elif idx == 1:
                    st.subheader("Total Sales by Region")
                display_base64_image(img)
                st.markdown("---")

# Repeat vs One-time Customers
elif page == "Repeat vs One-time Customers":
    st.header("Repeat vs One-time Customers")
    html_content = fetch_html_content("/repeat-vs-one-html")
    
    if html_content:
        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table')
        if table:
            st.markdown(str(table), unsafe_allow_html=True)

# Category Insights (Charts)
elif page == "Category Insights":
    st.header("Category Insights - Visual Analysis")
    html_content = fetch_html_content("/category-insights")
    
    if html_content:
        images = extract_images_from_html(html_content)
        titles = [
            "Total Sales by Category",
            "Average Order Value by Category",
            "Category Preferences by Customer Segment"
        ]
        
        for idx, img in enumerate(images):
            if idx < len(titles):
                st.subheader(titles[idx])
            display_base64_image(img)
            st.markdown("---")

# Top Customers Analysis
elif page == "Top Customers Analysis":
    st.header("Top Customers Analysis")
    html_content = fetch_html_content("/top-customers")
    
    if html_content:
        images = extract_images_from_html(html_content)
        titles = [
            "🏆 Top 10 Customers by Spend",
            "📊 Revenue Contribution by Segment",
            "📈 Cumulative Revenue Contribution"
        ]
        
        for idx, img in enumerate(images):
            if idx < len(titles):
                st.subheader(titles[idx])
            display_base64_image(img)
            st.markdown("---")

# Value Segmentation
elif page == "Value Segmentation":
    st.header("Value Segmentation")
    html_content = fetch_html_content("/value-segmentation")
    
    if html_content:
        images = extract_images_from_html(html_content)
        if images:
            st.subheader("💰 Revenue Contribution by Customer Segments")
            display_base64_image(images[0])

# Seasonality Analysis
elif page == "Seasonality Analysis":
    st.header("📅 Seasonality Analysis")
    html_content = fetch_html_content("/seasonality-analysis")
    
    if html_content:
        images = extract_images_from_html(html_content)
        titles = [
            "Daily Total Sales",
            "Daily Number of Invoices",
            "Monthly Sales Trend",
            "Quarterly Sales Comparison (YOY)",
            "Quarterly Sales Trend",
            "Yearly Sales Comparison"
        ]
        
        for idx, img in enumerate(images):
            if idx < len(titles):
                st.subheader(titles[idx])
            display_base64_image(img)
            st.markdown("---")

# Payment Method Preference
elif page == "Payment Method Preference":
    st.header("💳 Payment Method Preference")
    html_content = fetch_html_content("/payment-method-preference")
    
    if html_content:
        images = extract_images_from_html(html_content)
        if images:
            display_base64_image(images[0])

# RFM Analysis
elif page == "RFM Analysis":
    st.header("📊 RFM Customer Analysis")
    html_content = fetch_html_content("/rfm-analysis")
    
    if html_content:
        images = extract_images_from_html(html_content)
        if images:
            st.subheader("Customer Segmentation Distribution (RFM)")
            display_base64_image(images[0])

# Campaign Simulation
elif page == "Campaign Simulation":
    st.header("Campaign Simulation - High-Value Customer Targeting")
    html_content = fetch_html_content("/campaign-simulation")
    
    if html_content:
        images = extract_images_from_html(html_content)
        if images:
            st.subheader("ROI Heatmap: 10% Discount Campaign on Top 10% Customers")
            display_base64_image(images[0])
            st.info("""
            **Campaign Model**: Target high-value customers (top 10% by spend) with a 10% discount.
            
            This heatmap shows the projected ROI for different scenarios:
            - **Response Rate (Y-axis)**: % of targeted customers who respond to the campaign
            - **Uplift in Spend (X-axis)**: % increase in spending from responding customers
            
            """)

# Footer
st.sidebar.markdown("---")
