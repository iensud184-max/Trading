import yfinance as yf
import pandas as pd

df = yf.download("^KS11", start="2026-05-01", progress=False)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)
df = df.reset_index()
print("KS11 Columns after flattening:", df.columns)
print("First row of Date:", df.iloc[0]["Date"])
print("First row Date type:", type(df.iloc[0]["Date"]))
print("Formatted Date:", df.iloc[0]["Date"].strftime("%Y-%m-%d %H:%M:%S"))
