from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Iterable

from pypdf import PdfReader


@dataclass(frozen=True)
class Message:
    id: str
    sender: str
    text: str
    timestamp: str | None = None


# Handles common WhatsApp exports such as:
# 12/10/26, 10:15 am - Alice: Message
# [12/10/2026, 10:15:00 AM] Alice: Message
_TIMESTAMP_RE = re.compile(
    r"^\[?(?P<ts>\d{1,2}[/-]\d{1,2}[/-]\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)\]?\s*(?:[-–]\s*)?(?P<body>.*)$"
)
_SENDER_RE = re.compile(r"^(?P<sender>[^:]{1,80}):\s*(?P<text>.*)$")


def extract_pdf_text(data: bytes) -> str:
    """Extract text from a digital PDF. OCR/scanned PDFs are intentionally unsupported."""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:  # pypdf errors vary by input
        raise ValueError(f"Couldn't read this PDF: {exc}") from exc
    text = "\n\n".join(page for page in pages if page)
    if not text.strip():
        raise ValueError("This PDF has no selectable text. Scanned/image-only PDFs aren't supported in this MVP; paste the quote text instead.")
    return text


def parse_messages(raw: str, max_messages: int = 120) -> list[Message]:
    """Parse WhatsApp TXT exports and pasted `Sender: message` transcripts.

    Multiline WhatsApp messages are joined to the preceding message. Unrecognized
    non-empty lines are retained as messages so evidence isn't silently dropped.
    """
    records: list[dict[str, str | None]] = []
    for raw_line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        stamp = _TIMESTAMP_RE.match(line)
        if stamp:
            body = stamp.group("body").strip()
            sender_match = _SENDER_RE.match(body)
            if sender_match:
                records.append({
                    "timestamp": stamp.group("ts").strip(),
                    "sender": sender_match.group("sender").strip(),
                    "text": sender_match.group("text").strip(),
                })
            else:
                # System event (e.g. "Messages and calls are end-to-end encrypted")
                # or malformed export line. Keep as evidence, but don't invent a sender.
                records.append({"timestamp": stamp.group("ts").strip(), "sender": "System/Unknown", "text": body})
            continue

        sender_match = _SENDER_RE.match(line)
        if sender_match:
            records.append({"timestamp": None, "sender": sender_match.group("sender").strip(), "text": sender_match.group("text").strip()})
        elif records and records[-1].get("sender") != "Unknown":
            # Preserve wrapped lines belonging to a parsed/identified message.
            existing = records[-1]["text"] or ""
            records[-1]["text"] = f"{existing}\n{line}".strip()
        else:
            # A free-form line with no known preceding sender remains its own message.
            records.append({"timestamp": None, "sender": "Unknown", "text": line})

    # Ignore empty export boilerplate where possible, and cap context size.
    records = [r for r in records if (r.get("text") or "").strip()]
    records = records[:max_messages]
    return [
        Message(
            id=f"M{i:03d}",
            sender=str(record.get("sender") or "Unknown")[:80],
            text=str(record.get("text") or "")[:1200],
            timestamp=record.get("timestamp"),
        )
        for i, record in enumerate(records, start=1)
    ]


def messages_as_prompt_data(messages: Iterable[Message]) -> list[dict[str, str | None]]:
    return [
        {"id": m.id, "timestamp": m.timestamp, "sender": m.sender, "text": m.text}
        for m in messages
    ]
