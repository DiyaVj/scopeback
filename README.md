# ScopeBack — local-first project scope audit MVP

ScopeBack compares a project quote / statement of work with a client conversation export and highlights **potential** scope changes with source-message evidence. The freelancer makes the final decision about what was completed, approved, included or already billed.

## Demo: https://youtu.be/BQrEaSxW7fM?si=bAZ0jNwI8irKdDIi

## Current MVP features

- Paste a quote and WhatsApp conversation, or upload a text-based PDF/TXT quote and TXT conversation export.
- Uses a local Ollama model for structured analysis. Default: `qwen3.5:9b`.
- Parses messages into canonical IDs (`M001`, `M002`, ...) and validates all returned evidence references against the parsed export.
- Separates potential scope changes, likely in-scope requests and ambiguous cases.
- Human review status: needs review, confirmed extra work, included in scope, already billed/approved, or not applicable/not completed.
- Estimate field only counts items the user explicitly confirms, with hours and hourly rate entered by the user. The model never sets hours or prices.
- Export review results as Markdown.
- Synthetic sample project and a clearly labeled illustrative sample report (available even without Ollama).
- No app database or saved uploads in this MVP.
- Frontend assets are bundled locally; the UI does not load third-party font/CDN assets.

## Requirements

- Python 3.10+ (developed/tested with Python 3.13)
- [Ollama](https://ollama.com/) installed and running
- An Ollama model installed locally, e.g. `qwen3.5:9b` or another model that supports structured JSON output

## Run locally

```bash
cd scopeback
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env             # optional; defaults are in the app
ollama pull qwen3.5:9b           # skip if already installed
ollama serve                     # in another terminal, if Ollama isn't already running
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Check the header status pill to confirm Ollama and the configured model are available. Click **Load a sample project** before running an analysis. **Preview sample report** opens a canned, clearly labeled report without requiring Ollama.

### Configure a different model

Set environment variables before starting the server:

```bash
export OLLAMA_MODEL="gemma4:latest"
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_TIMEOUT_SECONDS="180"
uvicorn app.main:app --reload
```

Use an exact model tag that you have already pulled. If you want to claim the Hacktoberfest Gemma partner category, test a Gemma model and report the actual tag and results in the write-up. The app should only say “local” when the configured endpoint is local. If you configure a remote Ollama server, text is sent to that server.

### Optional Sentry tracing (partner category)

Create a Sentry project with Python/FastAPI tracing, then set `SENTRY_DSN` in `.env`. Tracing is disabled when that variable is blank. Set `SENTRY_TRACES_SAMPLE_RATE` to control trace sampling (use `1.0` while instrumenting a small demo, lower it for regular use). Request-body collection is disabled and custom AI spans only add model/provider and count metadata; do not manually attach prompts, conversation text or model outputs to telemetry. Verify the telemetry before demonstrating the privacy claim.

## Supported inputs and limits

- Quote: paste text or upload text-based `.pdf`, `.txt`, `.md`.
- Conversation: paste text or upload WhatsApp `.txt` export / `.md`.
- Upload cap: 5 MB/file by default.
- The API caps quote content and transcript length before inference and parses at most 120 messages.
- Scanned/image-only PDFs are not supported. OCR is intentionally postponed.
- This is an early local MVP, not a legal/accounting tool. It does not prove that work was completed, unbilled, or recoverable. Review the full agreement and all later approvals/invoices.

## Tests

```bash
python -m pytest -q
```

## API endpoints

- `GET /` — web UI
- `GET /api/health` — Ollama/model status
- `GET /api/demo` — synthetic project input
- `GET /api/demo-report` — canned report for testing UI without Ollama; explicitly marked as illustrative, not model-generated
- `POST /api/analyze` — quote and conversation analysis via Ollama

## Near-term roadmap

1. Validate the pain with 3–5 freelance developers/designers or small agencies before adding features.
2. Build a labelled evaluation set: in-scope, clearly out-of-scope, ambiguous, already approved and already billed examples.
3. Measure evidence-link accuracy and false positives; do not optimize only for the number of findings.
4. Add Sentry tracing with prompt/document content redacted; keep local analysis independent of any hosted demo.
5. Add a robust export format / PDF report only after the evidence workflow proves useful.
