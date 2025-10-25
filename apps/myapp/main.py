import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
from polygon import RESTClient
import datetime as dt
import time
from dateutil.relativedelta import relativedelta
import exchange_calendars as xcals
import streamlit as st
from utilities import *


##########################################################
####### Setting up global variables ######################
##########################################################

polygon_keys = st.secrets.get("polygon_keys") if "polygon_keys" in st.secrets else os.getenv("polygon_keys")

Clients = [RESTClient(key) for key in polygon_keys]

nb_api_keys = len(Clients)
ledger = pd.DataFrame(columns=["Asset","In_Out","Concept","Date", "Open_Close","Amount_Quantity", "Price"])

api_key_index = 0

###########################################################
############### App #######################################
###########################################################

st.set_page_config(page_title="Covered Call Backtest (Layout Only)", layout="wide")
st.title("📈 Covered Call Backtest — Layout Only")

with st.sidebar:
    st.header("Parameters")
    stock_ticker = st.text_input("Stock ticker", value="AAPL")
    market_ticker = st.selectbox("Market calendar", options=["XNAS","XNYS","XASE","XARC","XBOS"], index=0)
    strategy_start_date = st.date_input("Strategy start date", value=dt.date(2024, 1, 2))
    strategy_duration = st.number_input("Strategy duration (months)", value=3, min_value=1, max_value=60, step=1)
    relative_strike_price = st.number_input("Relative strike (e.g., 1.01 = 1% OTM)", value=1.01, min_value=0.5, max_value=3.0, step=0.01)
    num_shares = st.number_input("Initial target shares", value=10000, min_value=0, step=100)
    expiration_index = st.number_input("Expiration index in window (0=first)", value=0, min_value=0, step=1)

    st.divider()
    st.subheader("Premium source")
    premium_source = st.radio("Premium (Polygon keys available)", ["Polygon (historical vwap)"], index=0)
    band = st.number_input("Strike selection band (USD)", value=10.0, min_value=0.5, max_value=100.0, step=0.5)

    st.divider()
    debug = st.checkbox("Show debug messages", value=False)

    compute = st.button("▶️ Compute", type="primary")

# Right-side panel (currently placeholder only)
placeholder = st.empty()


