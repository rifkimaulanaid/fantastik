from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from helper.helper_function import *

# Configure Chrome Options
def web_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--verbose')
    options.add_argument('--no-sandbox')
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920, 1200')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    driver = webdriver.Chrome(options=options)
    return driver

def radar_scrap(start_date, end_date):
    """Scrap News Radar Tarakan"""
    scraped_data = []
    current_page = 1

    # Extract day, month text, and year form start_date and end_date
    start_day = start_date.day
    end_day = end_date.day
    start_month = start_date.strftime("%B")
    end_month = end_date.strftime("%B")
    start_year = start_date.year
    end_year = end_date.year

    while True:
        # Use start_day, end_day, etc. in the URL
        url = f'https://radartarakan.jawapos.com/indeks-berita?daterange={start_day}%20{start_month},%20{start_year}%20-%20{end_day}%20{end_month},%20{end_year}&page={current_page}'
        driver = web_driver()
        driver.get(url)

        # Wait for the page to load dynamically with a specific condition:
        wait = WebDriverWait(driver, 30)
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, '//div[@class="latest__item"]')))  
            # Check for presence of at least one article
        except Exception as e:
            print("Error:", e) # Print the exception for diagnosis
            driver.quit()
            break  # Exit loop in case of error

        articles = driver.find_elements(By.XPATH, '//div[@class="latest__item"]')
        
        if not articles:
            print("Tidak ada artikel ditemukan.")
            break

        for article in articles:
            category_tag = article.find_element(By.XPATH, './/h4[@class="latest__subtitle"]')
            title_tag = article.find_element(By.XPATH, './/h2[@class="latest__title"]')
            
            date_tag = article.find_element(By.XPATH, './/date[@class="latest__date"]').text.split('|')[0].strip()
            translated_date_str = translate_date(date_tag)
            article_date = datetime.strptime(translated_date_str, '%A, %d %B %Y').replace(hour=0, minute=0, second=0)
            
            link_tag = article.find_element(By.XPATH, './/h2[@class="latest__title"]/a')

            scraped_data.append({
                "Tagar": category_tag.text,
                "Judul": title_tag.text.replace('\xa0', ' '),
                "Tanggal": article_date.strftime('%Y-%m-%d'),
                "Tautan": link_tag.get_attribute('href'),
                "Sumber": "Radar Tarakan"
            })

        # The line below was incorrectly indented. It should be at the same level as the for loop.
        current_page += 1
        driver.quit() # Close the driver after each page

    return scraped_data