from bs4 import BeautifulSoup
from datetime import datetime
from helper.helper_function import *

# Benuanta Scrap Function
def benuanta_scrap(start_date, end_date, max_page=10):
    """Scrap News Benuanta with Performance Optimization"""
    scraped_data = []
    current_page = 1

    # Convert start date and end date to date.time
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    while current_page <= max_page:
        url = f'https://benuanta.co.id/index.php/page/{current_page}/?s'
        response = fetch_page(url)
        if not response:
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        articles = soup.find_all('article')

        if not articles:
            print("Tidak ada artikel ditemukan.")
            break

        for article in articles:
            date_tag = article.find('time')
            if date_tag:
                date_str = date_tag.text.strip()
                translated_date_str = translate_date(date_str) # translate date

                try:
                  # Parse the date string in the correct format with time and timezone
                    article_date = datetime.strptime(translated_date_str, '%d %B %Y').replace(hour=0, minute=0, second=0)

                except ValueError:
                    print(f"Could not parse date: {date_str}")
                    continue
                
                if start_datetime <= article_date <= end_datetime:
                    title_tag = article.find('h2')
                    category_tag = article.find('span', class_="gmr-meta-topic")
                    link_tag = article.find('a')

                    if title_tag and category_tag and link_tag:
                        scraped_data.append({
                            "Tagar": category_tag.text.strip(),
                            "Judul": title_tag.text.strip(),
                            "Tanggal": article_date.strftime('%Y-%m-%d'),
                            "Tautan": link_tag['href'],
                            "Sumber": "Benuanta"
                        })
          
        next_page = soup.find('a', class_="next page-numbers")
        if not next_page:
            break
          
        current_page += 1

    return scraped_data