if compute:

    ################################################################################
    ################### Setting up global variables ################################
    ################################################################################
    start_ts = pd.Timestamp(strategy_start_date)  # robust: works for date/str/Timestamp

    strategy_end_date = start_ts + relativedelta(months=int(strategy_duration))
    cal_end_date = start_ts + relativedelta(months=int(strategy_duration) + 3)

    strategy_start_date = start_ts
    current_date = start_ts
    # Only different thing that we need to consider, if current_date == start_date, is that we need to put cash in, based on target number of shares
    #strategy_end_date = pd.Timestamp(
    #    dt.datetime.strptime(strategy_start_date, "%Y-%m-%d") + relativedelta(months=strategy_duration))
    print(f"Strategy_end_date : {strategy_end_date}")
    #cal_end_date = pd.Timestamp(
    #    dt.datetime.strptime(strategy_start_date, "%Y-%m-%d") + relativedelta(months=strategy_duration + 3))
    print(f"cal_end_date : {cal_end_date}")
    #strategy_start_date = pd.Timestamp(strategy_start_date)
    #current_date = strategy_start_date

    # Get the calendar
    cal = list(xcals.get_calendar(market_ticker).sessions_in_range(strategy_start_date, cal_end_date))

    nb_api_keys = len(Clients)
    ledger = pd.DataFrame(columns=["Asset", "In_Out", "Concept", "Date", "Open_Close", "Amount_Quantity", "Price"])

    api_key_index = 0

    while current_date <= strategy_end_date:
        spot_price = list(
            yf.download(stock_ticker, start=current_date, end=next_trading_day(cal, current_date))["Open"][
                stock_ticker])[0]

        #######################################################################
        ################### How many shares do we buy ? #######################
        #######################################################################

        # Two options: - if we just start, we pull the amount of cash needed to by num_shares, defined at the beginning.
        #              - else, we recalculate num_shares based on how much cash we have on hand.

        if current_date == strategy_start_date:
            # Adding the cash into our account
            row = pd.DataFrame([["Cash", "In", "Inflow", current_date, "Open", spot_price * num_shares, None]],
                               columns=ledger.columns)
            ledger = pd.concat([ledger, row])
        else:
            num_shares = current_cash_position(ledger) // spot_price

        # we buy the amount of shares that we can
        spot_price = list(
            yf.download(stock_ticker, start=current_date, end=next_trading_day(cal, current_date))["Open"][
                stock_ticker])[0]
        # Purchasing the stock
        row = pd.DataFrame([[stock_ticker, "In", "Purchase", current_date, "Open", num_shares, spot_price]],
                           columns=ledger.columns)
        ledger = pd.concat([ledger, row])

        # Spending the equivalent amount of cash
        row = pd.DataFrame([["Cash", "Out", "Purchase", current_date, "Open", spot_price * num_shares, None]],
                           columns=ledger.columns)
        ledger = pd.concat([ledger, row])

        ###################################################
        ######### Sell calls against our stocks ###########
        ###################################################
        strike_price = relative_strike_price * spot_price
        sp_minus = strike_price - 10
        sp_max = strike_price + 10
        print(f"strike price : {strike_price}")
        print(f"start date : {current_date}")
        print(f" end date : {calculate_end_date_months(current_date.strftime("%Y-%m-%d"), 1)}")
        gen = Clients[api_key_index].list_options_contracts(underlying_ticker=stock_ticker,
                                                            contract_type="call",
                                                            expiration_date_gte=current_date.strftime("%Y-%m-%d"),
                                                            expiration_date_lte=calculate_end_date_months(
                                                                current_date.strftime("%Y-%m-%d"), 1),
                                                            strike_price_gte=sp_minus,
                                                            strike_price_lte=sp_max,
                                                            expired=True,
                                                            limit=1000)

        api_key_index = (api_key_index + 1) % nb_api_keys

        contractNames = []
        try:
            for c in gen:
                contractNames.append(c)
                # Add a small delay to avoid hitting the rate limit
                time.sleep(0.05)
        except:
            print("Request failed:")

        contract_df = pd.DataFrame(contractNames)
        # We set current_date as the expiration date of the option contract we sold
        exp_date = contract_df["expiration_date"].unique()[expiration_index]
        print(f"exp date = {exp_date}")
        closest_strike_price = min(contract_df.loc[contract_df["expiration_date"] == exp_date]["strike_price"].unique(),
                                   key=lambda x: abs(x - strike_price))
        print(f"Closest strike price = {closest_strike_price}")
        option_ticker = list(contract_df.loc[(contract_df["strike_price"] == closest_strike_price) & (
                    contract_df["expiration_date"] == exp_date)]["ticker"])[0]
        option_price_df = pd.DataFrame(Clients[api_key_index].get_aggs(ticker=option_ticker,
                                                                       multiplier=1,
                                                                       timespan='day',
                                                                       from_=current_date.strftime("%Y-%m-%d"),
                                                                       to=current_date.strftime("%Y-%m-%d")))

        api_key_index = (api_key_index + 1) % nb_api_keys
        #display(option_price_df)
        option_price = option_price_df["vwap"][0]

        num_shares_options = current_stock_position(ledger, stock_ticker) // 100 * 100

        # Selling the options
        row = pd.DataFrame([["Cash", "In", "Call sold", current_date, None, option_price * num_shares_options, None]],
                           columns=ledger.columns)
        ledger = pd.concat([ledger, row])

        ##############################################################
        ####### check ITM or OTM #####################################
        ##############################################################

        current_date = pd.Timestamp(exp_date)
        # On expiration date
        spot_price = list(
            yf.download(stock_ticker, start=current_date, end=next_trading_day(cal, current_date))["Close"][
                stock_ticker])[0]
        print(f"Close price at expiration date : {spot_price}")

        # ITM case
        # If we are ITM, then we have to sell our stocks to the option's buyer, at striker price
        if spot_price > closest_strike_price:
            # We remove the number of shares that we have
            row = pd.DataFrame([[stock_ticker, "Out", "Call exercised", current_date, "Close", num_shares_options,
                                 closest_strike_price]], columns=ledger.columns)
            ledger = pd.concat([ledger, row])

            # We receive cash for the shares we sold
            row = pd.DataFrame(
                [["Cash", "In", "Call exercised", current_date, "Close", closest_strike_price * num_shares_options,
                  None]], columns=ledger.columns)
            ledger = pd.concat([ledger, row])

        # OTM case
        # Nothing happens !! Buyer won't exercise

        current_date = next_trading_day(cal, current_date)

    #######################################################
    ########### Check this logic ##########################
    #######################################################


    # Dates
    ledger["Date"] = pd.to_datetime(ledger["Date"])
    first_dt = ledger["Date"].min().date()
    last_dt = ledger["Date"].max().date()
    days = max((last_dt - first_dt).days, 1)

    # Positions & prices
    shares = current_stock_position(ledger, stock_ticker)
    cash = current_cash_position(ledger)

    # Last close on the last session in your window
    last_close = float(
        yf.download(
            stock_ticker, start=last_dt, end=next_trading_day(cal, pd.Timestamp(last_dt)), progress=False
        )["Close"][stock_ticker].iloc[0]
    )

    # Capital & cash premiums
    initial_capital = float(
        ledger.query("Asset == 'Cash' and In_Out == 'In' and Concept == 'Inflow'")
        ["Amount_Quantity"].sum()
    )
    cash_premiums = float(
        ledger.query("Asset == 'Cash' and In_Out == 'In' and Concept == 'Call sold'")
        ["Amount_Quantity"].sum()
    )

    # Returns
    equity = cash + shares * last_close
    tot_ret = (equity / initial_capital) - 1 if initial_capital > 0 else 0.0
    ann_ret = (1 + tot_ret) ** (365 / days) - 1 if days > 0 else 0.0
    cash_yield = (cash_premiums / initial_capital) if initial_capital > 0 else 0.0
    ann_cash_y = cash_yield * (365 / days) if days > 0 else 0.0  # linear annualization

    # --- replace the placeholder with KPIs + table ---
    placeholder.empty()
    container = placeholder.container()

    k1, k2, k3, k4 = container.columns(4)
    k1.metric("Equity", f"${equity:,.0f}")
    k2.metric("Total Return", f"{tot_ret * 100:,.2f}%")
    k3.metric("Annualized Return", f"{ann_ret * 100:,.2f}%")
    k4.metric("Annualized Cash Yield", f"{ann_cash_y * 100:,.2f}%")

    container.dataframe(ledger, width="stretch", height=520)
    st.session_state["ledger"] = ledger


else:
    # If nothing computed yet, show a hint; otherwise show last result
    if "ledger" in st.session_state:
        placeholder.dataframe(st.session_state["ledger"], use_container_width=True, height=520)
    else:
        placeholder.caption("Set parameters then press **Compute**.")



# Footer note
st.markdown("<br/><span style='opacity:0.7'>Layout-only build. Next step: wire Polygon-based pricing and backtest logic.</span>",
            unsafe_allow_html=True)
