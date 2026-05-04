from bs4 import BeautifulSoup
from datetime import datetime
from helper.helper_function import build_web_driver, fetch_content_with_fallback, translate_date
import json
import random
import re
import time

ROOT_SITEMAP_URL = "https://kaltara.tribunnews.com/sitemap.xml"
SOURCE_NAME = "Kaltara Tribunnews"
SITEMAP_TYPES = ("sitemap_news.xml", "sitemap_web.xml")
EXCLUDED_SITEMAP_SECTIONS = ("iklan-online",)
ARTICLE_URL_DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")
MAX_SITEMAP_DEPTH = 4

def normalize_target_dates(dates_to_scrape):
    """Normalize input dates from DD-MM-YYYY into YYYY-MM-DD."""
    normalized = set()
    for raw_date in dates_to_scrape:
        try:
            normalized.add(datetime.strptime(raw_date, "%d-%m-%Y").strftime("%Y-%m-%d"))
        except ValueError:
            print(f"[WARN] Invalid target date skipped: {raw_date}")
    return normalized

def dedupe_preserve_order(values):
    """Deduplicate items while keeping insertion order."""
    return list(dict.fromkeys(values))

def extract_sitemap_locs(raw_content):
    """Extract sitemap or article URLs from XML-like content."""
    if not raw_content:
        return []

    loc_matches = re.findall(
        r"<loc>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</loc>",
        raw_content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if loc_matches:
        return dedupe_preserve_order([match.strip() for match in loc_matches if match.strip()])

    fallback_urls = re.findall(r"https://kaltara\.tribunnews\.com/[^\s<>\"]+", raw_content)
    return dedupe_preserve_order([url.rstrip("],)") for url in fallback_urls])

def extract_date_from_url(url):
    """Extract publication date from article URL path."""
    match = ARTICLE_URL_DATE_RE.search(url or "")
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

def get_child_sitemaps(driver=None):
    """Read the root sitemap and keep only relevant child sitemaps."""
    raw_content = fetch_content_with_fallback(
        ROOT_SITEMAP_URL,
        driver=driver,
        retries=1,
        mode="text",
    )
    sitemap_urls = extract_sitemap_locs(raw_content)

    filtered = [
        url for url in sitemap_urls
        if url.endswith(SITEMAP_TYPES)
        and not any(f"/{section}/" in url for section in EXCLUDED_SITEMAP_SECTIONS)
    ]
    print(f"[INFO] Tribun Kaltara child sitemaps found: {len(filtered)}")
    return dedupe_preserve_order(filtered)

def get_article_urls_from_sitemap(sitemap_url, driver=None, visited=None, depth=0):
    """Extract article URLs from a sitemap, including nested sitemap indexes."""
    if visited is None:
        visited = set()

    if sitemap_url in visited:
        return []

    if depth > MAX_SITEMAP_DEPTH:
        print(f"[WARN] Max sitemap depth reached, skipping: {sitemap_url}")
        return []

    visited.add(sitemap_url)

    raw_content = fetch_content_with_fallback(
        sitemap_url,
        driver=driver,
        retries=1,
        mode="text",
    )
    if not raw_content:
        print(f"[WARN] Empty sitemap content skipped: {sitemap_url}")
        return []

    locs = extract_sitemap_locs(raw_content)
    if not locs:
        print(f"[WARN] No loc entries found in sitemap: {sitemap_url}")
        return []

    nested_sitemaps = [url for url in locs if url.endswith(".xml")]
    article_urls = [url for url in locs if not url.endswith(".xml")]

    if nested_sitemaps:
        print(
            f"[INFO] Nested sitemaps discovered: {sitemap_url} -> "
            f"{len(nested_sitemaps)} sitemap(s)"
        )

    for nested_sitemap in nested_sitemaps:
        article_urls.extend(
            get_article_urls_from_sitemap(
                nested_sitemap,
                driver=driver,
                visited=visited,
                depth=depth + 1,
            )
        )

    deduped_urls = dedupe_preserve_order(article_urls)
    print(f"[INFO] URLs extracted from sitemap: {sitemap_url} -> {len(deduped_urls)}")
    return deduped_urls

def discover_candidate_urls(target_dates, driver=None, delay=1):
    """Discover article URLs from sitemap entries and filter them by date."""
    candidate_urls = []
    child_sitemaps = get_child_sitemaps(driver=driver)

    if not child_sitemaps:
        print("[WARN] No child sitemap found for Tribun Kaltara.")
        return []

    for sitemap_url in child_sitemaps:
        article_urls = get_article_urls_from_sitemap(sitemap_url, driver=driver)
        filtered_urls = [
            url for url in article_urls
            if not extract_date_from_url(url) or extract_date_from_url(url) in target_dates
        ]
        candidate_urls.extend(filtered_urls)
        time.sleep(random.uniform(0.2, max(0.2, delay)))

    print(f"[INFO] Tribun Kaltara candidate URLs before article parsing: {len(candidate_urls)}")
    return dedupe_preserve_order(candidate_urls)

def iterate_jsonld_nodes(payload):
    """Flatten JSON-LD payloads into a list of dictionaries."""
    if isinstance(payload, list):
        for item in payload:
            yield from iterate_jsonld_nodes(item)
    elif isinstance(payload, dict):
        if "@graph" in payload:
            yield from iterate_jsonld_nodes(payload["@graph"])
        else:
            yield payload

def get_article_jsonld(soup):
    """Find the JSON-LD node that describes the article."""
    for script in soup.select('script[type="application/ld+json"]'):
        raw_json = script.string or script.get_text(strip=True)
        if not raw_json:
            continue

        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            continue

        for node in iterate_jsonld_nodes(payload):
            node_type = node.get("@type")
            if isinstance(node_type, list):
                type_values = node_type
            else:
                type_values = [node_type]

            if any(value in {"NewsArticle", "Article"} for value in type_values):
                return node

    return None

def clean_title(title):
    """Normalize article title and remove site suffix when present."""
    if not title:
        return None

    cleaned = " ".join(str(title).split())
    for suffix in (" - TribunKaltara.com", " - Tribunnews.com", " | Tribun Kaltara"):
        if cleaned.endswith(suffix):
            return cleaned[:-len(suffix)].strip()
    return cleaned

def normalize_date_value(raw_date):
    """Normalize date strings from metadata into YYYY-MM-DD."""
    if not raw_date:
        return None

    text = " ".join(str(raw_date).split())
    if not text:
        return None

    iso_candidate = (
        text.replace("Z", "+00:00")
        .replace(" WIB", "+07:00")
        .replace(" WITA", "+08:00")
        .replace(" WIT", "+09:00")
    )
    try:
        return datetime.fromisoformat(iso_candidate).strftime("%Y-%m-%d")
    except ValueError:
        pass

    translated = (
        translate_date(text)
        .replace("WIB", "+0700")
        .replace("WITA", "+0800")
        .replace("WIT", "+0900")
    )
    for fmt in (
        "%A, %d %B %Y %H:%M %z",
        "%A, %d %B %Y %H:%M",
        "%A, %d %B %Y",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(translated, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None

def get_meta_content(soup, attr_name, attr_value):
    """Read a meta tag content by a specific attribute."""
    tag = soup.find("meta", attrs={attr_name: attr_value})
    return tag.get("content", "").strip() if tag else None

def get_title_from_soup(soup, article_data):
    """Extract article title from JSON-LD, OpenGraph, or HTML title."""
    if article_data and article_data.get("headline"):
        return clean_title(article_data.get("headline"))

    for attr_name, attr_value in (
        ("property", "og:title"),
        ("name", "title"),
        ("property", "twitter:title"),
    ):
        value = get_meta_content(soup, attr_name, attr_value)
        if value:
            return clean_title(value)

    if soup.title and soup.title.text:
        return clean_title(soup.title.text)

    heading = soup.find("h1")
    return clean_title(heading.get_text(strip=True)) if heading else None

def get_category_from_soup(soup, article_data):
    """Extract article category from metadata or breadcrumb."""
    if article_data:
        category = article_data.get("articleSection")
        if isinstance(category, list):
            category = ", ".join(str(item) for item in category if item)
        if category:
            return str(category).strip()

    for attr_name, attr_value in (
        ("property", "article:section"),
        ("name", "article:section"),
    ):
        value = get_meta_content(soup, attr_name, attr_value)
        if value:
            return value

    for selector in ("ul.breadcrumb li a", "nav a", ".breadcrumb a"):
        values = [
            element.get_text(strip=True)
            for element in soup.select(selector)
            if element.get_text(strip=True)
            and element.get_text(strip=True).lower() not in {"home", "tribunnews"}
        ]
        if values:
            return values[-1]

    return None

def get_published_date(soup, article_data, url):
    """Extract article publication date with URL date as last fallback."""
    if article_data:
        for key in ("datePublished", "dateCreated", "dateModified"):
            normalized = normalize_date_value(article_data.get(key))
            if normalized:
                return normalized

    for attr_name, attr_value in (
        ("property", "article:published_time"),
        ("name", "pubdate"),
        ("itemprop", "datePublished"),
    ):
        normalized = normalize_date_value(get_meta_content(soup, attr_name, attr_value))
        if normalized:
            return normalized

    time_tag = soup.find("time")
    if time_tag:
        normalized = normalize_date_value(time_tag.get("datetime") or time_tag.get_text(strip=True))
        if normalized:
            return normalized

    return extract_date_from_url(url)

def parse_article_page(url, driver=None):
    """Parse article metadata from a Tribunnews article page."""
    raw_html = fetch_content_with_fallback(
        url,
        driver=driver,
        retries=1,
        mode="html",
    )
    if not raw_html:
        return None

    soup = BeautifulSoup(raw_html, "html.parser")
    article_data = get_article_jsonld(soup)

    title = get_title_from_soup(soup, article_data)
    published_date = get_published_date(soup, article_data, url)
    category = get_category_from_soup(soup, article_data)

    if not title or not published_date:
        print(f"[WARN] Failed to parse article metadata: {url}")
        return None

    return {
        "Tagar": category,
        "Judul": title,
        "Tanggal": published_date,
        "Tautan": url,
        "Sumber": SOURCE_NAME,
    }

# Kaltara Tribunnews Scrap Function
def tribun_scrap(dates_to_scrape, delay=1):
    """Scrape Tribun Kaltara news by target dates through sitemap discovery."""
    target_dates = normalize_target_dates(dates_to_scrape)
    if not target_dates:
        return []

    scraped_data = []
    driver = None

    try:
        try:
            driver = build_web_driver()
        except Exception as e:
            print(f"[WARN] Selenium driver unavailable, continuing with requests only: {e}")

        candidate_urls = discover_candidate_urls(target_dates, driver=driver, delay=delay)
        if not candidate_urls:
            print("[INFO] No Tribun Kaltara candidate URLs matched target dates.")
            return []

        for article_url in candidate_urls:
            article = parse_article_page(article_url, driver=driver)
            if article and article["Tanggal"] in target_dates:
                scraped_data.append(article)
            time.sleep(random.uniform(0.2, max(0.2, delay)))
    finally:
        if driver is not None:
            driver.quit()

    return scraped_data
