import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
from polygon import RESTClient
import datetime as dt
import time
from dateutil.relativedelta import relativedelta

def calculate_end_date_months(start_date_str, offset_months):
    """
    Calculate the end date by adding `offset_months` months to `start_date_str`.
    :param start_date_str: (str) Start date in 'YYYY-MM-DD' format
    :param offset_months: (int) Number of months to add
    :return: (str) End date in 'YYYY-MM-DD' format
    """
    # Parse the start date
    fmt = "%Y-%m-%d"
    start_date = dt.datetime.strptime(start_date_str, fmt)

    # Create a relativedelta for the months
    delta = relativedelta(months=offset_months)

    # Calculate the end date by adding the month offset
    end_date = start_date + delta

    # Return as string in 'YYYY-MM-DD'
    return end_date.strftime(fmt)


def get_previous_trading_day(ticker, date_str):
    """
    Returns the date (as a string in YYYY-MM-DD format) of the last trading day before the given date_str.
    """
    target_date = pd.to_datetime(date_str)
    start_date = target_date - pd.Timedelta(days=6)
    end_date = target_date + pd.Timedelta(days=1)

    df = yf.download(ticker, start=start_date, end=end_date)

    # Filter to keep only the dates strictly before the target_date
    df_before = df[df.index < target_date]

    if df_before.empty:
        return None

    # Return the last trading day date as a string
    last_trading_day = df_before.index[-1].strftime('%Y-%m-%d')
    return last_trading_day

def get_previous_close(ticker, last_trading_day):
    """
    Returns the close price of `ticker` on the last trading day provided by `last_trading_day` (YYYY-MM-DD).
    """
    # Since we already know the exact trading day, we can directly fetch data for that day
    df = yf.download(ticker, start=last_trading_day, end=pd.to_datetime(last_trading_day) + pd.Timedelta(days=1))

    if df.empty:
        return None

    # Return the close price for the last trading day
    prev_close = df['Close'].iloc[-1]
    return prev_close

def get_next_trading_day(ticker, date_str):
    """
    Returns the next trading day (YYYY-MM-DD) strictly AFTER date_str.
    Looks ahead up to ~10 calendar days and picks the first market session.
    """
    target = pd.to_datetime(date_str).normalize()
    start  = target
    end    = target + pd.Timedelta(days=10)

    df = yf.download(ticker, start=start, end=end, progress=False)
    if df.empty:
        # very rare edge case; fall back to +1 day
        return (target + pd.Timedelta(days=1)).strftime('%Y-%m-%d')

    days = df.index.normalize().unique()
    nxt  = days[days > target]
    if len(nxt) == 0:
        return (target + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    return nxt[0].strftime('%Y-%m-%d')


def current_cash_position(Ledger):
    return Ledger.loc[(Ledger["Asset"] == "Cash") & (Ledger["In_Out"] == "In")]["Amount_Quantity"].sum() - Ledger.loc[(Ledger["Asset"] == "Cash") & (Ledger["In_Out"] == "Out")]["Amount_Quantity"].sum()

def current_stock_position(Ledger, Stock_Ticker):
    return Ledger.loc[(Ledger["Asset"] == Stock_Ticker) & (Ledger["In_Out"] == "In")]["Amount_Quantity"].sum() - Ledger.loc[(Ledger["Asset"] == Stock_Ticker) & (Ledger["In_Out"] == "Out")]["Amount_Quantity"].sum()


def next_trading_day(trading_list, day):      
    index = trading_list.index(day)
    index+=1
    return trading_list[index]
