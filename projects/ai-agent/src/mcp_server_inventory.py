"""SDK-independent opaque cursor contract for a paginated Tool inventory."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass


class InvalidInventoryCursor(ValueError):
    """Cursor is malformed, forged, stale, or outside the current inventory."""


@dataclass(frozen=True)
class InventoryPageWindow:
    start: int
    end: int
    next_cursor: str | None


@dataclass(frozen=True)
class ToolInventoryPaginator:
    """Issue signed cursors bound to one inventory revision."""

    secret: bytes
    page_size: int

    def __post_init__(self) -> None:
        if len(self.secret) < 16:
            raise ValueError("cursor secret must contain at least 16 bytes")
        if self.page_size < 1:
            raise ValueError("page size must be positive")

    def page(
        self,
        *,
        item_count: int,
        revision: str,
        cursor: str | None,
    ) -> InventoryPageWindow:
        if item_count < 0:
            raise ValueError("item count cannot be negative")
        start = 0 if cursor is None else self._decode(cursor, revision)
        if start < 0 or start >= item_count or start % self.page_size != 0:
            raise InvalidInventoryCursor("inventory cursor is outside the current snapshot")

        end = min(start + self.page_size, item_count)
        next_cursor = (
            self._encode(revision, end) if end < item_count else None
        )
        return InventoryPageWindow(start, end, next_cursor)

    def _encode(self, revision: str, offset: int) -> str:
        payload = json.dumps(
            {"revision": revision, "offset": offset},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        signature = hmac.new(self.secret, payload, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(payload + signature).decode("ascii")

    def _decode(self, cursor: str, expected_revision: str) -> int:
        try:
            sealed = base64.b64decode(
                cursor.encode("ascii"),
                altchars=b"-_",
                validate=True,
            )
            if len(sealed) <= hashlib.sha256().digest_size:
                raise ValueError("cursor payload is missing")
            payload = sealed[:-hashlib.sha256().digest_size]
            supplied_signature = sealed[-hashlib.sha256().digest_size:]
            expected_signature = hmac.new(
                self.secret,
                payload,
                hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ValueError("cursor signature mismatch")
            decoded = json.loads(payload)
            if set(decoded) != {"revision", "offset"}:
                raise ValueError("cursor fields mismatch")
            if decoded["revision"] != expected_revision:
                raise ValueError("cursor revision is stale")
            if not isinstance(decoded["offset"], int):
                raise ValueError("cursor offset is invalid")
            return decoded["offset"]
        except (UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise InvalidInventoryCursor("invalid inventory cursor") from exc
