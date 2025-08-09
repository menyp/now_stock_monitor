import yfinance as yf
import schedule
import time
import json
import os
from datetime import datetime, timedelta
import subprocess
import sys
import threading
from flask import Flask, request, jsonify, Response, render_template, render_template_string
import firebase_admin
from firebase_admin import credentials, db
import tempfile
import pandas as pd
import numpy as np
import logging

# Custom JSON encoder for pandas Series and other non-serializable objects
class SafeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'item'):
            try:
                return obj.item()  # Extract scalar from pandas Series
            except:
                return str(obj)
        elif pd.isna(obj) or obj is pd.NaT:
            return None
        elif hasattr(obj, 'isoformat'):  # Handle datetime objects
            return obj.isoformat()
        elif isinstance(obj, (pd.Series, pd.DataFrame)):
            return obj.to_dict()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

# Helper function for safe JSON serialization
def safe_json_dumps(obj):
    return json.dumps(obj, cls=SafeJSONEncoder)

# Helper functions for tooltips and explanations
def get_sell_score_explanation():
    """Return explanation of how the sell profitability score is calculated"""
    return {
        'calculation': 'Profitability Score = (70% × Stock Price Impact) + (30% × Exchange Rate Impact)',
        'factors': [
            'Higher ServiceNow stock price increases score (70% weight)',
            'Higher USD/ILS exchange rate increases score (30% weight)',
            'Score ranges from 0-100, with 50 as the baseline (neutral point)',
            'Both factors need to align for optimal selling conditions'
        ],
        'waiting_for': [
            'Stock price increases (watch the BLUE line in the graph)',
            'USD strengthening against ILS (watch the RED line increasing)',
            'For best results: Look for NOW stock price rising while USD/ILS exchange rate is increasing'
        ]
    }

def get_buy_score_explanation():
    """Return explanation of how the buy profitability score is calculated"""
    return {
        'calculation': 'Profitability Score = (70% × S&P Price Impact) + (30% × Exchange Rate Impact)',
        'factors': [
            'Lower S&P 500 price increases score (70% weight)',
            'Lower USD/ILS exchange rate increases score (30% weight)',
            'Score ranges from 0-100, with higher values indicating better buying opportunities',
            'Both factors need to align for optimal buying conditions'
        ],
        'waiting_for': [
            'S&P 500 price dips (watch the BLUE line in the graph)',
            'ILS strengthening against USD (watch the RED line decreasing)',
            'For best results: Look for S&P price falling while USD/ILS exchange rate is decreasing'
        ]
    }

# Function to prepare template data with safe serialization
def prepare_template_data(common_dates, profitability, prices, rates, current_profit=None, 
                          best_profit=None, best_date=None, current_price=None, current_rate=None):
    """Safely prepare all data for template rendering, handling pandas Series objects properly"""
    # Create safe versions of all data
    if not common_dates:
        return {
            'common_dates': [],
            'dates_json': '[]',
            'profitability_json': '[]',
            'stock_prices_json': '[]',
            'exchange_rates_json': '[]',
            'formatted_current_profit': 'N/A',
            'formatted_best_profit': 'N/A',
            'formatted_best_date': 'N/A',
            'formatted_current_stock': 'N/A',
            'formatted_current_rate': 'N/A',
            'recommendation_text': 'Insufficient data to make a recommendation.'
        }
    
    # Convert all data to safe, serializable formats
    safe_dates = []
    safe_profits = []
    safe_prices = []
    safe_rates = []
    
    for date in common_dates:
        # Add safe date
        safe_dates.append(str(date))
        
        # Add safe profit value
        try:
            value = profitability[date]
            if hasattr(value, 'item'):
                safe_profits.append(round(float(value.item()), 2))
            else:
                safe_profits.append(round(float(value), 2))
        except (ValueError, TypeError):
            safe_profits.append(None)
        
        # Add safe price value
        try:
            value = prices[date]
            if hasattr(value, 'item'):
                safe_prices.append(round(float(value.item()), 2))
            else:
                safe_prices.append(round(float(value), 2))
        except (ValueError, TypeError):
            safe_prices.append(None)
        
        # Add safe exchange rate
        try:
            value = rates[date]
            if hasattr(value, 'item'):
                safe_rates.append(round(float(value.item()), 4))
            else:
                safe_rates.append(round(float(value), 4))
        except (ValueError, TypeError):
            safe_rates.append(None)
    
    # Format scalar values
    try:
        current_profit_scalar = float(current_profit.item()) if hasattr(current_profit, 'item') else float(current_profit) if current_profit is not None else None
    except (TypeError, ValueError):
        current_profit_scalar = None
        
    try:
        best_profit_scalar = float(best_profit.item()) if hasattr(best_profit, 'item') else float(best_profit) if best_profit is not None else None
    except (TypeError, ValueError):
        best_profit_scalar = None
        
    try:
        current_price_scalar = float(current_price.item()) if hasattr(current_price, 'item') else float(current_price) if current_price is not None else None
    except (TypeError, ValueError):
        current_price_scalar = None
        
    try:
        current_rate_scalar = float(current_rate.item()) if hasattr(current_rate, 'item') else float(current_rate) if current_rate is not None else None
    except (TypeError, ValueError):
        current_rate_scalar = None
    
    # Format for display
    formatted_current_profit = f"{current_profit_scalar:.1f}" if current_profit_scalar is not None else "N/A"
    formatted_best_profit = f"{best_profit_scalar:.1f}" if best_profit_scalar is not None else "N/A"
    
    if best_date is not None:
        if hasattr(best_date, 'item'):
            try:
                formatted_best_date = str(best_date.item())
            except:
                formatted_best_date = str(best_date)
        else:
            formatted_best_date = str(best_date)
    else:
        formatted_best_date = "N/A"
        
    formatted_current_stock = f"{current_price_scalar:.2f}" if current_price_scalar is not None else "N/A"
    formatted_current_rate = f"{current_rate_scalar:.2f}" if current_rate_scalar is not None else "N/A"
    
    # JSON serialize data using our safe encoder
    dates_json = safe_json_dumps(safe_dates)
    profitability_json = safe_json_dumps(safe_profits)
    stock_prices_json = safe_json_dumps(safe_prices)
    exchange_rates_json = safe_json_dumps(safe_rates)
    
    return {
        'common_dates': safe_dates,
        'dates_json': dates_json,
        'profitability_json': profitability_json,
        'stock_prices_json': stock_prices_json,
        'exchange_rates_json': exchange_rates_json,
        'formatted_current_profit': formatted_current_profit,
        'formatted_best_profit': formatted_best_profit,
        'formatted_best_date': formatted_best_date,
        'formatted_current_stock': formatted_current_stock,
        'formatted_current_rate': formatted_current_rate
    }

DATA_FILE = 'sn_monthly_data.json'  # Kept for backwards compatibility
TICKER = 'NOW'

# External API keys and constants
# Primary and fallback exchange rate API URLs - using more reliable sources
EXCHANGE_APIS = [
    # Best reliability API from frankfurter.app
    {
        'url': 'https://api.frankfurter.app/latest?from=USD&to=ILS',
        'rate_path': ['rates', 'ILS']
    },
    # European Central Bank-backed free API
    {
        'url': 'https://api.exchangeratesapi.io/latest?base=USD&symbols=ILS',
        'rate_path': ['rates', 'ILS']
    },
    # Currency Freaks API - good alternative
    {
        'url': 'https://api.currencyfreaks.com/v2.0/rates/latest?apikey=7b78f8d2222e46b5a50c87c321ea8685',
        'rate_path': ['rates', 'ILS']
    },
    # GitHub CDN-hosted API as final fallback
    {
        'url': 'https://cdn.jsdelivr.net/gh/fawazahmed0/currency-api@1/latest/currencies/usd/ils.json',
        'rate_path': ['ils']
    }
]

# Default fallback rate (updated to August 2025 estimate)
DEFAULT_ILS_USD_RATE = 3.42

# Initialize Firebase (only if not already initialized)
if not firebase_admin._apps:
    # Check if we're running on Render (production)
    if os.environ.get('ENVIRONMENT') == 'production' or os.environ.get('RENDER') == 'true':
        # In production, use environment variables
        # You'll need to set these in your Render dashboard
        try:
            # Get the service account JSON from environment variable and save to temp file
            if 'FIREBASE_SERVICE_ACCOUNT_JSON' in os.environ:
                print("INFO: Found Firebase service account JSON in environment variables")
                service_account_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
                # Create a temporary file to store the service account JSON
                fd, path = tempfile.mkstemp()
                try:
                    with os.fdopen(fd, 'w') as tmp:
                        tmp.write(service_account_json)
                    print(f"INFO: Temporary service account file created: {path}")
                    # Initialize Firebase with the temporary file
                    cred = credentials.Certificate(path)
                    firebase_admin.initialize_app(cred, {
                        'databaseURL': os.environ.get('FIREBASE_DATABASE_URL')
                    })
                    print(f"INFO: Firebase initialized in production with database URL: {os.environ.get('FIREBASE_DATABASE_URL')}")
                finally:
                    # Clean up the temporary file
                    os.remove(path)
            else:
                print("CRITICAL: Firebase service account JSON not found in environment variables")
        except Exception as e:
            print(f"CRITICAL: Error initializing Firebase in production: {e}")
            import traceback
            print(traceback.format_exc())
    else:
        # In development, use a local service account file if it exists
        try:
            service_account_path = 'sn-stock-monitor-firebase-adminsdk-fbsvc-5f171ce112.json'
            if os.path.exists(service_account_path):
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': 'https://sn-stock-monitor-default-rtdb.europe-west1.firebasedatabase.app/'
                })
            else:
                print(f"WARNING: Firebase service account file not found at {service_account_path}")
        except Exception as e:
            print(f"Error initializing Firebase in development: {e}")


