import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os

st.set_page_config(page_title="Daily Portfolio Tracker", layout="wide")
st.title("📈 Historical Daily Portfolio Tracker")

# Local Storage Directory Setup
DATA_DIR = ".data"
DATA_FILE = os.path.join(DATA_DIR, "saved_portfolio.csv")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Helper function to save DataFrame to CSV
def save_portfolio_df(df_to_save):
    df_to_save.to_csv(DATA_FILE, index=False)

# Helper function to load DataFrame
def load_portfolio_df():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        df.columns = df.columns.str.strip().str.title()
        return df
    return pd.DataFrame(columns=["Ticker", "Type", "Quantity", "Purchase Price"])

# Load current state into session state or disk
if "portfolio_df" not in st.session_state:
    st.session_state.portfolio_df = load_portfolio_df()

# Sidebar: Controls & Data Management
st.sidebar.header("1. Data Management")

# --- Tab 1: CSV Upload / Tab 2: Manual Form ---
manage_mode = st.sidebar.radio("Data Mode", ["Edit Holdings Manually", "Upload CSV File"])

if manage_mode == "Upload CSV File":
    uploaded_file = st.sidebar.file_uploader("Upload Portfolio CSV", type=["csv"])
    if uploaded_file is not None:
        new_df = pd.read_csv(uploaded_file)
        new_df.columns = new_df.columns.str.strip().str.title()
        required_cols = {"Ticker", "Type", "Quantity", "Purchase Price"}
        if required_cols.issubset(new_df.columns):
            st.session_state.portfolio_df = new_df[list(required_cols)]
            save_portfolio_df(st.session_state.portfolio_df)
            st.sidebar.success("Uploaded CSV saved!")
            st.rerun()
        else:
            st.sidebar.error(f"CSV missing columns: {required_cols - set(new_df.columns)}")

else:
    # Manual Holdings Editor
    st.sidebar.subheader("➕ Add / Update Holding")
    with st.sidebar.form(key="add_holding_form", clear_on_submit=True):
        ticker_input = st.text_input("Ticker Symbol (e.g., AAPL, VOO)").upper().strip()
        asset_type = st.selectbox("Asset Type", ["Share", "ETF", "Crypto", "Other"])
        quantity_input = st.number_input("Quantity", min_value=0.0, step=1.0, format="%.4f")
        price_input = st.number_input("Purchase Price ($)", min_value=0.0, step=1.0, format="%.2f")
        
        submit_button = st.form_submit_button(label="Save Position")
        
        if submit_button:
            if ticker_input and quantity_input > 0:
                df_current = st.session_state.portfolio_df.copy()
                
                # Check if ticker already exists
                if not df_current.empty and ticker_input in df_current["Ticker"].values:
                    # Update existing row
                    df_current.loc[df_current["Ticker"] == ticker_input, ["Type", "Quantity", "Purchase Price"]] = [
                        asset_type, quantity_input, price_input
                    ]
                    st.sidebar.success(f"Updated {ticker_input}!")
                else:
                    # Append new position
                    new_row = pd.DataFrame([{
                        "Ticker": ticker_input,
                        "Type": asset_type,
                        "Quantity": quantity_input,
                        "Purchase Price": price_input
                    }])
                    df_current = pd.concat([df_current, new_row], ignore_index=True)
                    st.sidebar.success(f"Added {ticker_input}!")
                
                st.session_state.portfolio_df = df_current
                save_portfolio_df(df_current)
                st.rerun()
            else:
                st.sidebar.error("Please provide a valid ticker and quantity.")

    # Delete Holding Section
    if not st.session_state.portfolio_df.empty:
        st.sidebar.subheader("🗑️ Delete Holding")
        ticker_to_delete = st.sidebar.selectbox(
            "Select position to remove",
            options=st.session_state.portfolio_df["Ticker"].tolist()
        )
        if st.sidebar.button("Remove Position"):
            df_current = st.session_state.portfolio_df.copy()
            df_current = df_current[df_current["Ticker"] != ticker_to_delete]
            st.session_state.portfolio_df = df_current
            save_portfolio_df(df_current)
            st.sidebar.warning(f"Removed {ticker_to_delete}")
            st.rerun()

