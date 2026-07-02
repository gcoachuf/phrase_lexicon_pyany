"""Run Google Doc sync with throttling."""

import os
from datetime import datetime, timezone

import db
from parser import doc_source, parse_all

SYNC_INTERVAL_MINUTES = int(os.environ.get("SYNC_INTERVAL_MINUTES", "10"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _minutes_since(iso_timestamp: str | None) -> float:
    if not iso_timestamp:
        return float("inf")
    last = datetime.fromisoformat(iso_timestamp)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - last
    return delta.total_seconds() / 60


def should_sync(force: bool = False) -> bool:
    if force:
        return True
    last_sync = db.get_meta("last_sync_at")
    return _minutes_since(last_sync) >= SYNC_INTERVAL_MINUTES


def run_sync(force: bool = False) -> dict:
    if not should_sync(force):
        return {
            "ok": True,
            "synced": False,
            "skipped": True,
            "stats": db.get_stats(),
            "last_sync_at": db.get_meta("last_sync_at"),
        }

    cards = parse_all()
    added, skipped, total = db.import_cards(cards)
    now = _now_iso()
    source = doc_source()
    db.set_meta("last_sync_at", now)
    db.set_meta("last_sync_added", str(added))
    db.set_meta("last_sync_skipped", str(skipped))
    db.set_meta("last_sync_parsed", str(len(cards)))
    db.set_meta("last_sync_doc_tab", source["doc_tab"])

    return {
        "ok": True,
        "synced": True,
        "skipped": False,
        "parsed": len(cards),
        "added": added,
        "skipped_duplicates": skipped,
        "total": total,
        "stats": db.get_stats(),
        "last_sync_at": now,
        "doc_source": source,
    }
