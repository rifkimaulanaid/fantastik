import pandas as pd
import requests
import time

# Data Range
def get_date_range(start_date, end_date):
    """Generate a list fo date strings between start_date and end_date"""
    return pd.date_range(start_date, end_date).strftime('%d-%m-%Y').tolist()

# Fetch Page
def fetch_page(url, retries=3, delay=2):
    """Fetch a webpage with retry logic and timeout"""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt < retries:
                time.sleep(delay)
            else:
                print(f"[ERROR] Failed to fetch {url} after {retries} retries: {e}")
    return None

# Mapping Indonesian to English day and month names
def translate_date(raw_date):
    """Translate Indonesian day and month names in a string to English."""
    day_mapping = {
        "Senin": "Monday", "Selasa": "Tuesday", "Rabu": "Wednesday",
        "Kamis": "Thursday", "Jumat": "Friday", "Sabtu": "Saturday",
        "Minggu": "Sunday"
    }
    month_mapping = {
        "Januari": "January", "Februari": "February", "Maret": "March",
        "April": "April", "Mei": "May", "Juni": "June",
        "Juli": "July", "Agustus": "August", "September": "September",
        "Oktober": "October", "November": "November", "Desember": "December"
    }
    
    for indo, eng in {**day_mapping, **month_mapping}.items():
        raw_date = raw_date.replace(indo, eng)
    return raw_date