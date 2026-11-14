"""UTC in the DB and API, KST only in export files (spec 9)."""

from datetime import UTC, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def as_utc(dt: datetime) -> datetime:
    # SQLite returns naive datetimes; everything we store is UTC.
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def iso_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return as_utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")
