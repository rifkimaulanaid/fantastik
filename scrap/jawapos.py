"""Shared read-only GraphQL adapter for Prokal and Radar Tarakan."""
from dataclasses import dataclass
from datetime import datetime
import json
import re
from urllib.parse import quote, urlsplit

from bs4 import BeautifulSoup

from helper.content_cache import get_content, put_content
from helper.helper_function import decode_response_text, is_blocked_response, normalize_article_text
from helper.http_client import UnsafeURL, request, validate_url
from helper.models import Budget, SourceResult, WorkStopped, validate_dates
from helper.presentation import status_label

API_URL = "https://api-jjmn.jawapos.com/api-jp-graphql/"
QUERY = """
query GET_SEARCH_ARTICLE($publisherId: ID!, $dateStart: DateTime, $dateEnd: DateTime,
                        $page: Int = 1, $perPage: Int = 20) {
  searchArticle(filter: {publisherId: $publisherId, dateStart: $dateStart, dateEnd: $dateEnd},
                first: $perPage, page: $page) {
    paginatorInfo { hasMorePages }
    data { id article_id title date: published_at category { name slug } }
  }
}
""".strip()


class SchemaError(ValueError):
    code = "INVALID_SCHEMA"


@dataclass(frozen=True)
class Publisher:
    name: str
    publisher_id: str
    base_url: str

    @property
    def hosts(self):
        host = urlsplit(self.base_url).hostname
        return frozenset({host, "prokal.co"} if host == "www.prokal.co" else {host})


PROKAL = Publisher("Prokal", "8", "https://www.prokal.co")
RADAR = Publisher("Radar Tarakan", "10", "https://radartarakan.jawapos.com")


def slugify_title(title):
    collapsed = "-".join(str(title or "").lower().strip().split())
    return re.sub("-+", "-", "".join(c for c in collapsed if c.isalnum() or c == "-")).strip("-")


def build_article_url(article, publisher):
    category = article.get("category")
    if not isinstance(category, dict):
        raise SchemaError("Kategori artikel tidak valid.")
    category_slug = category.get("slug") or "uncategorized"
    article_id = str(article.get("article_id") or "")
    if (not isinstance(category_slug, str) or len(category_slug) > 200
            or not re.fullmatch(r"[\w-]+", category_slug)
            or not re.fullmatch(r"[0-9]{1,64}", article_id)):
        raise SchemaError("ID atau slug artikel tidak valid.")
    title = article.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 2000:
        raise SchemaError("Judul artikel kosong atau tidak valid.")
    return validate_url(
        f"{publisher.base_url}/{quote(category_slug)}/{article_id}/{quote(slugify_title(title))}",
        publisher.hosts,
    )


def fetch_page(publisher, start_date, end_date, page=1, per_page=20, budget=None):
    response = request(
        "POST", API_URL, allowed_hosts={"api-jjmn.jawapos.com"},
        json={"operationName": "GET_SEARCH_ARTICLE", "query": QUERY, "variables": {
            "publisherId": publisher.publisher_id, "page": page, "perPage": per_page,
            "dateStart": f"{start_date:%Y-%m-%d} 00:00:00",
            "dateEnd": f"{end_date:%Y-%m-%d} 23:59:59",
        }},
        headers={"Origin": publisher.base_url, "Referer": f"{publisher.base_url}/indeks-berita"},
        deadline=budget.deadline if budget else None, check=budget.check if budget else None,
    )
    try:
        return response.json()
    except (ValueError, TypeError) as error:
        raise SchemaError("Respons API bukan JSON valid.") from error


def parse_page(payload):
    if not isinstance(payload, dict) or payload.get("errors"):
        raise SchemaError("API mengembalikan error atau respons tidak valid.")
    data = payload.get("data")
    search = data.get("searchArticle") if isinstance(data, dict) else None
    if not isinstance(search, dict) or not isinstance(search.get("data"), list):
        raise SchemaError("Struktur daftar artikel berubah atau tidak tersedia.")
    paginator = search.get("paginatorInfo")
    if not isinstance(paginator, dict) or type(paginator.get("hasMorePages")) is not bool:
        raise SchemaError("Informasi halaman berikutnya tidak bisa dibaca.")
    articles, more = search["data"], paginator["hasMorePages"]
    if not articles and more:
        raise SchemaError("API memberi halaman kosong tetapi masih menyatakan ada halaman berikutnya.")
    return articles, more


