"""Publisher configuration for the shared Jawapos adapter."""
from scrap.jawapos import PROKAL, build_article_url as _url, extract_content, fetch_page, scrape, slugify_title


def build_article_url(article):
    return _url(article, PROKAL)


def fetch_prokal_page(start_date, end_date, page=1, per_page=20):
    return fetch_page(PROKAL, start_date, end_date, page, per_page)


def extract_prokal_content(url):
    return extract_content(url, PROKAL)


def prokal_scrap(start_date, end_date, progress_callback=None, **kwargs):
    return scrape(PROKAL, start_date, end_date, progress_callback, **kwargs)
