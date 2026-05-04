import pandas as pd
import requests
import time
import re

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
})

BLOCKED_RESPONSE_MARKERS = (
    "<title>tribunnews.com - 403</title>",
    "you don't have permission for this request",
    'var statuscode = "403"',
    '"http_error"',
)

# Data Range
def get_date_range(start_date, end_date):
    """Generate a list fo date strings between start_date and end_date"""
    return pd.date_range(start_date, end_date).strftime('%d-%m-%Y').tolist()

# Fetch Page
def fetch_page(url, retries=3, delay=2, timeout=10):
    """Fetch a webpage with retry logic and timeout"""
    for attempt in range(1, retries + 1):
        try:
            response = SESSION.get(url, timeout=timeout)
            response.raise_for_status()
            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding or response.encoding
            return response
        except requests.exceptions.RequestException as e:
            if attempt < retries:
                time.sleep(delay)
            else:
                print(f"[ERROR] Failed to fetch {url} after {retries} retries: {e}")
    return None


def decode_response_text(response):
    """Return response text with a best-effort mojibake repair pass."""
    if response is None:
        return None

    text = response.text
    suspicious_markers = ("â€", "â€™", "â€œ", "â€\x9d", "â€“", "â€”", "Â", "Ã")
    if any(marker in text for marker in suspicious_markers):
        try:
            repaired = text.encode("latin-1").decode("utf-8")
            text = repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    return text

def is_blocked_response(content):
    """Detect bot-block or deny pages returned as successful HTTP responses."""
    if not content:
        return False

    normalized = str(content).lower()
    return any(marker in normalized for marker in BLOCKED_RESPONSE_MARKERS)

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


def normalize_article_text(paragraphs_or_text):
    """Normalize article content into a single-line text block for storage/export."""
    if paragraphs_or_text is None:
        return None

    if isinstance(paragraphs_or_text, (list, tuple)):
        normalized_parts = [
            re.sub(r"\s+", " ", str(part)).strip()
            for part in paragraphs_or_text
            if str(part).strip()
        ]
        text = " ".join(normalized_parts)
    else:
        text = re.sub(r"\s+", " ", str(paragraphs_or_text)).strip()

    return text or None

def build_web_driver():
    """Build a reusable headless Chrome driver."""
    try:
        from selenium import webdriver
        from selenium.common.exceptions import NoSuchDriverException
        from selenium.webdriver.chrome.service import Service
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "Selenium belum tersedia. Install dengan `python -m pip install selenium webdriver-manager`."
        ) from e

    try:
        from webdriver_manager.chrome import ChromeDriverManager
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "webdriver-manager belum tersedia. Install dengan `python -m pip install webdriver-manager`."
        ) from e

    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1200")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    try:
        return webdriver.Chrome(options=options)
    except NoSuchDriverException:
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

def fetch_with_selenium(url, driver=None, timeout=20, mode="html"):
    """Fetch a page through Selenium and return HTML or visible text."""
    try:
        from selenium.common.exceptions import WebDriverException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
    except ModuleNotFoundError:
        print(f"[ERROR] Selenium unavailable while fetching {url}.")
        return None

    owned_driver = driver is None
    current_driver = driver or build_web_driver()

    try:
        current_driver.set_page_load_timeout(timeout)
        current_driver.get(url)
        WebDriverWait(current_driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(1)

        if mode == "text":
            return current_driver.find_element(By.TAG_NAME, "body").text
        return current_driver.page_source
    except WebDriverException as e:
        print(f"[ERROR] Selenium failed to fetch {url}: {e}")
        return None
    finally:
        if owned_driver:
            current_driver.quit()

def fetch_content_with_fallback(
    url,
    retries=3,
    delay=2,
    timeout=10,
    driver=None,
    selenium_timeout=20,
    mode="html",
):
    """Fetch a page with requests first and fallback to Selenium when blocked."""
    response = fetch_page(url, retries=retries, delay=delay, timeout=timeout)
    if response is not None:
        text = decode_response_text(response)
        if not is_blocked_response(text):
            return text

        print(f"[WARN] Requests response blocked for {url}, retrying with Selenium.")

    selenium_content = fetch_with_selenium(url, driver=driver, timeout=selenium_timeout, mode=mode)
    if is_blocked_response(selenium_content):
        print(f"[ERROR] Selenium response also blocked for {url}.")
        return None

    return selenium_content
