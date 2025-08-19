"""
Render-specific settings and utilities to improve reliability in the Render cloud environment.
Import this file in your main application to apply Render-specific fixes.
"""
import os
import time
import random
import pandas as pd
import requests
from datetime import datetime, timedelta

# Detect if we're running on Render
IS_RENDER = os.environ.get('RENDER') == 'true'

# Define fallback data for when APIs fail on Render
FALLBACK_STOCK_DATA = {
    # Last 30 days of synthetic data (adjust dates as needed)
    # Format: 'YYYY-MM-DD': price
    '2025-07-20': 885.34,
    '2025-07-21': 887.22,
    '2025-07-22': 890.55,
    '2025-07-23': 892.18,
    '2025-07-24': 891.45,
    '2025-07-25': 895.78,
    '2025-07-26': 897.55,
    '2025-07-27': 900.34,
    '2025-07-28': 899.67,
    '2025-07-29': 901.22,
    '2025-07-30': 905.45,
    '2025-07-31': 903.22,
    '2025-08-01': 900.56,
    '2025-08-02': 899.34,
    '2025-08-03': 901.22,
    '2025-08-04': 905.33,
    '2025-08-05': 906.78,
    '2025-08-06': 904.55,
    '2025-08-07': 902.33,
    '2025-08-08': 898.77,
    '2025-08-09': 896.55,
    '2025-08-10': 898.22,
    '2025-08-11': 900.44,
    '2025-08-12': 902.33,
    '2025-08-13': 905.66,
    '2025-08-14': 907.89,
    '2025-08-15': 908.22,
    '2025-08-16': 910.45,
    '2025-08-17': 912.33,
    '2025-08-18': 915.67,
    '2025-08-19': 892.22,  # Today's date - use actual data if available
}

FALLBACK_EXCHANGE_RATES = {
    # Last 30 days of synthetic exchange rate data
    # Format: 'YYYY-MM-DD': rate
    '2025-07-20': 3.38,
    '2025-07-21': 3.39,
    '2025-07-22': 3.41,
    '2025-07-23': 3.42,
    '2025-07-24': 3.40,
    '2025-07-25': 3.39,
    '2025-07-26': 3.38,
    '2025-07-27': 3.37,
    '2025-07-28': 3.38,
    '2025-07-29': 3.39,
    '2025-07-30': 3.42,
    '2025-07-31': 3.44,
    '2025-08-01': 3.45,
    '2025-08-02': 3.44,
    '2025-08-03': 3.43,
    '2025-08-04': 3.42,
    '2025-08-05': 3.41,
    '2025-08-06': 3.40,
    '2025-08-07': 3.39,
    '2025-08-08': 3.38,
    '2025-08-09': 3.37,
    '2025-08-10': 3.38,
    '2025-08-11': 3.39,
    '2025-08-12': 3.40,
    '2025-08-13': 3.41,
    '2025-08-14': 3.42,
    '2025-08-15': 3.43,
    '2025-08-16': 3.42,
    '2025-08-17': 3.41,
    '2025-08-18': 3.42,
    '2025-08-19': 3.42,  # Today's date - use actual data if available
}

def render_safe_request(url, timeout=20, max_retries=3):
    """
    Make HTTP requests more reliable on Render by adding retries and increased timeout.
    """
    if not IS_RENDER:
        # If not on Render, just do a regular request
        return requests.get(url, timeout=10)
    
    for attempt in range(max_retries):
        try:
            # Add a small random delay between retries to avoid rate limits
            if attempt > 0:
                time.sleep(1 + random.random())
                
            response = requests.get(url, timeout=timeout)
            return response
        except Exception as e:
            print(f"Attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt == max_retries - 1:
                # Re-raise on the last attempt
                raise
    
    # Should never reach here, but just in case
    raise Exception("All request attempts failed")

def get_fallback_stock_data(days=30):
    """
    Returns fallback stock price data for when API calls fail on Render.
    """
    # Filter to only include the requested number of days
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Sort keys by date and get the latest ones up to the requested days
    sorted_dates = sorted(FALLBACK_STOCK_DATA.keys())
    recent_dates = sorted_dates[-days:]
    
    # Create a filtered dictionary
    filtered_data = {date: FALLBACK_STOCK_DATA[date] for date in recent_dates}
    return filtered_data

def get_fallback_exchange_rates(days=30):
    """
    Returns fallback exchange rate data for when API calls fail on Render.
    """
    # Filter to only include the requested number of days
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Sort keys by date and get the latest ones up to the requested days
    sorted_dates = sorted(FALLBACK_EXCHANGE_RATES.keys())
    recent_dates = sorted_dates[-days:]
    
    # Create a filtered dictionary
    filtered_data = {date: FALLBACK_EXCHANGE_RATES[date] for date in recent_dates}
    return filtered_data
