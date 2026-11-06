"""Publisher configuration for the shared Jawapos adapter."""
from scrap.jawapos import RADAR, build_article_url as _url, extract_content, fetch_page, scrape, slugify_title


def build_article_url(article):
    return _url(article, RADAR)


def fetch_radar_page(start_date, end_date, page=1, per_page=20):
    return fetch_page(RADAR, start_date, end_date, page, per_page)


def extract_radar_content(url):
    return extract_content(url, RADAR)


def radar_scrap(start_date, end_date, progress_callback=None, **kwargs):
    return scrape(RADAR, start_date, end_date, progress_callback, **kwargs)
