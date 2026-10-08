"""Strict normalization of the pinned library's cloud media contract."""

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from math import isfinite
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid5

from porchlight.api.contracts import ApiError
from porchlight.providers.base import ClipReference


def retry_delay(value: str | None) -> float:
    try:
        seconds = float(value or "120")
        return max(120, seconds) if isfinite(seconds) else 120
    except ValueError:
        try:
            return max(
                120, (parsedate_to_datetime(value or "") - datetime.now(UTC)).total_seconds()
            )
        except (ValueError, TypeError):
            return 120


def media_path(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ApiError(
            503, "UNSUPPORTED_MEDIA_LOCATOR", "Blink returned an unsupported media link."
        )
    url = urlsplit(value)
    if (
        url.scheme
        or url.netloc
        or url.query
        or url.fragment
        or not value.startswith("/api/")
        or "\\" in value
        or any(part in {".", ".."} for part in value.split("/"))
        or "%" in value
        or any(ord(char) < 32 for char in value)
    ):
        raise ApiError(
            503, "UNSUPPORTED_MEDIA_LOCATOR", "Blink returned an unsupported media link."
        )
    return value


def normalize_page(
    body: Any, namespace: str, account_id: str, camera_ids: dict[str, list[str]]
) -> list[ClipReference]:
    if not isinstance(body, dict) or not isinstance(body.get("media"), list):
        raise ApiError(
            503, "RECORDING_LIST_UNAVAILABLE", "Blink's cloud recording list is unavailable."
        )
    result = []
    for item in body["media"]:
        if not isinstance(item, dict) or item.get("id") is None:
            raise ApiError(
                503, "RECORDING_CONTRACT_CHANGED", "Blink returned incomplete recording metadata."
            )
        # changed-media can include still thumbnails as well as clips.
        kind = item.get("media_type", item.get("type"))
        if kind in {"thumbnail", "image", "snapshot"}:
            continue
        deleted = item.get("deleted") is True
        raw_time = str(item.get("created_at", ""))
        captured = None
        try:
            parsed = datetime.fromisoformat(raw_time)
            if parsed.tzinfo is not None:
                captured = parsed.astimezone(UTC).isoformat()
        except ValueError:
            pass
        matches = camera_ids.get(str(item.get("device_id", "")), [])
        result.append(
            ClipReference(
                source_key="blink_cloud:"
                + str(uuid5(UUID(namespace), f"cloud:{account_id}:{item['id']}")),
                camera_id=matches[0] if len(matches) == 1 else None,
                captured_at=captured,
                raw_timestamp=raw_time,
                media_path="" if deleted else media_path(item.get("media")),
                deleted=deleted,
            )
        )
    return result
