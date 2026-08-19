import hashlib
import json
import re
from typing import Any

from app.core.errors import ValidationError

IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


def validate_idempotency_key(value: str | None, *, required: bool = False) -> str | None:
    if value is None or not value.strip():
        if required:
            raise ValidationError("Idempotency-Key is required for write requests")
        return None
    normalized = value.strip()
    if not IDEMPOTENCY_KEY.fullmatch(normalized):
        raise ValidationError("Idempotency-Key must be 8-128 safe ASCII characters")
    return normalized


def request_fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
