"""Orchestrate source adapters without UI state or source-wide data loss."""
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
import time

from helper.data import enrich_scraped_data
from helper.models import Budget, SourceResult, validate_dates
from scrap.benuanta import benuanta_scrap
from scrap.prokal import prokal_scrap
from scrap.radartarakan import radar_scrap

ACTIVE_SOURCES = {"Benuanta": benuanta_scrap, "Prokal": prokal_scrap, "Radar Tarakan": radar_scrap}
PARSER_VERSION = "3"


def scrape_news(start_date, end_date, selected_sources, *, progress=None, checkpoint=None, cancel=None,
                run_id=None, adapters=None, budget_factory=None):
    validate_dates(start_date, end_date)
    adapters = ACTIVE_SOURCES if adapters is None else adapters
    if not selected_sources or len(selected_sources) != len(set(selected_sources)):
        raise ValueError("Pilih sumber yang valid tanpa duplikasi.")
    if any(source not in adapters for source in selected_sources):
        raise ValueError("Sumber tidak diizinkan.")
    metadata = dict(run_id=run_id or uuid4().hex, parser_version=PARSER_VERSION,
                    requested_start=start_date.isoformat(), requested_end=end_date.isoformat(),
                    requested_sources=list(selected_sources), timezone="Asia/Makassar",
                    started_at=datetime.now(ZoneInfo("Asia/Makassar")).isoformat(), state="running")
    output = dict(data=[], reports=[], metadata=metadata)
    completed = []
    last_checkpoint = 0.0

    for index, source in enumerate(selected_sources):
        def source_progress(fraction, note):
            if progress:
                progress((index + max(0, min(fraction, 1))) / len(selected_sources), f"{source}: {note}")

        def source_checkpoint(result):
            nonlocal last_checkpoint
            now = time.monotonic()
            if result.stop_reason == "IN_PROGRESS" and now - last_checkpoint < 0.5:
                return
            last_checkpoint = now
            output["data"] = enrich_scraped_data(completed + result.rows)
            output["reports"] = output["reports"][:index] + [result.report()]
            if checkpoint:
                checkpoint(output)

        budget = budget_factory() if budget_factory else Budget(cancel=cancel)
        partial = SourceResult(source)

        def keep_checkpoint(result):
            nonlocal partial
            partial = result
            source_checkpoint(result)

        try:
            budget.check()
            result = adapters[source](start_date, end_date, progress_callback=source_progress,
                                      budget=budget, checkpoint=keep_checkpoint)
            if not isinstance(result, SourceResult):
                raise TypeError("Adapter harus mengembalikan SourceResult.")
        except Exception as error:
            result = partial
            result.stop_reason = getattr(error, "code", "SOURCE_FAILED")
            result.issue(result.stop_reason, error, stage="source")
        source_checkpoint(result)
        completed.extend(result.rows)

    output["data"] = enrich_scraped_data(sorted(completed, key=lambda r: (r.get("Tanggal", ""), r.get("Judul", "")), reverse=True))
    metadata["finished_at"] = datetime.now(ZoneInfo("Asia/Makassar")).isoformat()
    metadata["state"] = "complete" if all(r["status"] == "success" for r in output["reports"]) else "incomplete"
    if checkpoint:
        checkpoint(output)
    return output
