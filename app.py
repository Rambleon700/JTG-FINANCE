import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Daily Portfolio Tracker", layout="wide")
st.title("📈 Historical Daily Portfolio Tracker")

# Instructions for CSV Format
st.sidebar.header("1. Data Import")
st.sidebar.markdown("""
**CSV Format Required:**
- `Ticker` (e.g., AAPL, VOO, MSFT)
- `Type` (e.g., Share, ETF)
- `Quantity` (number of shares)
- `Purchase Price` (cost per share)
""")

uploaded_file = st.sidebar.file_uploader("Upload Portfolio CSV", type=["csv"])

# Sidebar filter for time range
time_range = st.sidebar.selectbox(
    "Historical Time Range",
    options=["1M", "3M", "6M", "1Y", "2Y", "5Y", "Max"],
    index=3
)

time_range_mapping = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
    "2Y": "2y",
    "5Y": "5y",
    "Max": "max"
}

@st.cache_data(ttl=3600)
def fetch_historical_prices(tickers, period):
    """Fetch daily closing prices for all tickers over selected time range."""
    try:
        # Fetch multi-ticker historical data
        data = yf.download(tickers, period=period, progress=False)["Close"]
        
        # If single ticker, convert Series to DataFrame
        if isinstance(data, pd.Series):
            data = data.to_frame(name=tickers[0])
            
        # Clean up missing values (ffill for non-trading days/gaps)
        data = data.ffill().bfill()
        return data
    except Exception as e:
        st.error(f"Error fetching historical market data: {e}")
        return pd.DataFrame()

if uploaded_file is not None:
    # Load portfolio data
    df = pd.read_csv(uploaded_file)
    
    # Clean column names
    df.columns = df.columns.str.strip().str.title()
    
    required_cols = {"Ticker", "Type", "Quantity", "Purchase Price"}
    if not required_cols.issubset(df.columns):
        st.error(f"CSV missing required columns: {required_cols - set(df.columns)}")
    else:
        # Group duplicates by Ticker (if user bought same asset multiple times)
        portfolio_summary = df.groupby(["Ticker", "Type"]).apply(
            lambda x: pd.Series({
                "Quantity": x["Quantity"].sum(),
                "Book Cost": (x["Quantity"] * x["Purchase Price"]).sum(),
                "Avg Purchase Price": (x["Quantity"] * x["Purchase Price"]).sum() / x["Quantity"].sum()
            })
        ).reset_index()

        tickers = portfolio_summary["Ticker"].tolist()

        with st.spinner("Downloading historical prices..."):
            hist_prices = fetch_historical_prices(tickers, period=time_range_mapping[time_range])

        if not hist_prices.empty:
            # Calculate daily value for each holding over time
            daily_asset_values = pd.DataFrame(index=hist_prices.index)

            for _, row in portfolio_summary.iterrows():
                ticker = row["Ticker"]
                qty = row["Quantity"]
                if ticker in hist_prices.columns:
                    daily_asset_values[ticker] = hist_prices[ticker] * qty

            # Calculate total daily portfolio value
            daily_portfolio_value = daily_asset_values.sum(axis=1)

            # Get current metrics from latest historical date
            latest_prices = hist_prices.iloc[-1]
            portfolio_summary["Current Price"] = portfolio_summary["Ticker"].map(latest_prices)
            portfolio_summary["Current Value"] = portfolio_summary["Quantity"] * portfolio_summary["Current Price"]
            portfolio_summary["Gain/Loss ($)"] = portfolio_summary["Current Value"] - portfolio_summary["Book Cost"]
            portfolio_summary["Gain/Loss (%)"] = (portfolio_summary["Gain/Loss ($)"] / portfolio_summary["Book Cost"]) * 100

            # Overall Totals
            total_book_cost = portfolio_summary["Book Cost"].sum()
            total_current_value = portfolio_summary["Current Value"].sum()
            total_gain_loss = total_current_value - total_book_cost
            total_percentage = (total_gain_loss / total_book_cost * 100) if total_book_cost > 0 else 0

            # --- Section 1: Top Metrics Dashboard ---
            st.header("Overall Portfolio Performance")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Book Cost", f"${total_book_cost:,.2f}")
            col2.metric("Total Current Value", f"${total_current_value:,.2f}")
            col3.metric("Overall Gain / Loss ($)", f"${total_gain_loss:,.2f}", delta=f"${total_gain_loss:,.2f}")
            col4.metric("Overall Return (%)", f"{total_percentage:.2f}%", delta=f"{total_percentage:.2f}%")

            st.markdown("---")

            # --- Section 2: Historical Trend Charts ---
            st.header("📈 Historical Portfolio Growth")
            
            # Line Chart: Total Portfolio Value Over Time vs Book Cost
            fig_total = go.Figure()
            fig_total.add_trace(go.Scatter(
                x=daily_portfolio_value.index,
                y=daily_portfolio_value.values,
                mode="lines",
                name="Portfolio Value ($)",
                line=dict(color="#00CC96", width=2.5)
            ))
            # Draw baseline for total book cost
            fig_total.add_hline(
                y=total_book_cost, 
                line_dash="dash", 
                line_color="red", 
                annotation_text=f"Book Cost (${total_book_cost:,.2f})", 
                annotation_position="bottom right"
            )
            fig_total.update_layout(
                title="Total Portfolio Value Over Time",
                xaxis_title="Date",
                yaxis_title="Value ($)",
                hovermode="x unified"
            )
            st.plotly_chart(fig_total, use_container_width=True)

            # Stacked Area Chart: Asset Breakdown Over Time
            fig_breakdown = px.area(
                daily_asset_values,
                x=daily_asset_values.index,
                y=daily_asset_values.columns,
                title="Individual Asset Value Contribution Over Time",
                labels={"value": "Value ($)", "variable": "Ticker", "index": "Date"}
            )
            fig_breakdown.update_layout(hovermode="x unified")
            st.plotly_chart(fig_breakdown, use_container_width=True)

            st.markdown("---")

            # --- Section 3: Distribution & Breakdown Table ---
            col_chart1, col_chart2 = st.columns(2)

            with col_chart1:
                st.subheader("Current Asset Allocation")
                fig_pie = px.pie(
                    portfolio_summary, 
                    values="Current Value", 
                    names="Ticker", 
                    hole=0.4,
                    title="Allocation by Current Market Value"
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_chart2:
                st.subheader("Gain / Loss by Position")
                fig_bar = px.bar(
                    portfolio_summary, 
                    x="Ticker", 
                    y="Gain/Loss ($)", 
                    color="Gain/Loss ($)",
                    color_continuous_scale=["#FF2B2B", "#00CC96"],
                    title="Profit / Loss per Asset ($)"
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            # Detailed Table
            st.subheader("Holdings Summary")
            st.dataframe(
                portfolio_summary.style.format({
                    "Quantity": "{:,.2f}",
                    "Avg Purchase Price": "${:,.2f}",
                    "Current Price": "${:,.2f}",
                    "Book Cost": "${:,.2f}",
                    "Current Value": "${:,.2f}",
                    "Gain/Loss ($)": "${:,.2f}",
                    "Gain/Loss (%)": "{:,.2f}%"
                }),
                use_container_width=True
            )

else:
    st.info("Please upload a CSV file in the sidebar to view your historical portfolio tracking.")
