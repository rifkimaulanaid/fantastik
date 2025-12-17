from bs4 import BeautifulSoup
from datetime import datetime
from helper.helper_function import *

# Prokal Scrap Function
def prokal_scrap(start_date, end_date):
    """Scrap News Prokal"""
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
        url = f'https://www.prokal.co/indeks-berita?daterange={start_day}%20{start_month}%20{start_year}%20-%20{end_day}%20{end_month}%20{end_year}&page={current_page}'
        response = fetch_page(url)
        if not response:
            break
            
        soup = BeautifulSoup(response.content, 'html.parser')
        articles = soup.find_all('div', class_='latest__item')
        if not articles:
            print("Tidak ada artikel ditemukan.")
            break
        
        for article in articles:
            category_tag = article.find('h4', class_='latest__subtitle')
            title_tag = article.find('h2', class_='latest__title')
    
            date_tag = article.find('date', class_='latest__date').text.strip().split('|')[0].strip()
            translated_date_str = translate_date(date_tag) # translate date
            article_date = datetime.strptime(translated_date_str, '%A, %d %B %Y').replace(hour=0, minute=0, second=0)
    
            link_tag = title_tag.find('a')

            scraped_data.append({
                "Tagar": category_tag.text.strip(),
                "Judul": title_tag.text.strip().replace('\xa0', ' '),
                "Tanggal": article_date.strftime('%Y-%m-%d'),
                "Tautan": link_tag['href'],
                "Sumber": "Prokal"
            })

        # The line below was incorrectly indented. It should be at the same level as the for loop.
        current_page += 1

    return scraped_data
