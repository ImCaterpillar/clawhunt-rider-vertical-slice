# -*- coding: utf-8 -*-
"""Runnable local vertical slice for rider recruitment tasks 1-5.

This is an in-memory acceptance demo, not a production service or real PII vault.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

SLOTS = ("name", "birth_ym", "area", "job_type", "has_ebike", "start_date", "experience")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d[- ]?\d{4}[- ]?\d{4}(?!\d)")


def mask_and_tokenize(text: str, secret: bytes) -> tuple[str, dict[str, str]]:
    """Replace Chinese mobile numbers before downstream/model processing."""
    mapping: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        raw = re.sub(r"\D", "", match.group(0))
        number = raw[-11:]
        token = "〔手机号_" + hmac.new(secret, number.encode(), hashlib.sha256).hexdigest()[:12] + "〕"
        mapping[token] = number
        return token

    return PHONE_RE.sub(replace, text), mapping


@dataclass
class Session:
    consent_version: Optional[str] = None
    slots: Dict[str, str] = field(default_factory=dict)
    status: str = "awaiting_consent"
    pii_tokens: Dict[str, str] = field(default_factory=dict)

    def give_consent(self, version: str) -> None:
        if not version.strip():
            raise ValueError("CONSENT_VERSION_REQUIRED")
        self.consent_version = version
        self.status = "collecting"

    def accept_message(self, text: str, secret: bytes) -> int:
        if self.status != "collecting":
            raise PermissionError("CONSENT_REQUIRED")
        safe, tokens = mask_and_tokenize(text, secret)
        self.pii_tokens.update(tokens)
        # Explicit slot=value demo grammar; never forwards raw input to a model.
        for slot in SLOTS:
            m = re.search(r"(?:^|\s)" + re.escape(slot) + r"=([^\s;]+)", safe)
            if m:
                self.slots[slot] = m.group(1)
        if self.slots.get("birth_ym", "").startswith(("2008", "2009", "2010")):
            self.status = "end_minor"
            self.slots.clear()
        elif len(self.slots) == len(SLOTS):
            self.status = "complete"
        return len(self.slots)

    @property
    def progress(self) -> str:
        return f"{len(self.slots)}/{len(SLOTS)}"

    def revoke(self) -> None:
        self.slots.clear()
        self.pii_tokens.clear()
        self.consent_version = None
        self.status = "deleted"


class Capacity:
    """Thread-safe in-memory atomic slot allocation for concurrency demo."""
    def __init__(self, seats: int):
        self.remaining = seats
        self._lock = threading.Lock()
        self._booked: set[str] = set()

    def book(self, candidate_id: str) -> bool:
        with self._lock:
            if candidate_id in self._booked or self.remaining <= 0:
                return False
            self.remaining -= 1
            self._booked.add(candidate_id)
            return True


class AuditChain:
    def __init__(self):
        self.rows: list[dict] = []

    def append(self, event: str, subject_token: str) -> None:
        prev = self.rows[-1]["hash"] if self.rows else "0" * 64
        row = {"seq": len(self.rows) + 1, "at": datetime.now(timezone.utc).isoformat(),
               "event": event, "subject_token": subject_token, "prev": prev}
        row["hash"] = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
        self.rows.append(row)

    def verify(self) -> bool:
        prev = "0" * 64
        for i, row in enumerate(self.rows, 1):
            body = {k: v for k, v in row.items() if k != "hash"}
            digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
            if row["seq"] != i or row["prev"] != prev or not hmac.compare_digest(digest, row["hash"]):
                return False
            prev = row["hash"]
        return True


def aggregate(events: list[dict]) -> dict:
    """Return aggregate-only metrics; source rows never pass through to output."""
    total = len(events)
    complete = sum(bool(e.get("complete")) for e in events)
    booked = sum(bool(e.get("booked")) for e in events)
    return {"total": total, "complete": complete, "booked": booked,
            "completion_rate": complete / total if total else 0.0}
