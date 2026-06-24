from datetime import UTC, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9), name="KST")


def utc_now() -> datetime:
    return datetime.now(UTC)


def korea_now() -> datetime:
    return datetime.now(KST)