def get_current_month():
    now = datetime.now()
    return now.strftime('%Y-%m')

def get_today():
    return datetime.now().strftime('%Y-%m-%d')

def fetch_sn_price():
    try:
        ticker = yf.Ticker(TICKER)
        # Try to get recent data
        data = ticker.history(period='1d', interval='1m')
        
        # If no data in 1m interval, try 1d interval
        if data.empty:
            print("No minute data available, trying daily data...")
            data = ticker.history(period='1d')
            
        if data.empty:
            print("WARNING: Could not fetch stock data")
            return None
            
        # Get the latest available close price and round to 2 decimal places
        return round(float(data['Close'][-1]), 2)
    except Exception as e:
        print(f"ERROR in fetch_sn_price: {e}")
        import traceback
        print(traceback.format_exc())
        return None
        
def fetch_historical_sn_prices(days=30):
    """Fetch historical ServiceNow stock prices for the given number of days"""
    try:
        ticker = yf.Ticker(TICKER)
        # Get daily data for the specified period
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        data = ticker.history(start=start_date, end=end_date)
        
        if data.empty:
            print(f"WARNING: Could not fetch historical stock data for {TICKER}")
            return None
        
        # Convert to dictionary with date strings as keys and close prices as values
        result = {}
        for date, row in data.iterrows():
            date_str = date.strftime('%Y-%m-%d')
            result[date_str] = round(float(row['Close']), 2)
            
        return result
    except Exception as e:
        print(f"ERROR in fetch_historical_sn_prices: {e}")
        import traceback
        print(traceback.format_exc())
        return None

# Cache for exchange rate to ensure consistency between page refreshes
_exchange_rate_cache = {'rate': 3.42, 'timestamp': None}