def parse_content(html):
    if is_blocked_response(html):
        raise SchemaError("Halaman artikel menolak akses.")
    soup = BeautifulSoup(html, "html.parser")
    app = soup.find("div", id="app")
    if not app or not app.get("data-page"):
        raise SchemaError("Data artikel tidak ditemukan pada halaman detail.")
    try:
        # BeautifulSoup already decoded the HTML attribute exactly once.
        payload = json.loads(app["data-page"])
    except (ValueError, TypeError) as error:
        raise SchemaError("JSON artikel tidak valid.") from error
    props = payload.get("props") if isinstance(payload, dict) else None
    article = props.get("article") if isinstance(props, dict) else None
    content = article.get("content") if isinstance(article, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise SchemaError("Isi artikel kosong atau tidak valid.")
    body = BeautifulSoup(content, "html.parser")
    for tag in body.find_all(["figure", "figcaption", "script", "style"]):
        tag.decompose()
    paragraphs = [p.get_text(" ", strip=True) for p in body.find_all("p")]
    text = normalize_article_text(paragraphs or body.get_text(" ", strip=True))
    if not text:
        raise SchemaError("Isi artikel tidak dapat dibaca.")
    return text


def extract_content(url, publisher, budget=None):
    url = validate_url(url, publisher.hosts)
    key = ("jawapos-v3", publisher.name, url)
    if budget:
        budget.check()
    cached = get_content(key)
    if cached is not None:
        return cached
    response = request(
        "GET", url, allowed_hosts=publisher.hosts,
        headers={"Referer": f"{publisher.base_url}/indeks-berita"},
        deadline=budget.deadline if budget else None, check=budget.check if budget else None,
    )
    text = parse_content(decode_response_text(response))
    put_content(key, text)
    return text


def scrape(publisher, start_date, end_date, progress_callback=None, *, budget=None, checkpoint=None):
    validate_dates(start_date, end_date)
    budget = budget or Budget()
    result = SourceResult(publisher.name)
    seen, page_signatures = set(), set()
    current = 1
    try:
        while True:
            budget.page(current)
            if progress_callback:
                progress_callback(min(0.1 + current * 0.02, 0.9), f"Memuat halaman {current}.")
            articles, more = parse_page(fetch_page(publisher, start_date, end_date, page=current, budget=budget))
            signature = tuple(str(item.get("article_id") or item.get("id")) if isinstance(item, dict)
                              else repr(item) for item in articles)
            if signature and signature in page_signatures:
                raise WorkStopped("REPEATED_PAGE", "Sumber mengirim halaman yang sama lagi. Proses dihentikan.")
            page_signatures.add(signature)
            result.pages = current
            new_ids = 0
            for item in articles:
                budget.check()
                result.found += 1
                identity = str(item.get("article_id") or "") if isinstance(item, dict) else ""
                if identity and identity in seen:
                    result.duplicates += 1
                    continue
                budget.article(result.found - 1)
                try:
                    if not isinstance(item, dict):
                        raise SchemaError("Entri artikel tidak berbentuk objek.")
                    url = build_article_url(item, publisher)
                    name = item["category"].get("name")
                    if name is not None and (not isinstance(name, str) or len(name) > 200):
                        raise SchemaError("Nama kategori tidak valid.")
                    published = datetime.strptime(item["date"], "%Y-%m-%d %H:%M:%S").date()
                except (ValueError, TypeError, KeyError, UnsafeURL) as error:
                    result.issue("INVALID_ARTICLE", error, stage="metadata", article_id=identity)
                    continue
                seen.add(identity)
                new_ids += 1
                if not start_date <= published <= end_date:
                    result.issue("OUT_OF_RANGE", "Artikel API berada di luar tanggal yang diminta.",
                                 stage="metadata", article_id=identity)
                    continue
                record = {"ID Artikel": identity, "Tagar": (name or "Tanpa kategori").strip(),
                          "Judul": " ".join(item["title"].split()), "Tanggal": published.isoformat(),
                          "Tautan": url, "Sumber": publisher.name, "Isi": None, "Status Isi": "gagal"}
                try:
                    content = extract_content(url, publisher, budget)
                    if not content:
                        raise SchemaError("Isi artikel kosong.")
                    budget.add_text(content)
                    record["Isi"] = content
                    record["Status Isi"] = "lengkap"
                except WorkStopped:
                    result.rows.append(record)
                    raise
                except Exception as error:
                    result.issue(getattr(error, "code", "CONTENT_FAILED"), error, stage="content", article_id=identity)
                result.rows.append(record)
                if checkpoint:
                    checkpoint(result)
            if checkpoint:
                checkpoint(result)
            if not more:
                result.coverage_complete = True
                result.stop_reason = "COMPLETE"
                break
            if not new_ids:
                raise WorkStopped("NO_PROGRESS", "Tidak ada artikel baru pada halaman lanjutan.")
            current += 1
    except Exception as error:
        result.stop_reason = getattr(error, "code", "SOURCE_FAILED")
        result.issue(result.stop_reason, error, stage="pagination")
    if checkpoint:
        checkpoint(result)
    if progress_callback:
        progress_callback(1.0, f"Selesai: {len(result.rows)} berita ({status_label(result.status).lower()}).")
    return result
