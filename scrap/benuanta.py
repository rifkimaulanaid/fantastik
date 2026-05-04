from bs4 import BeautifulSoup
from datetime import datetime
from helper.helper_function import *

CONTENT_STOP_PREFIXES = (
    "Reporter:",
    "Editor:",
    "Baca juga:",
    "BACA JUGA:",
)


def extract_benuanta_content(url):
    """Fetch and normalize article body text from a Benuanta detail page."""
    response = fetch_page(url)
    if not response:
        return None

    soup = BeautifulSoup(decode_response_text(response), 'html.parser')
    content_node = soup.select_one('.entry-content')
    if not content_node:
        return None

    paragraphs = []
    for paragraph in content_node.find_all('p'):
        text = " ".join(paragraph.get_text(" ", strip=True).split())
        if not text:
            continue
        if text.startswith(CONTENT_STOP_PREFIXES):
            break
        paragraphs.append(text)

    if not paragraphs:
        return None

    return normalize_article_text(paragraphs)


# Benuanta Scrap Function
def benuanta_scrap(start_date, end_date, max_page=200, progress_callback=None):
    """Scrap News Benuanta across paginated index pages."""
    scraped_data = []
    current_page = 1

    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    has_reached_target_range = False

    while current_page <= max_page:
        if progress_callback:
            scan_progress = min(0.08 + ((current_page - 1) * 0.08), 0.82)
            progress_callback(
                scan_progress,
                f"Memindai halaman {current_page} indeks Benuanta.",
            )

        url = f'https://benuanta.co.id/index.php/page/{current_page}/?s'
        response = fetch_page(url)
        if not response:
            break

        soup = BeautifulSoup(decode_response_text(response), 'html.parser')
        articles = soup.find_all('article')

        if not articles:
            print("Tidak ada artikel ditemukan.")
            break

        page_dates = []
        for article in articles:
            date_tag = article.find('time')
            if not date_tag:
                continue

            date_str = date_tag.text.strip()
            translated_date_str = translate_date(date_str)

            try:
                article_date = datetime.strptime(translated_date_str, '%d %B %Y').replace(
                    hour=0,
                    minute=0,
                    second=0,
                )
            except ValueError:
                print(f"Could not parse date: {date_str}")
                continue

            page_dates.append(article_date)

            if article_date > end_datetime:
                continue

            if article_date < start_datetime:
                continue

            has_reached_target_range = True
            title_tag = article.find('h2')
            category_tag = article.find('span', class_="gmr-meta-topic")
            link_tag = article.find('a')

            if title_tag and category_tag and link_tag:
                article_url = link_tag['href']
                scraped_data.append({
                    "Tagar": category_tag.text.strip(),
                    "Judul": title_tag.text.strip(),
                    "Tanggal": article_date.strftime('%Y-%m-%d'),
                    "Tautan": article_url,
                    "Sumber": "Benuanta",
                    "Isi": extract_benuanta_content(article_url),
                })
                if progress_callback and len(scraped_data) % 5 == 0:
                    article_progress = min(0.15 + ((current_page - 1) * 0.08), 0.9)
                    progress_callback(
                        article_progress,
                        f"{len(scraped_data)} berita Benuanta sudah terkumpul.",
                    )

        if page_dates:
            newest_article_date = max(page_dates)
            oldest_article_date = min(page_dates)

            if newest_article_date < start_datetime:
                break

            if has_reached_target_range and oldest_article_date < start_datetime:
                break

        next_page = soup.find('a', class_="next page-numbers")
        if not next_page:
            break

        current_page += 1

    if progress_callback:
        progress_callback(1.0, f"Selesai. {len(scraped_data)} berita Benuanta terkumpul.")

    return scraped_data