def fetch_ils_usd_rate():
    """Fetch current ILS to USD exchange rate with caching for consistency and multiple API fallbacks"""
    global _exchange_rate_cache
    
    # If we have a cached rate from today, return it
    current_date = datetime.now().strftime('%Y-%m-%d')
    if _exchange_rate_cache['timestamp'] == current_date:
        print(f"Using cached exchange rate: {_exchange_rate_cache['rate']} from {current_date}")
        return _exchange_rate_cache['rate']
    
    print("No valid cache found. Fetching fresh exchange rate...")
    import requests
    import time
    
    # Define API-specific handlers to extract the exchange rate
    # Try each API in order until we get a successful response
    for api_config in EXCHANGE_APIS:
        try:
            print(f"Attempting to fetch exchange rate from {api_config['url']}")
            
            # Add User-Agent header to avoid being blocked by some APIs
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(api_config['url'], headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Navigate to the exchange rate value using the provided path
                rate_value = data
                path_found = True
                for key in api_config['rate_path']:
                    if rate_value is not None and isinstance(rate_value, dict) and key in rate_value:
                        rate_value = rate_value.get(key)
                    else:
                        print(f"Key '{key}' not found in response data")
                        path_found = False
                        break
                
                if path_found and rate_value is not None:
                    # Convert to float if it's a string
                    if isinstance(rate_value, str):
                        rate_value = float(rate_value)
                    
                    # Special handling for APIs that might return USD/ILS instead of ILS/USD
                    # If rate is very small (e.g., 0.29 instead of 3.4), it's likely USD/ILS
                    if rate_value < 1.0:
                        rate = round(1 / rate_value, 4)
                        print(f"Converted USD/ILS to ILS/USD: {rate}")
                    else:
                        rate = round(rate_value, 4)
                    
                    print(f"Successfully fetched ILS/USD rate: {rate}")
                    
                    # Verify the rate is reasonable (between 3.0 and 4.0 for USD/ILS in 2025)
                    if 3.0 <= rate <= 4.0:
                        # Update the cache
                        _exchange_rate_cache = {'rate': rate, 'timestamp': current_date}
                        return rate
                    else:
                        print(f"Rate {rate} outside of expected range (3.0-4.0), trying next API")
                else:
                    print("Failed to extract rate value from response")
            else:
                print(f"API returned non-200 status code: {response.status_code}")
        except Exception as e:
            print(f"Error with API {api_config['url']}: {str(e)}")
            # Continue to the next API on failure
            time.sleep(0.5)  # Brief pause before trying next API
    
    # If all APIs failed, use the most recent known good rate (August 2025)
    print("WARNING: All exchange rate APIs failed, using default rate")
    _exchange_rate_cache = {'rate': DEFAULT_ILS_USD_RATE, 'timestamp': current_date}
    return _exchange_rate_cache['rate']

def fetch_historical_ils_usd_rates(days=30):
    """Fetch historical ILS to USD exchange rates for the given number of days"""
    try:
        import requests
        
        # Unfortunately, the free tier of most exchange rate APIs doesn't provide historical data
        # For a production app, you would use a paid API service like Alpha Vantage or similar
        # For this demo, we'll simulate historical data with slight variations from the current rate
        
        # Get current rate as baseline
        current_rate = fetch_ils_usd_rate()
        if not current_rate:
            return None
            
        # Generate simulated historical data
        result = {}
        for i in range(days, -1, -1):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            
            # Add a random variation of up to ±3% from current rate
            import random
            # Use a fixed seed based on the date to ensure consistent values between refreshes
            random.seed(hash(date_str))
            variation = random.uniform(-0.03, 0.03)
            rate = current_rate * (1 + variation)
            
            result[date_str] = round(rate, 4)
            
        return result
    except Exception as e:
        print(f"ERROR in fetch_historical_ils_usd_rates: {e}")
        import traceback
        print(traceback.format_exc())
        return None
        
def calculate_sell_profitability(stock_prices, exchange_rates):
    """Calculate profitability for selling based on stock price and exchange rate using min/max normalization"""
    try:
        # Extract scalar values to avoid Series truth value ambiguity
        scalar_stock_values = {}
        scalar_exchange_rates = {}
        
        # Find common dates between stock prices and exchange rates
        common_dates = sorted(set(stock_prices.keys()) & set(exchange_rates.keys()))
        
        # Check if we have valid data
        if not common_dates:
            return {}
        
        # Convert to scalar values
        for date in common_dates:
            try:
                # Convert to float to ensure we have scalar values
                scalar_stock_values[date] = float(stock_prices[date])
                scalar_exchange_rates[date] = float(exchange_rates[date])
            except (ValueError, TypeError):
                # Skip dates with invalid values
                continue
        
        # Get valid dates after filtering
        valid_dates = sorted(set(scalar_stock_values.keys()) & set(scalar_exchange_rates.keys()))
        if not valid_dates:
            return {}
        
        # Calculate min and max values
        stock_value_list = list(scalar_stock_values.values())
        rate_value_list = list(scalar_exchange_rates.values())
        
        min_stock = min(stock_value_list)
        max_stock = max(stock_value_list)
        stock_range = max_stock - min_stock
        
        min_rate = min(rate_value_list)
        max_rate = max(rate_value_list)
        rate_range = max_rate - min_rate
        
        # Normalize and calculate profitability
        # For stock: higher price = higher score (direct relationship)
        # For exchange rate: higher rate = higher score (direct relationship)
        profitability = {}
        
        for date in valid_dates:
            # Normalize stock price (higher = better)
            if stock_range > 0:
                normalized_stock = (scalar_stock_values[date] - min_stock) / stock_range
            else:
                normalized_stock = 0.5  # Default if no range
            
            # Normalize exchange rate (higher = better)
            if rate_range > 0:
                normalized_rate = (scalar_exchange_rates[date] - min_rate) / rate_range
            else:
                normalized_rate = 0.5  # Default if no range
            
            # Calculate final score (70% price, 30% exchange rate)
            profitability[date] = (normalized_stock * 0.7 + normalized_rate * 0.3) * 100
        
        return profitability
    except Exception as e:
        print(f"ERROR in calculate_sell_profitability: {e}")
        import traceback
        traceback.print_exc()
        return {}

def load_data():
    print(f"INFO: Loading data, Firebase initialized: {bool(firebase_admin._apps)}")
    try:
        # First try to get data from Firebase
        if firebase_admin._apps:
            print("INFO: Attempting to load data from Firebase")
            # Get a reference to the root of the database
            ref = db.reference('/')
            data = ref.get()
            print(f"INFO: Firebase data loaded: {data is not None}")
            if data is not None:
                # Initialize email_recipients if not present
                if 'email_recipients' not in data:
                    data['email_recipients'] = ["menypeled@gmail.com"]  # Default recipient
                print(f"INFO: Returning Firebase data with keys: {', '.join(data.keys() if data else [])}")
                return data
            
    except Exception as e:
        print(f"Error loading data from Firebase: {e}")
    
    # Fall back to local file if Firebase fails or is not initialized
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                # Initialize email_recipients if not present
                if 'email_recipients' not in data:
                    data['email_recipients'] = ["menypeled@gmail.com"]  # Default recipient
                return data
    except Exception as e:
        print(f"Error loading data from local file: {e}")
        
    # Return default empty data structure with email_recipients
    return {'email_recipients': ["menypeled@gmail.com"]}

def format_window_key(start_date, end_date):
    """Create a unique key for a trading window"""
    return f"{start_date}_to_{end_date}"

def save_data(data):
    print(f"INFO: Saving data, Firebase initialized: {bool(firebase_admin._apps)}")
    try:
        # First try to save to Firebase
        if firebase_admin._apps:
            print("INFO: Attempting to save data to Firebase")
            # Get a reference to the root of the database
            ref = db.reference('/')
            ref.set(data)
            print(f"INFO: Data saved to Firebase with keys: {', '.join(data.keys() if data else [])}")
        else:
            print("WARNING: Firebase not initialized, skipping Firebase save")
    except Exception as e:
        print(f"ERROR: Failed saving data to Firebase: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Also save to local file as backup or if Firebase fails
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving data to local file: {e}")

import logging
logging.basicConfig(filename='sn_alerts.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def send_email_alert(subject, body, to_email):
    import smtplib
    from email.mime.text import MIMEText

    # ---- CONFIGURE THESE ----
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = "menypeled@gmail.com"         # <-- Replace with your Gmail address
    sender_password = "upmjrmpzuthbbfpd"         # <-- Replace with your Gmail App Password
    # -------------------------

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [to_email], msg.as_string())
        print("[ALERT] Email sent!")
        logging.info("[ALERT] Email sent!")
    except Exception as e:
        print(f"[ALERT] Email failed: {e}")
        logging.error(f"[ALERT] Email failed: {e}")

def get_simulation_note():
    return "\n\nNote: This is a simulation, not a real alert."

def notify_peak(price, is_simulation=False):
    message = f"SN stock hit a new monthly peak: ${price:.2f}\n\nFor more info visit the SN stock monitor: https://now-stock-monitor.onrender.com/"
    title = "ServiceNow Stock Alert"
    if is_simulation:
        message += get_simulation_note()
    print(f"[ALERT] Triggering alert: {message}")
    logging.info(f"[ALERT] Triggering alert: {message}")
    
    # Only run local notifications if not in cloud environment
    if os.environ.get('ENVIRONMENT') != 'production':
        # Try to play sound on macOS
        try:
            subprocess.Popen(['afplay', '/System/Library/Sounds/Glass.aiff'])
        except Exception:
            pass
            
        # Try to show Mac notification
        try:
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(['osascript', '-e', script], capture_output=True)
        except Exception as e:
            print(f"[ALERT] Local notification failed: {e}")
            logging.error(f"[ALERT] Local notification failed: {e}")
    
    # ---- SEND EMAIL ALERTS TO ALL RECIPIENTS ----
    try:
        # Get all email recipients from the data
        data = load_data()
        recipients = data.get('email_recipients', [])
        
        if recipients:
            for email in recipients:
                try:
                    send_email_alert(title, message, email)
                    print(f"[ALERT] Email sent to {email}")
                except Exception as e:
                    print(f"[ALERT] Email notification to {email} failed: {e}")
                    logging.error(f"[ALERT] Email notification to {email} failed: {e}")
        else:
            print("[ALERT] No email recipients configured")
    except Exception as e:
        print(f"[ALERT] Email notification process failed: {e}")
        logging.error(f"[ALERT] Email notification process failed: {e}")

def monitor_stock(window_start=None, window_end=None, manual_refresh=False):
    try:
        data = load_data()
        today = get_today()
        current_price = fetch_sn_price()
        
        if current_price is None:
            print("Could not fetch SN price.")
            return
    except Exception as e:
        print(f"Error initializing monitor_stock: {e}")
        import traceback
        print(traceback.format_exc())
        return
        
    # Determine which trading window we're using
    if 'active_window' in data and not (window_start and window_end):
        window_key = data['active_window']
        window_start, window_end = window_key.split('_to_')
    elif window_start and window_end:
        window_key = format_window_key(window_start, window_end)
    else:
        # Default to current month if no window is specified
        month = get_current_month()
        window_key = month

    # Calculate baseline based on window start date or default to first day of current month
    ticker = yf.Ticker(TICKER)
    
    # Convert window_start to datetime if it exists, otherwise use first day of current month
    if window_start:
        try:
            start_date = datetime.strptime(window_start, '%Y-%m-%d')
        except ValueError:
            print(f"Invalid start date format: {window_start}")
            start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Convert window_end to datetime if it exists, otherwise use first day of next month
    if window_end:
        try:
            end_date = datetime.strptime(window_end, '%Y-%m-%d')
            # Add one day to include the end date in the data
            end_date = end_date + timedelta(days=1)
        except ValueError:
            print(f"Invalid end date format: {window_end}")
            end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    
    # Get historical data for the window
    hist = ticker.history(start=start_date, end=end_date, interval='1d')
    if not hist.empty:
        first_market_day = hist.index[0]
        minute_hist = ticker.history(start=first_market_day, end=first_market_day + timedelta(days=1), interval='1m')
        if not minute_hist.empty:
            first_minute_row = minute_hist.iloc[0]
            baseline_price = round(float(first_minute_row['Open']), 2)
            baseline_date = first_minute_row.name.strftime('%Y-%m-%d %H:%M')
        else:
            first_open_row = hist.iloc[0]
            baseline_price = round(float(first_open_row['Open']), 2)
            baseline_date = first_open_row.name.strftime('%Y-%m-%d')
    else:
        baseline_price = round(current_price, 2)
        baseline_date = today

    if window_key not in data:
        # First run for this window: set only baseline and current price; leave peak unset
        data[window_key] = {
            'baseline_date': baseline_date,
            'baseline_price': round(baseline_price, 2),
            'peak_price': None,
            'peak_date': None,
            'current_price': round(current_price, 2),
            'peak_simulated': False,
            'last_real_peak_price': None,
            'last_real_peak_date': None,
        }
        save_data(data)
        print(f"Initialized baseline for window {window_key}: ${baseline_price:.2f} on {baseline_date}")
        return
    else:
        # Always update baseline to the correct value
        data[window_key]['baseline_date'] = baseline_date
        data[window_key]['baseline_price'] = round(baseline_price, 2)

    # Always update current price
    data[window_key]['current_price'] = round(current_price, 2)

    # When refreshing manually, always clear any simulated peak
    if manual_refresh:
        # Check if there was a simulated peak
        if data[window_key].get('peak_simulated', False):
            print(f"Detected simulated peak in window {window_key}. Restoring real data...")
            
            # Restore from last real peak, or use baseline if no real peak exists
            last_real_price = data[window_key].get('last_real_peak_price')
            last_real_date = data[window_key].get('last_real_peak_date')
            
            if last_real_price is not None and last_real_date is not None:
                # If there was a real peak before simulation, restore it
                data[window_key]['peak_price'] = last_real_price
                data[window_key]['peak_date'] = last_real_date
                print(f"Restored last real peak: ${last_real_price} on {last_real_date}")
            else:
                # If there was no real peak before, remove peak information completely
                data[window_key]['peak_price'] = None
                data[window_key]['peak_date'] = None
                print(f"No previous real peak found. Peak info cleared.")
            
            # Mark as not simulated and save changes
            data[window_key]['peak_simulated'] = False
            save_data(data)
            print(f"Simulated peak cleared for window {window_key}")
    # If not manual refresh and peak was simulated, keep it as is

    # Check for new real peak (must be above both previous peak and baseline)
    # Use get() with fallback to safely access last_real_peak_price
    last_real = data[window_key].get('last_real_peak_price')
    if last_real is None:
        last_real = data[window_key]['baseline_price']
    if current_price > max(last_real, data[window_key]['baseline_price']):
        data[window_key]['peak_price'] = round(current_price, 2)
        data[window_key]['peak_date'] = today
        data[window_key]['last_real_peak_price'] = round(current_price, 2)
        data[window_key]['last_real_peak_date'] = today
        save_data(data)
        notify_peak(current_price)
        print(f"New peak for window {window_key}: ${current_price:.2f}")
    else:
        save_data(data)
        # Safely access peak_price with fallback to avoid KeyError
        peak_price = data[window_key].get('peak_price', current_price)
        print(f"Checked: ${current_price:.2f} (Current peak: ${peak_price:.2f})")

def start_scheduler():
    print("Starting SN stock monitor...")
    monitor_stock()  # Run once at start
    schedule.every(10).minutes.do(monitor_stock)
    while True:
        schedule.run_pending()
        time.sleep(10)

# --- Flask Web Interface ---
app = Flask(__name__, template_folder='templates')

@app.route('/')
def dashboard():
    html = '''
    <style>
    body { background: #f6f8fa; font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; }
    .container { max-width: 520px; margin: 40px auto; background: #fff; border-radius: 16px; box-shadow: 0 2px 16px #0002; padding: 32px 24px; text-align: center; }
    /* Tab navigation */
    .tabs { display: flex; justify-content: space-between; margin-bottom: 20px; border-bottom: 1px solid #ddd; }
    .tab { flex: 1; padding: 10px 5px; text-align: center; cursor: pointer; color: #555; font-weight: 500; transition: all 0.3s ease; border-bottom: 3px solid transparent; }
    .tab.active { color: #1976d2; border-bottom: 3px solid #1976d2; }
    .tab:hover:not(.active) { color: #333; background-color: #f1f1f1; }
    h2 { margin-top: 0; color: #2c3e50; font-size: 1.7em; letter-spacing: 0.5px; }
    h4 { margin: 12px 0 20px 0; font-weight: 400; color: #3b4b5a; }
    .fields-panel { display: flex; flex-direction: column; gap: 16px; margin: 18px 0 8px 0; }
    .field-card { display: flex; justify-content: space-between; align-items: center; background: #f9fbfc; border-radius: 8px; box-shadow: 0 1px 4px #0001; padding: 14px 18px; font-size: 1.13em; border: 1px solid #e3e7eb; }
    .field-label { color: #34495e; font-weight: 500; letter-spacing: 0.1px; }
    .field-value { color: #1976d2; font-weight: 600; font-size: 1.13em; letter-spacing: 0.1px; }
    .field-card.highlight { background: #e3fbe7; border: 1.5px solid #388e3c; }
    .field-card.highlight .field-value { color: #388e3c; font-weight: 700; font-size: 1.22em; }
    .field-card.big { font-size: 1.24em; padding: 20px 18px; }
    .field-card.two-cols .field-label { min-width: 55px; }
    .btn-group { display: flex; gap: 14px; justify-content: center; margin: 22px 0 14px 0; flex-wrap: wrap; }
    button { background: #1976d2; color: #fff; border: none; border-radius: 8px; padding: 12px 24px; font-size: 1.08em; font-weight: 500; cursor: pointer; transition: background 0.18s, box-shadow 0.18s; box-shadow: 0 1px 4px #1976d220; }
    button:hover, button:focus { background: #1565c0; outline: none; box-shadow: 0 2px 8px #1976d230; }
    #msg { text-align: center; margin-top: 12px; min-height: 28px; font-weight: 500; font-size: 1.08em; letter-spacing: 0.1px; }
    .spinner { display: inline-block; width: 22px; height: 22px; border: 3px solid #1976d2; border-radius: 50%; border-top: 3px solid #fff; animation: spin 1s linear infinite; margin-right: 8px; vertical-align: middle; }
    
    /* Trading window styles */
    .trading-window-inputs { display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 10px; border: 1px dashed #ccc; }
    .date-input-group { display: flex; align-items: center; justify-content: space-between; }
    .date-input-group label { font-weight: 500; color: #555; flex: 1; text-align: left; }
    .date-input-group input[type="date"] { flex: 2; padding: 8px; border: 1px solid #ddd; border-radius: 5px; font-family: inherit; }
    .window-btn { background: #4caf50; margin-top: 8px; }
    .window-btn:hover, .window-btn:focus { background: #388e3c; }
    
    /* Email management styles */
    .email-management { margin: 15px 0 25px; padding: 15px; background: #f0f8ff; border-radius: 10px; border: 1px dashed #1976d2; }
    .email-management h4 { margin: 0 0 15px; color: #1976d2; font-weight: 500; }
    .email-input-group { display: flex; gap: 10px; margin-bottom: 15px; }
    .email-input-group input { flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 5px; font-family: inherit; }
    .email-btn { background: #1976d2; padding: 8px 15px; margin: 0; }
    .email-list { max-height: 150px; overflow-y: auto; border-top: 1px solid #ddd; padding-top: 10px; }
    .email-item { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; }
    .email-address { font-size: 0.95em; color: #444; }
    .delete-email { background: #f44336; color: white; border: none; border-radius: 4px; padding: 3px 8px; cursor: pointer; font-size: 0.8em; }
    .delete-email:hover { background: #d32f2f; }
    .loading-placeholder { color: #888; font-style: italic; text-align: center; padding: 10px 0; }
    
    @keyframes spin { 100% { transform: rotate(360deg); } }
    @media (max-width: 600px) {
      .container { max-width: 99vw; padding: 10px 2px; }
      h2 { font-size: 1.1em; }
      h4 { font-size: 1em; }
      .fields-panel { gap: 9px; }
      .field-card { padding: 8px 8px; font-size: 0.98em; }
      .field-label, .field-value { font-size: 0.98em; }
      button { padding: 8px 10px; font-size: 0.98em; }
    }
    </style>
    <div class="container">
      <div class="tabs">
        <a href="/" class="tab active">SN Monitor</a>
        <a href="/best-to-sell" class="tab">Best to Sell</a>
        <a href="/best-to-buy-sp" class="tab">Buy S&P</a>
        <a href="/best-to-shift" class="tab">Shift to S&P</a>
      </div>
      <h2>ServiceNow (NOW) Stock Monitor</h2>
      <h4>Trading Window: <span id="month"></span></h4>
      <div class="trading-window-inputs">
        <div class="date-input-group">
          <label for="window-start">Window Start Date:</label>
          <input type="date" id="window-start" name="window-start">
        </div>
        <div class="date-input-group">
          <label for="window-end">Window End Date:</label>
          <input type="date" id="window-end" name="window-end">
        </div>
        <button onclick="setTradingWindow()" class="window-btn">Set Trading Window</button>
      </div>
      
      <div class="email-management">
        <h4>Email Notifications</h4>
        <div class="email-input-group">
          <input type="email" id="new-email" placeholder="Enter email address...">
          <button onclick="addEmailRecipient()" class="email-btn">Add</button>
        </div>
        <div id="email-list" class="email-list">
          <!-- Email recipients will be listed here -->
          <div class="loading-placeholder">Loading recipients...</div>
        </div>
      </div>
      <div class="fields-panel">
        <div class="field-card highlight big">
          <div class="field-label">Current Price</div>
          <div class="field-value" id="current_price">-</div>
        </div>
        <div class="field-card two-cols">
          <div class="field-label">Baseline</div>
          <div class="field-value" style="display:flex;gap:16px;justify-content:flex-end;width:100%;">
            <span id="baseline_price">-</span>
            <span style="color:#888;font-size:0.97em;">(<span id="baseline_date">-</span>)</span>
          </div>
        </div>
        <div class="field-card two-cols">
          <div class="field-label">Peak</div>
          <div class="field-value" style="display:flex;gap:16px;justify-content:flex-end;width:100%;">
            <span id="peak_price">-</span>
            <span style="color:#888;font-size:0.97em;">(<span id="peak_date">-</span>)</span>
          </div>
        </div>
      </div>
      <div class="btn-group">
        <button onclick="refreshStatus()">Refresh</button>
        <button onclick="simulatePeak()">Simulate Peak</button>
        <button onclick="clearAll()" style="background:#b71c1c;">Clear</button>
      </div>
      <div id="msg"></div>
    </div>
    <script>
    // Function to play notification sound in the browser
    function playNotificationSound() {
        // Create audio element with a simple beep sound (data URL for a short beep)
        const audio = new Audio("data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBwQxEEIFmcyO7c0q6FTgcAAEi10vvq28CXWAkAC1es6/r74spUCgAARa3z/vvixlEIAEGq8/7+5slTCQBCqvL+/ObJUgkAQarx/v3mx1IKAD+q8v7+58lSCQA/qvH+/ebHUgoAP6rx/v3mx1IKAD+p8f795sdSCgA+qfH+/ebHUgoAPqnx/v3mx1IKAD6p8f795sdSCgA+qfH+/ebHUgoAPqnx/v3mx1IKAD6p8f795sdSCgA+qfH+/ebHUgoAPqnx/v3mx1IKAD6p8f795sdSCgA+qfH+/ebHUgoAPqnx/v3mx1IKAD2p8f795sZSCgA9qfH+/ebGUgoAPanw/v3mxlIKAD2p8P795sZSCgA9qfD+/ebGUgoAPanw/v3mxlIKAD2p8P795sZSCgA9qfD+/ebGUgoAPanw/v3mxlIKAD2p8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA7qfD+/ebGUgoAO6nw/v3mxlIKADup8P795sZSCgA7qfD+/ebGUgoAO6nw/v3mxlIKADup8P795sZSCgA7qfD+/ebGUgoAO6nw/v3mxlIKADup8P795sZSCgA7qfD+/ebGUgoAO6nw/v3mxlIKADup8P795sZSCgA7qfD+/ebGUgoAO6nw/v3mxlIKADup8P795sZSCgA7qfD+/ebGUgoAO6nw/v3mxlIKADuqPD+/ebGUgoAOqny/v3myFIKADup8v797shSCgA6qvP+/ejIUQsAOarz/v7pxlAMADmr9P7/6MRPDAA4rPb+/+bBTg4ANa/5/v/juUwRADLC/Pv55LJEFD4AAM3f8eq9ekAAADMWl9K8gVRQTnaCbAAajMNPUGn1/f1IPQAYmtclNl7iyO/sHAAAKMy/FClrk8PomRcAACLOyxIYZZrK8Z8TAAAhz9AJFGC14OKMEQAALdPIISRip9TkfxQAADfWxx0rZZrF6XgSAAA51dUcKnChtN5tEgAAQtPmGjE0U6b44E0MAABJ2dUfLS5zk9zVaxEAAEjbzB8qOHmPzddiEwAAS9LLJS08g4i7x2cXAABKy8wwKlFjeNDZYRYAAE7Py0guXEV9ycJxGQAATszQUCxoF5NAqxwAAFbMzWgrdodfVJAfAABJbVoNAAECAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMA==");
        audio.play();
        console.log("Notification sound played");
    }
    
    
    // Function to set the trading window
    function setTradingWindow() {
        const startDate = document.getElementById('window-start').value;
        const endDate = document.getElementById('window-end').value;
        
        if (!startDate || !endDate) {
            showMsg('Please select both start and end dates', 'red');
            return;
        }
        
        if (new Date(startDate) > new Date(endDate)) {
            showMsg('Start date must be before end date', 'red');
            return;
        }
        
        showSpinner('Setting trading window...');
        
        fetch('/api/set_trading_window', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                start_date: startDate,
                end_date: endDate
            })
        })
        .then(r => r.json())
        .then(data => {
            updateTable(data.status);
            showMsg(data.message || 'Trading window set!', 'green');
            
            // Update date inputs with the selected values for visual confirmation
            document.getElementById('window-start').value = data.status.window_start;
            document.getElementById('window-end').value = data.status.window_end;
            
            setTimeout(() => { document.getElementById('msg').innerText = ''; }, 3000);
        })
        .catch(() => {
            showMsg('Failed to set trading window', 'red');
        });
    }
    
    function updateTable(data) {
        // Update trading window heading and dates
        document.getElementById('month').innerText = data.month || '-';
        
        // If window dates are provided, update the date inputs
        if (data.window_start) {
            document.getElementById('window-start').value = data.window_start;
        }
        if (data.window_end) {
            document.getElementById('window-end').value = data.window_end;
        }
        
        // Update price and date fields
        document.getElementById('baseline_date').innerText = data.baseline_date || '-';
        document.getElementById('baseline_price').innerText = data.baseline_price || '-';
        document.getElementById('peak_price').innerText = (data.peak_price === undefined || data.peak_price === null) ? '–' : data.peak_price;
        document.getElementById('peak_date').innerText = (data.peak_date === undefined || data.peak_date === null) ? '–' : data.peak_date;
        document.getElementById('current_price').innerText = data.current_price || '-';
    }
    function clearAll() {
        // Save current form values
        const startDate = document.getElementById('window-start').value;
        const endDate = document.getElementById('window-end').value;
        
        showSpinner('Clearing...');
        fetch('/api/clear', {method:'POST'})
        .then(r=>r.json()).then(data=>{
            clearTable(); // Only clear the display table, not form inputs
            
            // Restore the date input values
            if (startDate) document.getElementById('window-start').value = startDate;
            if (endDate) document.getElementById('window-end').value = endDate;
            
            // Don't clear email recipients, just reload them
            loadEmailRecipients();
            
            showMsg('All price values cleared!', 'green');
        });
    }
    function clearTable() {
        document.getElementById('baseline_date').innerText = '';
        document.getElementById('baseline_price').innerText = '';
        document.getElementById('peak_date').innerText = '';
        document.getElementById('peak_price').innerText = '';
        document.getElementById('current_price').innerText = '';
        document.getElementById('month').innerText = '';
    }
    function showSpinner(msg) {
        document.getElementById('msg').innerHTML = '<span class="spinner"></span>' + msg;
    }
    function showMsg(msg, color) {
        document.getElementById('msg').innerHTML = '<span style="color:' + (color||'green') + '">' + msg + '</span>';
    }
    function refreshStatus() {
        // Save current values before refreshing
        const startDate = document.getElementById('window-start').value;
        const endDate = document.getElementById('window-end').value;
        
        showSpinner('Refreshing...');
        fetch('/api/refresh', {method:'POST'})
        .then(r=>r.json()).then(data=>{
            updateTable(data.status);
            
            // Restore date values if they're not provided in the response
            if (!data.status.window_start && startDate) {
                document.getElementById('window-start').value = startDate;
            }
            if (!data.status.window_end && endDate) {
                document.getElementById('window-end').value = endDate;
            }
            
            // Reload email recipients to ensure they're up to date
            loadEmailRecipients();
            
            showMsg(data.message || 'Refreshed!', 'green');
            setTimeout(()=>{document.getElementById('msg').innerText='';}, 1800);
        }).catch(()=>{
            showMsg('Failed to refresh.', 'red');
        });
    }
    function simulatePeak() {
        // Save current values before simulating
        const startDate = document.getElementById('window-start').value;
        const endDate = document.getElementById('window-end').value;
        
        showSpinner('Simulating...');
        fetch('/api/simulate_peak', {method:'POST'})
        .then(r=>r.json()).then(data=>{
            updateTable(data.status);
            
            // Restore date values if they're not provided in the response
            if (!data.status.window_start && startDate) {
                document.getElementById('window-start').value = startDate;
            }
            if (!data.status.window_end && endDate) {
                document.getElementById('window-end').value = endDate;
            }
            
            // Reload email recipients to ensure they're up to date
            loadEmailRecipients();
            
            showMsg(data.message || 'Simulated peak!', 'green');
            playNotificationSound(); // Play sound notification when a peak is simulated
            setTimeout(()=>{document.getElementById('msg').innerText='';}, 1800);
        }).catch(()=>{
            showMsg('Failed to simulate.', 'red');
        });
    }
    // Store the current peak value to detect changes
    let previousPeakValue = null;
    
    // Store email recipients
    let emailRecipients = [];
    
    // Check if peak value has changed and notify if it has
    function checkForPeakChanges(data) {
        // First update the table with new data
        updateTable(data);
        
        // Check if this is a new peak
        if (data.peak_price !== null && 
            data.peak_price !== undefined &&
            previousPeakValue !== null &&
            previousPeakValue !== undefined &&
            data.peak_price > previousPeakValue) {
            
            // Play notification for new peak
            playNotificationSound();
            showMsg('New peak detected!', 'green');
            setTimeout(()=>{document.getElementById('msg').innerText='';}, 3000);
        }
        
        // Update our stored peak value
        previousPeakValue = data.peak_price;
    }
    
    // Initial load
    function loadStatus() {
        fetch('/api/status')
            .then(r => r.json())
            .then(data => {
                previousPeakValue = data.peak_price;
                updateTable(data);
            });
    }
    
    // Set up automatic polling to check for changes
    function startAutomaticChecking() {
        // Check every 10 seconds for updates
        setInterval(() => {
            fetch('/api/status')
                .then(r => r.json())
                .then(checkForPeakChanges);
        }, 10000); // 10 seconds
    }
    
    // Email management functions
    function loadEmailRecipients() {
        fetch('/api/email_recipients')
            .then(r => r.json())
            .then(data => {
                emailRecipients = data.recipients || [];
                renderEmailList();
            })
            .catch(() => {
                showMsg('Failed to load email recipients', 'red');
            });
    }
    
    function renderEmailList() {
        const listEl = document.getElementById('email-list');
        listEl.innerHTML = '';
        
        if (emailRecipients.length === 0) {
            listEl.innerHTML = '<div class="loading-placeholder">No recipients added yet</div>';
            return;
        }
        
        emailRecipients.forEach((email, index) => {
            const itemEl = document.createElement('div');
            itemEl.className = 'email-item';
            itemEl.innerHTML = `
                <span class="email-address">${email}</span>
                <button class="delete-email" onclick="removeEmailRecipient(${index})">Remove</button>
            `;
            listEl.appendChild(itemEl);
        });
    }
    
    function addEmailRecipient() {
        const emailInput = document.getElementById('new-email');
        const email = emailInput.value.trim();
        
        if (!email) {
            showMsg('Please enter an email address', 'red');
            return;
        }
        
        // Basic email validation
        if (!email.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) {
            showMsg('Please enter a valid email address', 'red');
            return;
        }
        
        // Check if email already exists
        if (emailRecipients.includes(email)) {
            showMsg('This email is already in the list', 'red');
            return;
        }
        
        fetch('/api/add_email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                emailRecipients = data.recipients;
                renderEmailList();
                emailInput.value = '';
                showMsg('Email added successfully!', 'green');
                setTimeout(() => { document.getElementById('msg').innerText = ''; }, 1800);
            } else {
                showMsg(data.message || 'Failed to add email', 'red');
            }
        })
        .catch(() => {
            showMsg('Failed to add email', 'red');
        });
    }
    
    function removeEmailRecipient(index) {
        if (index < 0 || index >= emailRecipients.length) {
            return;
        }
        
        const emailToRemove = emailRecipients[index];
        
        fetch('/api/remove_email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: emailToRemove })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                emailRecipients = data.recipients;
                renderEmailList();
                showMsg('Email removed successfully', 'green');
                setTimeout(() => { document.getElementById('msg').innerText = ''; }, 1800);
            } else {
                showMsg(data.message || 'Failed to remove email', 'red');
            }
        })
        .catch(() => {
            showMsg('Failed to remove email', 'red');
        });
    }
    
    // Initialize everything
    loadStatus();
    loadEmailRecipients();
    startAutomaticChecking();
    </script>
    '''
    return render_template_string(html)

@app.route('/api/status')
def api_status():
    data = load_data()
    
    # Fetch fresh stock price when status is requested
    current_price = fetch_sn_price()
    
    # Check if there's an active trading window set
    if 'active_window' in data:
        window_key = data['active_window']
        window_data = data.get(window_key, {})
        
        # Update the current price if we have a fresh one
        if current_price is not None:
            window_data['current_price'] = round(current_price, 2)
            data[window_key] = window_data
            save_data(data)
        
        # Parse the window_key to get start and end dates
        try:
            start_date, end_date = window_key.split('_to_')
            return jsonify({
                "month": f"{start_date} to {end_date}",  # Display format
                "window_start": start_date,
                "window_end": end_date,
                **window_data
            })
        except Exception:
            # Fall back to using window_key as is
            return jsonify({"month": window_key, **window_data})
    else:
        # Default to current month if no window is set
        month = get_current_month()
        month_data = data.get(month, {})
        
        # Update the current price if we have a fresh one
        if current_price is not None:
            month_data['current_price'] = round(current_price, 2)
            data[month] = month_data
            save_data(data)
            
        return jsonify({"month": month, **month_data})

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    try:
        print("Starting refresh operation...")
        # First fetch the current stock price
        current_price = fetch_sn_price()
        if current_price is None:
            return jsonify({"status": "error", "message": "Could not fetch current price"})
            
        # Get the current data
        data = load_data()
        
        # We'll handle everything manually to avoid complex interactions
        if 'active_window' in data:
            window_key = data['active_window']
            if window_key in data:
                # Always update the current price
                data[window_key]['current_price'] = round(current_price, 2)
                
                # If there's a simulated peak, reset it
                if data[window_key].get('peak_simulated', False):
                    data[window_key]['peak_price'] = None
                    data[window_key]['peak_date'] = None
                    data[window_key]['peak_simulated'] = False
                    print(f"Cleared simulated peak for {window_key}")
                
                # Save the changes
                save_data(data)
                print("Updated data saved")
                
                # Now we'll fetch the data again to make sure we have the latest
                data = load_data()
                window_data = data.get(window_key, {})
                
                # Format the response based on window key format
                try:
                    if '_to_' in window_key:
                        start_date, end_date = window_key.split('_to_')
                        return jsonify({
                            "status": {
                                "month": f"{start_date} to {end_date}",
                                "window_start": start_date,
                                "window_end": end_date,
                                **window_data
                            },
                            "message": "Refreshed!"
                        })
                    else:
                        # For monthly windows
                        return jsonify({"status": {"month": window_key, **window_data}, "message": "Refreshed!"})
                except Exception as e:
                    print(f"Error formatting response: {e}")
                    return jsonify({"status": {"month": window_key, **window_data}, "message": "Refreshed!"})
            else:
                # Window key not found in data
                return jsonify({"status": "error", "message": f"No data found for window {window_key}"})
        else:
            # No active window set
            month = get_current_month()
            month_data = data.get(month, {})
            return jsonify({"status": {"month": month, **month_data}, "message": "Refreshed!"})
        data = load_data()
        
        # Check if there's an active trading window set
        if 'active_window' in data:
            window_key = data['active_window']
            window_data = data.get(window_key, {})
            
            try:
                # Parse the window_key to get start and end dates
                if '_to_' in window_key:
                    start_date, end_date = window_key.split('_to_')
                    return jsonify({
                        "status": {
                            "month": f"{start_date} to {end_date}",  # Display format
                            "window_start": start_date,
                            "window_end": end_date,
                            **window_data
                        }, 
                        "message": "Refreshed!"
                    })
                else:
                    # Handle case where window_key is not in expected format
                    return jsonify({"status": {"month": window_key, **window_data}, "message": "Refreshed!"})
            except Exception as e:
                print(f"Error parsing window key: {e}")
                # Fall back to using window_key as is
                return jsonify({"status": {"month": window_key, **window_data}, "message": "Refreshed!"})
        else:
            # Default to current month if no window is set
            month = get_current_month()
            month_data = data.get(month, {})
            return jsonify({"status": {"month": month, **month_data}, "message": "Refreshed!"})
    except Exception as e:
        print(f"Error in api_refresh: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": f"Refresh failed: {str(e)}"})

@app.route('/api/set_trading_window', methods=['POST'])
def api_set_window():
    data = load_data()
    # Get start and end dates from the request
    start_date = request.json.get('start_date')
    end_date = request.json.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({'error': 'Missing start_date or end_date'}), 400
    
    # Create a unique key for this window
    window_key = format_window_key(start_date, end_date)
    
    # Set this as the active window
    data['active_window'] = window_key
    
    # Initialize window data if it doesn't exist
    if window_key not in data:
        data[window_key] = {
            'baseline_price': None,
            'baseline_date': None,
            'peak_price': None,
            'peak_date': None,
            'current_price': None,
            'peak_simulated': False,
            'last_real_peak_price': None,
            'last_real_peak_date': None,
        }
    
    save_data(data)
    
    # Force a stock check to update the data with the new window
    monitor_stock()
    
    # Fetch the updated data
    updated_data = load_data()
    window_data = updated_data.get(window_key, {})
    
    return jsonify({
        'status': {
            'month': f"{start_date} to {end_date}",
            'window_start': start_date,
            'window_end': end_date,
            **window_data
        },
        'message': f'Trading window set from {start_date} to {end_date}!'
    })

@app.route('/api/clear', methods=['POST'])
def api_clear():
    data = load_data()
    # Check if there's an active window
    if 'active_window' in data:
        window_key = data['active_window']
        if window_key in data:
            del data[window_key]
        del data['active_window']
    else:
        # Default to current month
        month = get_current_month()
        if month in data:
            del data[month]
    
    save_data(data)
    return jsonify({'status': {}, 'message': 'Cleared!'})

@app.route('/api/email_recipients')
def api_email_recipients():
    data = load_data()
    recipients = data.get('email_recipients', [])
    return jsonify({'recipients': recipients})

@app.route('/api/add_email', methods=['POST'])
def api_add_email():
    email = request.json.get('email', '').strip()
    
    # Basic validation
    if not email or '@' not in email:
        return jsonify({'success': False, 'message': 'Invalid email address'})
    
    data = load_data()
    recipients = data.get('email_recipients', [])
    
    # Check if email already exists
    if email in recipients:
        return jsonify({'success': False, 'message': 'Email already exists'})
    
    # Add the new email
    recipients.append(email)
    data['email_recipients'] = recipients
    save_data(data)
    
    return jsonify({'success': True, 'recipients': recipients, 'message': 'Email added successfully'})

@app.route('/api/remove_email', methods=['POST'])
def api_remove_email():
    email = request.json.get('email', '').strip()
    
    if not email:
        return jsonify({'success': False, 'message': 'No email provided'})
    
    data = load_data()
    recipients = data.get('email_recipients', [])
    
    # Remove the email if it exists
    if email in recipients:
        recipients.remove(email)
        data['email_recipients'] = recipients
        save_data(data)
        return jsonify({'success': True, 'recipients': recipients, 'message': 'Email removed successfully'})
    else:
        return jsonify({'success': False, 'message': 'Email not found in the list'})

@app.route('/api/simulate_peak', methods=['POST'])
def api_simulate_peak():
    try:
        data = load_data()
        
        # Check if there's an active trading window set
        if 'active_window' in data:
            window_key = data['active_window']
            if window_key not in data:
                return jsonify({"status": {"message": "No data for current trading window."}, "message": "No data found."})
        else:
            # Default to current month if no window is set
            window_key = get_current_month()
            if window_key not in data:
                return jsonify({"status": {"month": window_key}, "message": "No data for this month."})
        
        # Initialize fields if they don't exist
        if 'last_real_peak_price' not in data[window_key]:
            data[window_key]['last_real_peak_price'] = None
            
        if 'last_real_peak_date' not in data[window_key]:
            data[window_key]['last_real_peak_date'] = None
        
        # Save the current peak as the last real peak before simulating
        if not data[window_key].get('peak_simulated', False) and data[window_key].get('peak_price') is not None:
            data[window_key]['last_real_peak_price'] = data[window_key]['peak_price']
            data[window_key]['last_real_peak_date'] = data[window_key].get('peak_date')
        
        # Get the reference price for simulation
        reference_price = 500  # Default fallback
        
        if data[window_key].get('last_real_peak_price') is not None:
            reference_price = data[window_key]['last_real_peak_price']
        elif data[window_key].get('peak_price') is not None and not data[window_key].get('peak_simulated', False):
            reference_price = data[window_key]['peak_price']
        elif data[window_key].get('baseline_price') is not None:
            reference_price = data[window_key]['baseline_price']
        elif data[window_key].get('current_price') is not None:
            reference_price = data[window_key]['current_price']
            
        # Simulate a new peak by adding 100 to the reference price
        simulated_peak = round(reference_price + 100, 2)
        data[window_key]['current_price'] = simulated_peak
        data[window_key]['peak_price'] = simulated_peak
        data[window_key]['peak_date'] = get_today()
        data[window_key]['peak_simulated'] = True
        save_data(data)
        
        # Send notification
        notify_peak(simulated_peak, is_simulation=True)
        
        # Build response based on window type
        if 'active_window' in data and '_to_' in window_key:
            # Parse window for display
            start_date, end_date = window_key.split('_to_')
            return jsonify({
                "status": {
                    "month": f"{start_date} to {end_date}",
                    "window_start": start_date,
                    "window_end": end_date,
                    **data[window_key]
                }, 
                "message": "Simulated peak!"
            })
        else:
            return jsonify({"status": {"month": window_key, **data[window_key]}, "message": "Simulated peak!"})
    except Exception as e:
        print(f"Error in simulate_peak: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": f"Failed to simulate peak: {str(e)}"})

