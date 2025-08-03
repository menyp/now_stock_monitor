# ServiceNow (NOW) Stock Employee Trading Window Analysis

This project analyzes historical ServiceNow (NOW) stock prices to help employees decide when to sell during the quarterly trading window.

## How to Use

1. Install dependencies:
pip install -r requirements.txt


2. Run the analysis:
python analyze_windows.py


3. The script will:
   - Download 3 years of daily NOW prices.
   - Analyze price patterns for each employee trading window (Feb, May, Aug, Nov).
   - Output a summary to the console and save it as `window_summary.csv`.
   - Display plots of price movement for each window.

## Requirements

- Python 3.7+
- Internet connection (for downloading stock data)

## Output

- `window_summary.csv`: Table summarizing first, last, highest, and lowest prices for each window.
- Plots: Visualize price movement within each window.

---

If you have any issues or questions, let me know!