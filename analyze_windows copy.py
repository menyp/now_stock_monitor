import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import numpy as np

print("Script started")  # Optional debug print

# --- Configuration ---
TICKER = "NOW"
YEARS = 5  # Analyze last 5 years
WINDOW_MONTHS = [2, 5, 8, 11]  # Feb, May, Aug, Nov (employee trading windows)
WINDOW_LABELS = ["Q1-Feb", "Q2-May", "Q3-Aug", "Q4-Nov"]

# --- Download Data ---
end_date = datetime.today()
start_date = end_date - timedelta(days=YEARS * 365)
df = yf.download(TICKER, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"))
df.reset_index(inplace=True)

# --- Prepare Results ---
results = []

for year in range(end_date.year - YEARS + 1, end_date.year + 1):
    for i, month in enumerate(WINDOW_MONTHS):
        # Get all trading days in this window
        window_mask = (df['Date'] >= pd.Timestamp(year=year, month=month, day=1)) & \
                      (df['Date'] < pd.Timestamp(year=year if month < 12 else year+1, month=month % 12 + 1, day=1))
        window_df = df.loc[window_mask].copy()
        if window_df.empty:
            continue

        # Reset index so idxmax returns position
        window_df = window_df.reset_index(drop=True)
        first_day = window_df.iloc[0]
        last_day = window_df.iloc[-1]
        max_day = window_df.loc[window_df['Close'].idxmax()]
        min_day = window_df.loc[window_df['Close'].idxmin()]

        # Determine when the max occurred
        total_days = len(window_df)
        max_idx = window_df['Close'].idxmax()
        if isinstance(max_idx, (pd.Series, list, tuple, np.ndarray)):
            max_pos = int(max_idx[0])
        else:
            max_pos = int(max_idx)

        if max_pos == 0:
            max_when = "Start"
        elif max_pos == total_days - 1:
            max_when = "End"
        else:
            max_when = "Middle"

        # Robustly extract and format dates
        def get_date(val):
            dt = pd.to_datetime(val)
            if isinstance(dt, pd.Series):
                dt = dt.iloc[0]
            return dt.strftime("%Y-%m-%d")

        # Robustly extract scalar for prices
        def get_scalar(val):
            if isinstance(val, pd.DataFrame):
                return float(val.iloc[0, 0])
            if isinstance(val, pd.Series):
                return float(val.iloc[0])
            return float(val)

        # Save result
        results.append({
            "Window": f"{year}-{WINDOW_LABELS[i]}",
            "First_Date": get_date(first_day['Date']),
            "First_Close": get_scalar(first_day['Close']),
            "Last_Date": get_date(last_day['Date']),
            "Last_Close": get_scalar(last_day['Close']),
            "Max_Date": get_date(max_day['Date']),
            "Max_Close": get_scalar(max_day['Close']),
            "Max_When": max_when,
            "Min_Date": get_date(min_day['Date']),
            "Min_Close": get_scalar(min_day['Close']),
        })

        # Plot window
        plt.figure(figsize=(8, 4))
        plt.plot(window_df['Date'], window_df['Close'], marker='o')
        plt.title(f"{TICKER} {year} {WINDOW_LABELS[i]} Window")
        plt.xlabel("Date")
        plt.ylabel("Close Price ($)")
        plt.scatter([max_day['Date']], [max_day['Close']], color='green', label='Max')
        plt.scatter([min_day['Date']], [min_day['Close']], color='red', label='Min')
        plt.scatter([first_day['Date']], [first_day['Close']], color='blue', label='First')
        plt.scatter([last_day['Date']], [last_day['Close']], color='purple', label='Last')
        plt.legend()
        plt.tight_layout()
        plt.show()

# --- Output Results ---
summary_df = pd.DataFrame(results)
print("\nSummary of Employee Trading Windows (last 5 years):\n")
print(summary_df[["Window", "First_Date", "First_Close", "Last_Date", "Last_Close", "Max_Date", "Max_Close", "Max_When", "Min_Date", "Min_Close"]])

summary_df.to_csv("window_summary.csv", index=False)
print("\nSummary saved to window_summary.csv")

# --- Analyze Trend and Give Recommendation ---
max_when_counts = summary_df['Max_When'].value_counts()
total_windows = max_when_counts.sum()
print("\n--- Analysis of High Price Timing ---")
for period in ["Start", "Middle", "End"]:
    count = max_when_counts.get(period, 0)
    print(f"- {period}: {count} times ({count/total_windows:.0%})")

most_common_period = max_when_counts.idxmax()
if most_common_period == "Start":
    reco = "Based on the last 5 years, the highest price during trading windows most often occurs at the START of the window. Consider selling early in the window."
elif most_common_period == "End":
    reco = "Based on the last 5 years, the highest price during trading windows most often occurs at the END of the window. Consider selling late in the window."
else:
    reco = "Based on the last 5 years, the highest price during trading windows most often occurs in the MIDDLE of the window. Consider monitoring prices throughout the window and selling when a spike occurs."

print("\nRecommendation:")
print(reco)

# --- Graphical Recommendation ---
import matplotlib.patches as mpatches

periods = ["Start", "Middle", "End"]
counts = [max_when_counts.get(period, 0) for period in periods]
colors = ['tab:green' if period == most_common_period else 'tab:gray' for period in periods]

plt.figure(figsize=(7, 4))
bars = plt.bar(periods, counts, color=colors, edgecolor='black')
plt.title("When Does the Highest Price Occur in the Trading Window?")
plt.ylabel("Number of Windows (out of %d)" % total_windows)
plt.xlabel("Period in Trading Window")
for bar, count in zip(bars, counts):
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(), str(count), ha='center', va='bottom', fontsize=12)
highlight_patch = mpatches.Patch(color='tab:green', label='Recommended Period')
plt.legend(handles=[highlight_patch])
plt.tight_layout()
plt.show()