def get_recommendation_text(current_profit, best_profit, best_date):
    """Generate a recommendation based on profitability scores"""
    try:
        # Handle None values immediately
        if current_profit is None or best_profit is None:
            return "Insufficient data to make a recommendation at this time."
        
        # Convert pandas Series to scalar values if needed
        if hasattr(current_profit, 'item'):
            try:
                current_profit = current_profit.item()
            except:
                current_profit = float(current_profit)
                
        if hasattr(best_profit, 'item'):
            try:
                best_profit = best_profit.item()
            except:
                best_profit = float(best_profit)
            
        # Convert string inputs to float if possible
        if isinstance(current_profit, str):
            try:
                current_profit = float(current_profit)
            except ValueError:
                return "Unable to process profitability data."
                
        if isinstance(best_profit, str):
            try:
                best_profit = float(best_profit)
            except ValueError:
                return "Unable to process profitability data."
        
        # Safety check for best_date
        if best_date is None or best_date == 'N/A':
            best_date = "unknown date"
            
        # Calculate the difference without formatting
        try:
            profit_gap = best_profit - current_profit
        except Exception:
            profit_gap = 0
            
        # Generate plain text recommendations without formatting
        if current_profit >= 80:
            return '<span class="action-strong">STRONG SELL RECOMMENDATION</span>: Current profitability is excellent (80+ score). Market conditions favor selling NOW for maximum profit based on both stock price and USD/ILS exchange rate.'
            
        elif current_profit >= 70:
            return '<span class="action-strong">SELL RECOMMENDATION</span>: Current profitability is very good (70+ score). Consider selling now as conditions are favorable both for stock price and exchange rate.'
            
        elif current_profit >= 60:
            if profit_gap < 10:
                return '<span class="action-strong">CONSIDER SELLING</span>: Current profitability is good (60+ score) and close to the optimal selling point. Selling now would capture most of the potential profit.'
            else:
                msg = '<span class="action-strong">WAIT WITH CAUTION</span>: Current profitability is good (60+ score), but significantly better conditions may occur.'
                msg += ' The best selling day appears to be ' + str(best_date)
                try:
                    msg += ' with a ' + str(int(best_profit)) + ' score.'
                except:
                    msg += '.'
                return msg
        
        elif current_profit >= 50:
            msg = '<span class="action-strong">HOLD</span>: Current profitability is moderate (50+ score). Better selling opportunities are likely in the future.'
            msg += ' The best potential selling date based on historical data is ' + str(best_date) + '.'
            return msg
            
        elif current_profit >= 30:
            msg = '<span class="action-strong">HOLD FIRMLY</span>: Current profitability is below average ('
            try:
                msg += str(int(current_profit))
            except:
                msg += 'low'
            msg += ' score). Conditions for selling are not ideal at present. Consider waiting for improved market conditions.'
            return msg
            
        else:
            return '<span class="action-strong">DO NOT SELL</span>: Current profitability is poor. This is not an advantageous time to sell based on both stock price and USD/ILS exchange rate. Better to wait for more favorable market conditions.'
            
    except Exception as e:
        print(f"Error generating recommendation: {e}")
        return "Unable to generate a recommendation due to a calculation error."

