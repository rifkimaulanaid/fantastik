from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from datetime import datetime
from helper.helper_function import *
import random

# Configure Chrome Options
def web_driver():
    options = Options()
    options.binary_location = "/usr/bin/chromium-browser"
    options.add_argument('--verbose')
    options.add_argument('--no-sandbox')
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920, 1200')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    service = Service("/usr/lib/chromium-browser/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# Kaltara Tribunnews Scrap Function
def tribun_scrap(dates_to_scrape, delay = 10):
    """Scrap News Kaltara Tribunnews"""
    scraped_data = []
    driver = web_driver()

    try:
        for date_input in dates_to_scrape:
            current_page = 1
            while True:
                url = f'https://kaltara.tribunnews.com/index-news?date={date_input}&page={current_page}'
                driver.get(url)

                try:
                    # Wait for article container to load
                    WebDriverWait(driver, delay).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'li.ptb15'))
                    )
                except:
                    print(f"[INFO] No articles for {date_input} (Page {current_page})")
                    break

                articles = driver.find_elements(By.CSS_SELECTOR, 'li.ptb15')
                if not articles:
                    print("Tidak ada artikel ditemukan.")
                    break

                for article in articles:
                    try:
                        title_el = article.find_element(By.CSS_SELECTOR, "h3.f16.fbo")
                        title = title_el.text.strip()
                        link = title_el.find_element(By.TAG_NAME, "a").get_attribute("href")

                        try:
                            category = article.find_element(By.CSS_SELECTOR, "h4.red.fbo2.f14").text.strip()
                        except:
                            category = None

                        raw_date = article.find_element(By.CSS_SELECTOR, "time.grey").text.strip()
                        translated = translate_date(raw_date).replace("WITA", "+0800")
                        parsed = datetime.strptime(translated, "%A, %d %B %Y %H:%M %z")
                        date_only = parsed.date().strftime('%Y-%m-%d')

                        scraped_data.append({
                            "Tagar": category,
                            "Judul": title,
                            "Tanggal": date_only,
                            "Tautan": link,
                            "Sumber": "Kaltara Tribunnews"
                        })
                    except Exception as e:
                        print(f"[WARN] Skipping article due to: {e}")
                        continue

                current_page += 1
                time.sleep(random.uniform(1, 3))  # polite delay

    finally:
        driver.quit()

    return scraped_data