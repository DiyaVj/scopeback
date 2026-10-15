from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration

from .analyzer import analyze_with_ollama
from .parser import extract_pdf_text, parse_messages

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")
_sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[FastApiIntegration(), HttpxIntegration()],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "1.0")),
        environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
        send_default_pii=False,
        max_request_body_size="never",
    )
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "5")) * 1024 * 1024
MAX_QUOTE_CHARS = 22000
MAX_CHAT_CHARS = 60000

app = FastAPI(title="ScopeBack", version="0.1.0", description="Local-first project scope audit MVP")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
def root():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
async def health():
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
    connected = False
    installed = False
    error = None
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
            connected = True
            names = [item.get("name", "") for item in response.json().get("models", [])]
            installed = any(name == model or name.startswith(model + ":") for name in names)
    except Exception as exc:
        error = str(exc)[:180]
    return {
        "ollama_connected": connected,
        "model": model,
        "model_installed": installed,
        "base_url": base_url,
        "error": error,
        "privacy": "Analysis runs against the configured Ollama endpoint. With the default URL, inference is local on this machine.",
    }


async def read_upload(upload: Optional[UploadFile], role: str) -> str:
    if upload is None or not upload.filename:
        return ""
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"{role} file is too large. Max file size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    suffix = Path(upload.filename).suffix.lower()
    if suffix == ".pdf":
        if role != "Quote":
            raise HTTPException(400, "Conversation upload must be a .txt file in this MVP.")
        try:
            return extract_pdf_text(data)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    if suffix not in {".txt", ".md", ".text"}:
        raise HTTPException(400, f"{role} file must be a PDF (quote only) or plain text (.txt/.md).")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


@app.post("/api/analyze")
async def analyze(
    quote_text: str = Form(""),
    messages_text: str = Form(""),
    hourly_rate: float = Form(0),
    quote_file: Optional[UploadFile] = File(None),
    messages_file: Optional[UploadFile] = File(None),
):
    if hourly_rate < 0 or hourly_rate > 10000000:
        raise HTTPException(400, "Hourly rate must be between ₹0 and ₹10,000,000.")
    uploaded_quote = await read_upload(quote_file, "Quote")
    uploaded_messages = await read_upload(messages_file, "Conversation")
    quote = (uploaded_quote or quote_text).strip()
    transcript = (uploaded_messages or messages_text).strip()
    if not quote:
        raise HTTPException(400, "Add a quote/SOW as text or upload a text-based PDF/TXT file.")
    if not transcript:
        raise HTTPException(400, "Add a WhatsApp export or pasted conversation.")
    if len(quote) > MAX_QUOTE_CHARS:
        quote = quote[:MAX_QUOTE_CHARS]
    if len(transcript) > MAX_CHAT_CHARS:
        transcript = transcript[:MAX_CHAT_CHARS]

    messages = parse_messages(transcript)
    if not messages:
        raise HTTPException(400, "No messages could be read from the conversation.")
    try:
        analysis, model = await analyze_with_ollama(quote, messages)
    except RuntimeError as exc:
        message = str(exc)
        status = 503 if "connect to Ollama" in message else 502
        raise HTTPException(status, message) from exc
    return {
        "ok": True,
        "mode": "local_ollama",
        "model": model,
        "message_count": len(messages),
        "hourly_rate": hourly_rate,
        "notice": "AI findings are suggestions only. Review the agreement, evidence, completion status, and billing status before acting.",
        **analysis,
    }


@app.get("/api/demo")
def demo():
    quote = """PROJECT QUOTE — WEBSITE BUILD
Project fee: ₹40,000
Included deliverables:
- Five responsive pages: Home, About, Services, Portfolio, Contact.
- A basic contact form that sends submissions to the supplied email address.
- Up to two rounds of design revisions.
- Client provides approved copy and existing brand assets.
Excluded unless separately quoted:
- Blog/CMS functionality.
- Scroll animations or custom motion design.
- CRM integrations such as HubSpot.
- Copywriting or additional pages.
Any work outside the listed deliverables should be estimated and approved separately before implementation.
"""
    messages = """Client: Can we add a blog section where we can publish posts ourselves?
Developer: Blog/CMS isn't in the original quote; I can estimate it separately.
Client: Please put it in before launch. We can discuss the cost later.
Client: Could we also add scroll animations and connect the contact form to HubSpot?
Developer: The quote includes a basic email form only. I'll estimate the HubSpot integration separately.
Client: Send me the estimate, but let's start on the animations.
Client: Could you change the colors and contact page copy one more time?
Developer: The quote includes two design revision rounds. I need to check which round we're on.
Client: Fair enough, let's confirm that tomorrow.
"""
    return {"quote_text": quote, "messages_text": messages}