# Fetch historical ServiceNow stock prices
def fetch_historical_sn_prices(days=30):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    try:
        # Get ServiceNow stock data
        data = yf.download('NOW', start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        
        # Extract closing prices
        sn_prices = {}
        for date, row in data.iterrows():
            date_str = date.strftime('%Y-%m-%d')
            sn_prices[date_str] = round(row['Close'], 2)
            
        return sn_prices
    except Exception as e:
        print(f"Error fetching SN prices: {e}")
        return {}

# Fetch historical S&P 500 prices
def fetch_historical_sp_prices(days=30):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    try:
        # Get S&P 500 data using yfinance (^GSPC is the ticker for S&P 500)
        data = yf.download('^GSPC', start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        
        # Extract closing prices
        sp_prices = {}
        for date, row in data.iterrows():
            date_str = date.strftime('%Y-%m-%d')
            sp_prices[date_str] = round(row['Close'], 2)
            
        return sp_prices
    except Exception as e:
        print(f"Error fetching S&P 500 prices: {e}")
        return {}

# Calculate buying profitability for S&P 500
def calculate_buy_profitability(sp_prices, exchange_rates):
    """
    Calculate the profitability of buying S&P 500 based on:
    1. Lower S&P price = better buying opportunity
    2. Stronger ILS (lower USD/ILS rate) = better buying power
    
    Returns a dictionary of profitability scores by date using min/max normalization
    """
    if not sp_prices or not exchange_rates:
        return {}
    
    # Get common dates between S&P prices and exchange rates
    common_dates = sorted(set(sp_prices.keys()) & set(exchange_rates.keys()))
    if not common_dates:
        return {}
    
    # Extract scalar values to avoid Series truth value ambiguity
    # Make sure we're working with primitive float values, not Series or DataFrames
    scalar_sp_values = {}
    scalar_exchange_rates = {}
    
    for date in common_dates:
        try:
            # Convert to float to ensure we have scalar values
            scalar_sp_values[date] = float(sp_prices[date])
            scalar_exchange_rates[date] = float(exchange_rates[date])
        except (ValueError, TypeError):
            # Skip dates with invalid values
            continue
    
    # Get new common dates after potential filtering
    valid_dates = sorted(set(scalar_sp_values.keys()) & set(scalar_exchange_rates.keys()))
    if not valid_dates:
        return {}
    
    # Calculate min and max values
    sp_value_list = list(scalar_sp_values.values())
    rate_value_list = list(scalar_exchange_rates.values())
    
    min_sp = min(sp_value_list)
    max_sp = max(sp_value_list)
    sp_range = max_sp - min_sp
    
    min_rate = min(rate_value_list)
    max_rate = max(rate_value_list)
    rate_range = max_rate - min_rate
    
    # Normalize and calculate profitability
    # For S&P: lower price = higher score (inverse relationship)
    # For exchange rate: lower rate = higher score (inverse relationship)
    profitability = {}
    
    for date in valid_dates:
        # Normalize S&P price (lower = better)
        if sp_range > 0:
            normalized_sp = 1 - ((scalar_sp_values[date] - min_sp) / sp_range)  # Inverse: lower price = higher score
        else:
            normalized_sp = 0.5  # Default if no range
        
        # Normalize exchange rate (lower = better)
        if rate_range > 0:
            normalized_rate = 1 - ((scalar_exchange_rates[date] - min_rate) / rate_range)  # Inverse: lower rate = higher score
        else:
            normalized_rate = 0.5  # Default if no range
        
        # Calculate final score (70% price, 30% exchange rate)
        profitability[date] = (normalized_sp * 0.7 + normalized_rate * 0.3) * 100
    
    return profitability

# Function to get buy recommendation text
def get_buy_recommendation_text(current_profit, best_profit, best_date):
    """Generate recommendation text based on buy profitability scores."""
    try:
        # Handle None values immediately
        if current_profit is None or best_profit is None:
            return "Insufficient data to make a recommendation at this time."
        
        # Convert pandas Series to scalar values if needed
        if hasattr(current_profit, 'item'):
            try:
                current_profit = current_profit.item()
            except:
                current_profit = float(current_profit)
                
        if hasattr(best_profit, 'item'):
            try:
                best_profit = best_profit.item()
            except:
                best_profit = float(best_profit)
        
        # Convert string inputs to float if possible
        if isinstance(current_profit, str):
            try:
                current_profit = float(current_profit)
            except ValueError:
                return "Unable to process profitability data."
                
        if isinstance(best_profit, str):
            try:
                best_profit = float(best_profit)
            except ValueError:
                return "Unable to process profitability data."
        
        # Safety check for best_date
        if best_date is None or best_date == 'N/A':
            best_date = "unknown date"
            
        # Calculate the difference without formatting
        try:
            profit_gap = best_profit - current_profit
        except Exception:
            profit_gap = 0
            
        # Generate recommendations based on buying score
        if current_profit >= 80:
            return '<span class="action-strong">STRONG BUY RECOMMENDATION</span>: Current buying opportunity score is excellent (80+ score). Market conditions strongly favor buying NOW based on both S&P price and USD/ILS exchange rate.'
            
        elif current_profit >= 70:
            return '<span class="action-strong">BUY RECOMMENDATION</span>: Current buying opportunity is very good (70+ score). Consider buying now as conditions are favorable for both S&P price and exchange rate.'
            
        elif current_profit >= 60:
            if profit_gap < 10:
                return '<span class="action-strong">CONSIDER BUYING</span>: Current buying opportunity is good (60+ score) and close to the optimal buying point. Buying now would capture most of the potential value.'
            else:
                msg = '<span class="action-strong">WAIT WITH CAUTION</span>: Current buying opportunity is good (60+ score), but significantly better conditions may occur.'
                msg += ' The best buying day appears to be ' + str(best_date)
                try:
                    msg += ' with a ' + str(int(best_profit)) + ' score.'
                except:
                    msg += '.'
                return msg
        
        elif current_profit >= 50:
            msg = '<span class="action-strong">WAIT</span>: Current buying opportunity is moderate (50+ score).'
            msg += ' Better conditions are likely on ' + str(best_date)
            try:
                msg += ' with a ' + str(int(best_profit)) + ' score.'
            except:
                msg += '.'
            return msg
            
        elif current_profit >= 40:
            return '<span class="action-strong">WAIT FOR BETTER CONDITIONS</span>: Current buying opportunity is below average (40+ score). Waiting for better market conditions is recommended.'
            
        elif current_profit >= 30:
            return '<span class="action-strong">NOT RECOMMENDED</span>: Current buying opportunity is poor (30+ score). S&P price is too high or USD/ILS exchange rate is unfavorable. Consider waiting for a significant market correction.'
            
        else:
            return '<span class="action-strong">AVOID BUYING</span>: Current buying opportunity is very poor. Market conditions are highly unfavorable for buying S&P 500 with ILS at this time.'
    except Exception as e:
        return f"Unable to generate recommendation due to an error: {e}"

# Route for the best to sell SN page
@app.route('/best-to-sell')
def best_to_sell():
    # Get the timeframe parameter from query string, default to 30 days
    timeframe = request.args.get('timeframe', '30')
    # Convert to integer and validate (default to 30 if invalid)
    try:
        days = int(timeframe)
        if days not in [30, 60, 90]:
            days = 30
    except ValueError:
        days = 30
    
    # Fetch historical data with the specified timeframe
    stock_prices = fetch_historical_sn_prices(days)
    exchange_rates = fetch_historical_ils_usd_rates(days)
    
    profitability = calculate_sell_profitability(stock_prices, exchange_rates)
    
    # Get common dates between stock prices and exchange rates
    common_dates = sorted(set(stock_prices.keys()) & set(exchange_rates.keys()) & set(profitability.keys()))
    
    # Initialize variables with default values
    current_profit = None
    current_price = None
    current_rate = None
    best_profit = None
    best_date = None
    
    if common_dates:
        # Get current dates/values
        current_date = common_dates[-1]  # Last date is the current date
        current_profit = profitability.get(current_date)
        current_price = stock_prices.get(current_date)
        current_rate = exchange_rates.get(current_date)
        
        # Find the best day to sell (highest profitability score)
        # Ensure we're working with scalar values, not Series
        profit_values = []
        for date in common_dates:
            try:
                value = profitability[date]
                # If it's a pandas Series, convert to scalar
                if hasattr(value, 'item'):
                    profit_values.append(value.item())
                else:
                    profit_values.append(float(value))
            except (ValueError, TypeError):
                continue
                
        if profit_values:
            best_profit = max(profit_values)
            
            # Find all dates with the best profitability score
            # Find all dates with the best profitability score - properly handle Series comparison
            best_dates = []
            for date in common_dates:
                try:
                    value = profitability[date]
                    # Convert to scalar if it's a Series
                    if hasattr(value, 'item'):
                        scalar_value = value.item()
                    else:
                        scalar_value = float(value)
                        
                    # Compare scalar values
                    if abs(scalar_value - best_profit) < 0.0001:  # Use small epsilon for float comparison
                        best_dates.append(date)
                except (ValueError, TypeError):
                    continue
            if best_dates:
                best_date = best_dates[0]
                
        # Ensure we're working with scalar values for string formatting
        try:
            current_profit_scalar = float(current_profit) if current_profit is not None else None
        except (TypeError, ValueError):
            current_profit_scalar = None
            
        try:
            best_profit_scalar = float(best_profit) if best_profit is not None else None
        except (TypeError, ValueError):
            best_profit_scalar = None
            
        try:
            current_price_scalar = float(current_price) if current_price is not None else None
        except (TypeError, ValueError):
            current_price_scalar = None
            
        try:
            current_rate_scalar = float(current_rate) if current_rate is not None else None
        except (TypeError, ValueError):
            current_rate_scalar = None
        
        # Format values for display
        formatted_current_profit = f"{current_profit_scalar:.1f}" if current_profit_scalar is not None else "N/A"
        formatted_best_profit = f"{best_profit_scalar:.1f}" if best_profit_scalar is not None else "N/A"
        formatted_best_date = best_date if best_date else "N/A"
        formatted_current_stock = f"{current_price_scalar:.2f}" if current_price_scalar is not None else "N/A"
        formatted_current_rate = f"{current_rate_scalar:.2f}" if current_rate_scalar is not None else "N/A"
        
        # Get recommendation text
        recommendation_text = get_recommendation_text(current_profit, best_profit, best_date)
        
        # Use the prepare_template_data function to safely handle all data serialization
        context = prepare_template_data(
            common_dates=common_dates, 
            profitability=profitability, 
            prices=stock_prices, 
            rates=exchange_rates, 
            current_profit=current_profit,
            best_profit=best_profit, 
            best_date=best_date, 
            current_price=current_price, 
            current_rate=current_rate
        )
        # Add recommendation text to context
        context['recommendation_text'] = recommendation_text
    else:
        # Use empty data template
        context = prepare_template_data([], {}, {}, {})
        context['recommendation_text'] = "Insufficient data to make a recommendation."
    
    # Add score explanation data for tooltips
    context['score_explanation'] = get_sell_score_explanation()
    
    # Add timeframe to context
    context['timeframe'] = days
    
    # Render the template with context
    return render_template('best_to_sell_new.html', **context)

# Route for the best to buy S&P page
@app.route('/best-to-buy-sp')
def best_to_buy_sp():
    # Get the timeframe parameter from query string, default to 30 days
    timeframe = request.args.get('timeframe', '30')
    # Convert to integer and validate (default to 30 if invalid)
    try:
        days = int(timeframe)
        if days not in [30, 60, 90]:
            days = 30
    except ValueError:
        days = 30
        
    # Fetch historical data with the specified timeframe
    sp_prices = fetch_historical_sp_prices(days)
    exchange_rates = fetch_historical_ils_usd_rates(days)
    
    # Calculate profitability for buying S&P
    profitability = calculate_buy_profitability(sp_prices, exchange_rates)
    
    # Get common dates between stock prices and exchange rates
    common_dates = sorted(set(sp_prices.keys()) & set(exchange_rates.keys()) & set(profitability.keys()))
    
    # Initialize variables with default values
    current_profit = None
    current_price = None
    current_rate = None
    best_profit = None
    best_date = None
    
    if common_dates:
        # Get current dates/values
        current_date = common_dates[-1]  # Last date is the current date
        current_profit = profitability.get(current_date)
        current_price = sp_prices.get(current_date)
        current_rate = exchange_rates.get(current_date)
        
        # Find the best day to buy (highest profitability score)
        # Ensure we're working with scalar values, not Series
        profit_values = []
        for date in common_dates:
            try:
                value = profitability[date]
                # If it's a pandas Series, convert to scalar
                if hasattr(value, 'item'):
                    profit_values.append(value.item())
                else:
                    profit_values.append(float(value))
            except (ValueError, TypeError):
                continue
                
        if profit_values:
            best_profit = max(profit_values)
            
            # Find all dates with the best profitability score
            # Find all dates with the best profitability score - properly handle Series comparison
            best_dates = []
            for date in common_dates:
                try:
                    value = profitability[date]
                    # Convert to scalar if it's a Series
                    if hasattr(value, 'item'):
                        scalar_value = value.item()
                    else:
                        scalar_value = float(value)
                        
                    # Compare scalar values
                    if abs(scalar_value - best_profit) < 0.0001:  # Use small epsilon for float comparison
                        best_dates.append(date)
                except (ValueError, TypeError):
                    continue
            if best_dates:
                best_date = best_dates[0]
                
        # Ensure we're working with scalar values for string formatting
        try:
            current_profit_scalar = float(current_profit) if current_profit is not None else None
        except (TypeError, ValueError):
            current_profit_scalar = None
            
        try:
            best_profit_scalar = float(best_profit) if best_profit is not None else None
        except (TypeError, ValueError):
            best_profit_scalar = None
            
        try:
            current_price_scalar = float(current_price) if current_price is not None else None
        except (TypeError, ValueError):
            current_price_scalar = None
            
        try:
            current_rate_scalar = float(current_rate) if current_rate is not None else None
        except (TypeError, ValueError):
            current_rate_scalar = None
        
        # Format values for display
        formatted_current_profit = f"{current_profit_scalar:.1f}" if current_profit_scalar is not None else "N/A"
        formatted_best_profit = f"{best_profit_scalar:.1f}" if best_profit_scalar is not None else "N/A"
        formatted_best_date = best_date if best_date else "N/A"
        formatted_current_stock = f"{current_price_scalar:.2f}" if current_price_scalar is not None else "N/A"
        formatted_current_rate = f"{current_rate_scalar:.2f}" if current_rate_scalar is not None else "N/A"
        
        # Get recommendation text
        recommendation_text = get_buy_recommendation_text(current_profit, best_profit, best_date)
        
        # Use the prepare_template_data function to safely handle all data serialization
        context = prepare_template_data(
            common_dates=common_dates, 
            profitability=profitability, 
            prices=sp_prices,  # Note: using sp_prices instead of stock_prices for this route
            rates=exchange_rates, 
            current_profit=current_profit,
            best_profit=best_profit, 
            best_date=best_date, 
            current_price=current_price, 
            current_rate=current_rate
        )
        # Add recommendation text to context
        context['recommendation_text'] = recommendation_text
    else:
        # Use empty data template
        context = prepare_template_data([], {}, {}, {})
        context['recommendation_text'] = "Insufficient data to make a recommendation."
    
    # Add score explanation data for tooltips
    context['score_explanation'] = get_buy_score_explanation()
    
    # Add timeframe to context
    context['timeframe'] = days

    # Render template with context data
    return render_template('best_to_buy_sp.html', **context)

# Route for the best to shift SN to S&P page
@app.route('/best-to-shift')
def best_to_shift():
    html = '''
    <style>
    body { background: #f6f8fa; font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; }
    .container { max-width: 520px; margin: 40px auto; background: #fff; border-radius: 16px; box-shadow: 0 2px 16px #0002; padding: 32px 24px; text-align: center; }
    /* Tab navigation */
    .tabs { display: flex; justify-content: space-between; margin-bottom: 20px; border-bottom: 1px solid #ddd; }
    .tab { flex: 1; padding: 10px 5px; text-align: center; cursor: pointer; color: #555; font-weight: 500; transition: all 0.3s ease; border-bottom: 3px solid transparent; }
    .tab.active { color: #1976d2; border-bottom: 3px solid #1976d2; }
    .tab:hover:not(.active) { color: #333; background-color: #f1f1f1; }
    /* Empty state */
    .empty-state { margin: 50px 0; padding: 30px; text-align: center; }
    .empty-state h3 { color: #555; margin-bottom: 10px; }
    .empty-state p { color: #777; margin-bottom: 20px; }
    </style>
    <div class="container">
      <div class="tabs">
        <a href="/" class="tab">SN Monitor</a>
        <a href="/best-to-sell" class="tab">Best to Sell</a>
        <a href="/best-to-buy-sp" class="tab">Buy S&P</a>
        <a href="/best-to-shift" class="tab active">Shift to S&P</a>
      </div>
      <h2>Best Time to Shift SN to S&P</h2>
      <div class="empty-state">
        <h3>Coming soon to theaters...</h3>
        <p>This feature is under development and will be available soon.</p>
      </div>
    </div>
    '''
    return render_template_string(html)

if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='ServiceNow Stock Monitor')
    parser.add_argument('--port', type=int, default=None, help='Port number for Flask app')
    args = parser.parse_args()
    
    print("--- Environment Information ---")
    print(f"ENVIRONMENT: {os.environ.get('ENVIRONMENT')}")
    print(f"RENDER: {os.environ.get('RENDER')}")
    print(f"PORT: {os.environ.get('PORT')}")
    print(f"FIREBASE_DATABASE_URL: {os.environ.get('FIREBASE_DATABASE_URL', 'NOT SET')}")
    print(f"FIREBASE_SERVICE_ACCOUNT_JSON present: {bool(os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON'))}")
    print("-----------------------------")
    
    # Get port from command line args or environment variable for cloud deployment
    port = args.port if args.port else int(os.environ.get('PORT', 5001))
    
    # Only send email if not in production (to avoid spamming)
    if os.environ.get('ENVIRONMENT') != 'production':
        try:
            send_email_alert(
                "SN Stock Monitor Started",
                f"The SN stock monitor script has started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.",
                "menypeled@gmail.com"
            )
        except Exception as e:
            print(f"Email notification failed: {e}")
    
    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Start the Flask web server - bind to 0.0.0.0 for cloud deployment
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'True').lower() == 'true')
