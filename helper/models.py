"""Shared source results and cooperative work limits; no Streamlit dependency."""

from dataclasses import asdict, dataclass, field
from datetime import date
import time

MAX_DATE_DAYS = 31


class WorkStopped(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def validate_dates(start_date, end_date):
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise ValueError("Tanggal tidak valid.")
    if start_date > end_date:
        raise ValueError("Tanggal awal tidak boleh lebih dari tanggal akhir.")
    if (end_date - start_date).days >= MAX_DATE_DAYS:
        raise ValueError(f"Rentang tanggal maksimal {MAX_DATE_DAYS} hari per proses.")


@dataclass
class Budget:
    max_pages: int = 200
    max_articles: int = 1000
    seconds: float = 180
    max_characters: int = 8_000_000
    characters: int = 0
    cancel: object = None
    started: float = field(default_factory=time.monotonic)

    @property
    def deadline(self):
        return self.started + self.seconds

    def check(self):
        if self.cancel is not None and self.cancel.is_set():
            raise WorkStopped("CANCELLED", "Proses dibatalkan; hasil yang telah diperoleh dipertahankan.")
        if time.monotonic() >= self.deadline:
            raise WorkStopped("TIME_LIMIT", "Batas durasi sumber tercapai.")

    def page(self, number):
        self.check()
        if number > self.max_pages:
            raise WorkStopped("PAGE_LIMIT", "Batas halaman tercapai sebelum pengumpulan lengkap.")

    def article(self, count):
        self.check()
        if count >= self.max_articles:
            raise WorkStopped("ARTICLE_LIMIT", "Batas artikel tercapai sebelum pengumpulan lengkap.")

    def add_text(self, text):
        self.check()
        self.characters += len(text or "")
        if self.characters > self.max_characters:
            raise WorkStopped("TEXT_LIMIT", "Batas total ukuran isi artikel tercapai.")


@dataclass
class SourceResult:
    source: str
    rows: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    pages: int = 0
    found: int = 0
    duplicates: int = 0
    coverage_complete: bool = False
    stop_reason: str = "IN_PROGRESS"

    def issue(self, code, message, *, stage, article_id=""):
        self.issues.append(dict(code=code, message=str(message)[:500], stage=stage,
                                article_id=str(article_id)))

    @property
    def status(self):
        if self.coverage_complete and not self.issues:
            return "success"
        return "partial" if self.rows else "failed"

    def report(self):
        return dict(source=self.source, status=self.status, count=len(self.rows),
                    found=self.found, missing_body=sum(not row.get("Isi") for row in self.rows),
                    pages=self.pages, duplicates=self.duplicates,
                    coverage_complete=self.coverage_complete, stop_reason=self.stop_reason,
                    message=self.issues[-1]["message"] if self.issues else None,
                    issues=list(self.issues))

    def to_dict(self):
        return asdict(self)
