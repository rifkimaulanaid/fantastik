import json
from datetime import datetime
from html import unescape

from bs4 import BeautifulSoup
from helper.helper_function import SESSION, decode_response_text, normalize_article_text

PROKAL_GRAPHQL_URL = "https://api-jjmn.jawapos.com/api-jp-graphql/"
PROKAL_PUBLISHER_ID = "8"
PROKAL_QUERY = """
query GET_SEARCH_ARTICLE(
    $keyword: String,
    $categoryId: ID,
    $dateStart: DateTime,
    $dateEnd: DateTime,
    $publisherId: ID!,
    $page: Int = 1,
    $perPage: Int = 10
) {
    searchArticle(
        filter: {
            keyword: $keyword,
            categoryId: $categoryId,
            dateStart: $dateStart,
            dateEnd: $dateEnd,
            publisherId: $publisherId
        },
        first: $perPage,
        page: $page
    ) {
        paginatorInfo {
            hasMorePages
        }
        data {
            id
            article_id
            title
            slug
            description
            image: cover
            date: published_at
            category {
                id
                name
                slug
            }
        }
    }
}
""".strip()


def slugify_title(title):
    """Build a URL-safe slug using the same rules as the Prokal frontend helper."""
    normalized = str(title or "").lower().strip()
    collapsed = "-".join(normalized.split())
    alphanumeric = "".join(
        char for char in collapsed
        if char.isalnum() or char == "-"
    )

    while "--" in alphanumeric:
        alphanumeric = alphanumeric.replace("--", "-")

    return alphanumeric.strip("-")


def build_article_url(article):
    """Construct article URL from category slug, article id, and title."""
    category = article.get("category") or {}
    category_slug = (
        category.get("slug")
        or article.get("category_slug")
        or "uncategorized"
    )
    article_id = str(article.get("article_id") or "#")
    title_slug = slugify_title(article.get("title"))
    return f"https://www.prokal.co/{category_slug}/{article_id}/{title_slug}"


def fetch_prokal_page(start_date, end_date, page=1, per_page=20):
    """Fetch one Prokal index page through its GraphQL API."""
    payload = {
        "operationName": "GET_SEARCH_ARTICLE",
        "query": PROKAL_QUERY,
        "variables": {
            "publisherId": PROKAL_PUBLISHER_ID,
            "page": page,
            "perPage": per_page,
            "dateStart": f"{start_date.strftime('%Y-%m-%d')} 00:00:00",
            "dateEnd": f"{end_date.strftime('%Y-%m-%d')} 23:59:59",
            "categoryId": None,
            "keyword": None,
        },
    }

    response = SESSION.post(
        PROKAL_GRAPHQL_URL,
        json=payload,
        timeout=20,
        headers={
            "Content-Type": "application/json",
            "Origin": "https://www.prokal.co",
            "Referer": "https://www.prokal.co/indeks-berita",
        },
    )
    response.raise_for_status()
    return response.json()


def extract_prokal_content(url):
    """Fetch and normalize article body text from a Prokal detail page."""
    try:
        response = SESSION.get(
            url,
            timeout=20,
            headers={
                "Referer": "https://www.prokal.co/indeks-berita",
            },
        )
        response.raise_for_status()
    except Exception as e:
        print(f"[WARN] Gagal mengambil isi Prokal: {url} -> {e}")
        return None

    soup = BeautifulSoup(decode_response_text(response), "html.parser")
    app_node = soup.find("div", id="app")
    if not app_node or not app_node.get("data-page"):
        return None

    payload = json.loads(unescape(app_node["data-page"]))
    article = payload.get("props", {}).get("article", {})
    content_html = article.get("content")
    if not content_html:
        return None

    content_soup = BeautifulSoup(content_html, "html.parser")
    for tag in content_soup.find_all(["figure", "figcaption", "script", "style"]):
        tag.decompose()

    paragraphs = []
    for paragraph in content_soup.find_all("p"):
        text = " ".join(paragraph.get_text(" ", strip=True).split())
        if text:
            paragraphs.append(text)

    if not paragraphs:
        return normalize_article_text(content_soup.get_text(" ", strip=True))

    return normalize_article_text(paragraphs)


def prokal_scrap(start_date, end_date, progress_callback=None):
    """Scrape Prokal via the GraphQL endpoint used by the current frontend."""
    scraped_data = []
    current_page = 1

    while True:
        if progress_callback:
            page_progress = min(0.08 + ((current_page - 1) * 0.18), 0.82)
            progress_callback(
                page_progress,
                f"Memuat halaman API {current_page} Prokal.",
            )

        try:
            payload = fetch_prokal_page(start_date, end_date, page=current_page)
        except Exception as e:
            raise RuntimeError(f"Gagal mengambil data Prokal dari API: {e}") from e

        if payload.get("errors"):
            raise RuntimeError(f"GraphQL Prokal mengembalikan error: {payload['errors']}")

        search_article = payload.get("data", {}).get("searchArticle", {})
        articles = search_article.get("data", [])
        if not articles:
            print("Tidak ada artikel ditemukan.")
            break

        total_articles = len(articles)
        for article_index, article in enumerate(articles, start=1):
            raw_date = article.get("date")
            try:
                article_date = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError):
                print(f"Could not parse date: {raw_date}")
                continue

            category = article.get("category") or {}
            article_url = build_article_url(article)
            scraped_data.append({
                "Tagar": category.get("name", "").strip(),
                "Judul": str(article.get("title", "")).strip().replace('\xa0', ' '),
                "Tanggal": article_date.strftime("%Y-%m-%d"),
                "Tautan": article_url,
                "Sumber": "Prokal",
                "Isi": extract_prokal_content(article_url),
            })

            if progress_callback and (article_index == total_articles or article_index % 5 == 0):
                article_progress = min(
                    0.12 + ((current_page - 1) * 0.18) + ((article_index / total_articles) * 0.12),
                    0.94,
                )
                progress_callback(
                    article_progress,
                    f"{len(scraped_data)} berita Prokal sudah terkumpul.",
                )

        has_more_pages = search_article.get("paginatorInfo", {}).get("hasMorePages")
        if not has_more_pages:
            break

        current_page += 1

    if progress_callback:
        progress_callback(1.0, f"Selesai. {len(scraped_data)} berita Prokal terkumpul.")

    return scraped_data
