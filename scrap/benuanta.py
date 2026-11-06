"""Benuanta HTML adapter with bounded scanning and explicit partial results."""
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from helper.content_cache import get_content, put_content
from helper.helper_function import decode_response_text, fetch_page, is_blocked_response, normalize_article_text, translate_date
from helper.http_client import validate_url
from helper.models import Budget, SourceResult, WorkStopped, validate_dates

HOSTS = frozenset({"benuanta.co.id", "www.benuanta.co.id"})
CONTENT_STOP_PREFIXES = ("Reporter:", "Editor:", "Baca juga:", "BACA JUGA:")


def extract_benuanta_content(url, budget=None):
    url = validate_url(url, HOSTS)
    if budget:
        budget.check()
    key = ("benuanta-v3", url)
    cached = get_content(key)
    if cached is not None:
        return cached
    response = fetch_page(url, allowed_hosts=HOSTS,
                          deadline=budget.deadline if budget else None,
                          check=budget.check if budget else None)
    html = decode_response_text(response)
    if is_blocked_response(html):
        raise ValueError("Halaman artikel menolak akses.")
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one(".entry-content")
    if not node:
        raise ValueError("Selector isi artikel tidak ditemukan.")
    paragraphs = []
    for paragraph in node.find_all("p"):
        text = " ".join(paragraph.get_text(" ", strip=True).split())
        if text.startswith(CONTENT_STOP_PREFIXES):
            break
        if text:
            paragraphs.append(text)
    content = normalize_article_text(paragraphs)
    if not content:
        raise ValueError("Isi artikel kosong.")
    put_content(key, content)
    return content


def benuanta_scrap(start_date, end_date, max_page=200, progress_callback=None, *, budget=None, checkpoint=None):
    validate_dates(start_date, end_date)
    budget = budget or Budget(max_pages=max_page)
    result = SourceResult("Benuanta")
    seen, signatures = set(), set()
    current = 1
    try:
        while True:
            budget.page(current)
            if progress_callback:
                progress_callback(min(0.1 + current * 0.02, 0.9), f"Memindai halaman {current} Benuanta.")
            index_url = f"https://benuanta.co.id/index.php/page/{current}/?s"
            response = fetch_page(index_url, allowed_hosts=HOSTS, deadline=budget.deadline, check=budget.check)
            html = decode_response_text(response)
            if is_blocked_response(html):
                raise ValueError("Indeks menolak akses.")
            soup = BeautifulSoup(html, "html.parser")
            articles = soup.find_all("article")
            if not articles:
                if soup.select_one("section.no-results, .no-results.not-found"):
                    result.coverage_complete = True
                    result.stop_reason = "COMPLETE"
                    break
                raise ValueError("Struktur indeks berubah atau halaman bukan indeks berita.")
            signature = tuple((a.find("a", href=True).get("href") if a.find("a", href=True) else a.get_text())
                              for a in articles)
            if signature in signatures:
                raise WorkStopped("REPEATED_PAGE", "Indeks mengulang halaman yang sama.")
            signatures.add(signature)
            result.pages = current
            dates = []
            for article in articles:
                budget.check()
                result.found += 1
                budget.article(result.found - 1)
                try:
                    time_tag = article.find("time")
                    if not time_tag:
                        raise ValueError("Tanggal artikel tidak ditemukan.")
                    published = datetime.strptime(translate_date(time_tag.get_text(strip=True)), "%d %B %Y").date()
                    dates.append(published)
                    if not start_date <= published <= end_date:
                        continue
                    heading = article.find("h2")
                    link = heading.find("a", href=True) if heading else None
                    link = link if link is not None else article.find("a", href=True)
                    if not heading or not heading.get_text(strip=True) or not link:
                        raise ValueError("Judul atau tautan artikel tidak ditemukan.")
                    url = validate_url(urljoin(index_url, link["href"]), HOSTS)
                    if url in seen:
                        result.duplicates += 1
                        continue
                    seen.add(url)
                    category = article.find("span", class_="gmr-meta-topic")
                    if len(heading.get_text()) > 2000 or (category and len(category.get_text()) > 200):
                        raise ValueError("Metadata artikel melebihi batas ukuran.")
                    record = {"ID Artikel": url, "Judul": heading.get_text(" ", strip=True),
                              "Tagar": category.get_text(" ", strip=True) if category else "Tanpa kategori",
                              "Tanggal": published.isoformat(), "Sumber": "Benuanta", "Tautan": url,
                              "Isi": None, "Status Isi": "gagal"}
                except Exception as error:
                    result.issue(getattr(error, "code", "INVALID_ARTICLE"), error, stage="metadata")
                    continue
                try:
                    content = extract_benuanta_content(url, budget)
                    if not content:
                        raise ValueError("Isi artikel kosong.")
                    budget.add_text(content)
                    record["Isi"] = content
                    record["Status Isi"] = "lengkap"
                except WorkStopped:
                    result.rows.append(record)
                    raise
                except Exception as error:
                    result.issue(getattr(error, "code", "CONTENT_FAILED"), error, stage="content", article_id=url)
                result.rows.append(record)
                if checkpoint:
                    checkpoint(result)
            if checkpoint:
                checkpoint(result)
            # Do not stop for one old pinned article mixed with current articles.
            if dates and len(dates) == len(articles) and max(dates) < start_date:
                result.coverage_complete = True
                result.stop_reason = "COMPLETE"
                break
            if not soup.select_one("a.next.page-numbers"):
                result.coverage_complete = True
                result.stop_reason = "COMPLETE"
                break
            current += 1
    except Exception as error:
        result.stop_reason = getattr(error, "code", "SOURCE_FAILED")
        result.issue(result.stop_reason, error, stage="pagination")
    if checkpoint:
        checkpoint(result)
    if progress_callback:
        progress_callback(1.0, f"Selesai ({result.status}): {len(result.rows)} artikel.")
    return result