# Clear All Data Option
if not st.session_state.portfolio_df.empty:
    st.sidebar.markdown("---")
    if st.sidebar.button("🚨 Clear Entire Portfolio"):
        st.session_state.portfolio_df = pd.DataFrame(columns=["Ticker", "Type", "Quantity", "Purchase Price"])
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        st.rerun()

# Time Range Selector
st.sidebar.markdown("---")
time_range = st.sidebar.selectbox(
    "Historical Time Range",
    options=["1M", "3M", "6M", "1Y", "2Y", "5Y", "Max"],
    index=3
)

time_range_mapping = {
    "1M": "1mo", "3M": "3mo", "6M": "6mo",
    "1Y": "1y", "2Y": "2y", "5Y": "5y", "Max": "max"
}

@st.cache_data(ttl=3600)
def fetch_historical_prices(tickers, period):
    """Fetch daily closing prices for all tickers over selected time range."""
    try:
        data = yf.download(tickers, period=period, progress=False)["Close"]
        if isinstance(data, pd.Series):
            data = data.to_frame(name=tickers[0])
        data = data.ffill().bfill()
        return data
    except Exception as e:
        st.error(f"Error fetching market data: {e}")
        return pd.DataFrame()

# Main Logic: Render Dashboard if portfolio has holdings
df_holdings = st.session_state.portfolio_df

if not df_holdings.empty:
    # Group holdings by Ticker
    portfolio_summary = df_holdings.groupby(["Ticker", "Type"]).apply(
        lambda x: pd.Series({
            "Quantity": x["Quantity"].sum(),
            "Book Cost": (x["Quantity"] * x["Purchase Price"]).sum(),
            "Avg Purchase Price": (x["Quantity"] * x["Purchase Price"]).sum() / x["Quantity"].sum()
        })
    ).reset_index()

    tickers = portfolio_summary["Ticker"].tolist()

    with st.spinner("Downloading market prices..."):
        hist_prices = fetch_historical_prices(tickers, period=time_range_mapping[time_range])

    if not hist_prices.empty:
        # Calculate daily value for each asset over time
        daily_asset_values = pd.DataFrame(index=hist_prices.index)
        for _, row in portfolio_summary.iterrows():
            ticker = row["Ticker"]
            qty = row["Quantity"]
            if ticker in hist_prices.columns:
                daily_asset_values[ticker] = hist_prices[ticker] * qty

        daily_portfolio_value = daily_asset_values.sum(axis=1)

        # Latest Market Price Calculations
        latest_prices = hist_prices.iloc[-1]
        portfolio_summary["Current Price"] = portfolio_summary["Ticker"].map(latest_prices)
        portfolio_summary["Current Value"] = portfolio_summary["Quantity"] * portfolio_summary["Current Price"]
        portfolio_summary["Gain/Loss ($)"] = portfolio_summary["Current Value"] - portfolio_summary["Book Cost"]
        portfolio_summary["Gain/Loss (%)"] = (portfolio_summary["Gain/Loss ($)"] / portfolio_summary["Book Cost"]) * 100

        # Totals
        total_book_cost = portfolio_summary["Book Cost"].sum()
        total_current_value = portfolio_summary["Current Value"].sum()
        total_gain_loss = total_current_value - total_book_cost
        total_percentage = (total_gain_loss / total_book_cost * 100) if total_book_cost > 0 else 0

        # --- Summary Metrics ---
        st.header("Overall Portfolio Performance")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Book Cost", f"${total_book_cost:,.2f}")
        col2.metric("Total Current Value", f"${total_current_value:,.2f}")
        col3.metric("Overall Gain / Loss ($)", f"${total_gain_loss:,.2f}", delta=f"${total_gain_loss:,.2f}")
        col4.metric("Overall Return (%)", f"{total_percentage:.2f}%", delta=f"{total_percentage:.2f}%")

        st.markdown("---")

        # --- Historical Charts ---
        st.header("📈 Historical Portfolio Growth")
        
        # Line Chart: Total Portfolio Value
        fig_total = go.Figure()
        fig_total.add_trace(go.Scatter(
            x=daily_portfolio_value.index,
            y=daily_portfolio_value.values,
            mode="lines",
            name="Portfolio Value ($)",
            line=dict(color="#00CC96", width=2.5)
        ))
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

        # Stacked Area Chart: Individual Contributions
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

        # --- Distribution & Breakdown Table ---
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

        # Table
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
    st.info("Your portfolio is currently empty. Use the sidebar on the left to add your first position or upload a CSV file.")