@app.get("/api/demo-report")
def demo_report():
    """Canned illustrative report for UI exploration; it is not an AI result."""
    return {
        "ok": True,
        "mode": "illustrative_demo",
        "model": None,
        "message_count": 8,
        "hourly_rate": 1500,
        "project_summary": "A ₹40,000 five-page website quote with two revision rounds and explicit exclusions for CMS, animation, and CRM integration.",
        "agreed_scope": [
            "Five responsive pages: Home, About, Services, Portfolio, Contact",
            "Basic email contact form",
            "Up to two design revision rounds",
            "Blog/CMS, animations and CRM integrations are excluded unless separately quoted",
        ],
        "findings": [
            {
                "title": "Blog / CMS functionality",
                "classification": "potential_scope_change",
                "summary": "The quote explicitly excludes blog/CMS functionality. The client requested a self-publishing blog and later asked to add it before launch. These messages support a scope-change discussion, but do not establish that the work was completed or remained unpaid.",
                "source_message_ids": ["M001", "M003"],
                "evidence": [
                    {"message_id": "M001", "timestamp": None, "sender": "Client", "text": "Can we add a blog section where we can publish posts ourselves?"},
                    {"message_id": "M003", "timestamp": None, "sender": "Client", "text": "Please put it in before launch. We can discuss the cost later."},
                ],
                "scope_reference": "Excluded unless separately quoted: Blog/CMS functionality",
                "confidence": "high",
                "review_status": "needs_review",
                "hours": 0,
            },
            {
                "title": "Scroll animations",
                "classification": "potential_scope_change",
                "summary": "Custom scroll animations are specifically excluded unless separately quoted. The client asked for them and said to start on them, but the conversation does not confirm an approved price or completion.",
                "source_message_ids": ["M004", "M006"],
                "evidence": [
                    {"message_id": "M004", "timestamp": None, "sender": "Client", "text": "Could we also add scroll animations and connect the contact form to HubSpot?"},
                    {"message_id": "M006", "timestamp": None, "sender": "Client", "text": "Send me the estimate, but let's start on the animations."},
                ],
                "scope_reference": "Excluded unless separately quoted: Scroll animations or custom motion design",
                "confidence": "high",
                "review_status": "needs_review",
                "hours": 0,
            },
            {
                "title": "HubSpot integration",
                "classification": "potential_scope_change",
                "summary": "The included form only sends submissions to email. The client requested a HubSpot connection. Confirm whether an estimate was approved and whether the integration was completed or billed.",
                "source_message_ids": ["M004"],
                "evidence": [
                    {"message_id": "M004", "timestamp": None, "sender": "Client", "text": "Could we also add scroll animations and connect the contact form to HubSpot?"}
                ],
                "scope_reference": "Excluded unless separately quoted: CRM integrations such as HubSpot",
                "confidence": "high",
                "review_status": "needs_review",
                "hours": 0,
            },
            {
                "title": "Possible third design revision",
                "classification": "unclear",
                "summary": "The client requested another color and contact-page copy change, but the agreement does not say how revision rounds are counted and the developer says they need to check. Verify the revision history before classifying this as extra work.",
                "source_message_ids": ["M007", "M008"],
                "evidence": [
                    {"message_id": "M007", "timestamp": None, "sender": "Client", "text": "Could you change the colors and contact page copy one more time?"},
                    {"message_id": "M008", "timestamp": None, "sender": "Developer", "text": "The quote includes two design revision rounds. I need to check which round we're on."},
                ],
                "scope_reference": "Up to two rounds of design revisions",
                "confidence": "medium",
                "review_status": "needs_review",
                "hours": 0,
            },
        ],
        "limitations": [
            "This is a canned example, not generated by the local model.",
            "The conversation shows requests, not proof that the work was completed or unpaid.",
            "Review the full agreement, any later approvals, delivery records and invoices before taking action.",
        ],
        "notice": "Illustrative sample only. AI findings are suggestions; review all evidence before acting.",
    }
