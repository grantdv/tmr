# Total Medical Record (TMR)

TMR is a local medical-record ingestion and analysis system. It ingests PDFs and
images, performs OCR, sends focused contexts to a local LLM, extracts structured
medical entities, attaches provenance, and marks uncertain records for review.

## Current Capabilities

- Scanned PDF OCR with page markers.
- Image OCR.
- Local OpenAI-compatible LLM extraction.
- No fabricated extraction behavior.
- Patient, encounter metadata, lab, and prescription extraction.
- Encounter metadata includes facility, provider, and date of service.
- Source page/source text provenance for extracted entities.
- Page-level document sections retained for future review/database workflows.
- Non-destructive OCR suggestions, e.g. suggested dosage/name corrections.
- Review status and review reasons.
- Structured JSON output artifacts.
- Validation harness for the current local test document.

## Project Structure

- `src/ingestion`: File scanning and raw file discovery.
- `src/processing`: PDF/image OCR and text extraction.
- `src/analysis`: LLM client, prompts, extraction, normalization, schemas.
- `src/db`: Placeholder for future PostgreSQL integration.
- `scripts`: Development and validation scripts.
- `tests/fixtures`: Local/sanitized validation fixture area.
- `data/input`: Local-only source documents.
- `data/output`: Local-only generated JSON outputs.

## Local LLM Requirement

The local LLM server is expected at:

```text
http://localhost:8080
```

The client discovers the model identifier from:

```text
/v1/models
```

Set `TMR_LLM_MODEL` only if you need to override automatic discovery.

## Getting Started

Use the project virtual environment for all Python commands.

```bash
cd /Users/grant/tmr
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python src/main.py
```

For an exact recreation of the current working environment, use:

```bash
.venv/bin/python -m pip install -r requirements-lock.txt
```

Do not use the system `python3` after creating the environment. Use
`.venv/bin/python` or activate the environment with:

```bash
source .venv/bin/activate
```

## Validation

The validation harness runs the real OCR and real local LLM pipeline, then
compares the observed result to a manually reviewed local fixture.

```bash
.venv/bin/python scripts/validate_test_record.py
```

Optionally dump the observed structured record:

```bash
.venv/bin/python scripts/validate_test_record.py --dump-json data/output/test_record_observed.json
```

The default expected fixture path is:

```text
tests/fixtures/test_record_expected.json
```

That file is intentionally ignored by git because it may contain values reviewed
from real medical records. A sanitized template is available at:

```text
tests/fixtures/test_record_expected.example.json
```

## Structured Output Metadata

Extraction outputs are versioned artifacts. Each JSON output contains:

- `tmr_version`
- `output_schema_version`
- Processing timestamps
- Runtime settings
- OCR cache setting
- Local LLM provider/base URL/model/timeout
- Source file metadata including SHA256
- Extracted records
- Retained page-level document sections for review

Example:

```json
{
  "tmr_version": "0.1.0",
  "output_schema_version": "0.1",
  "llm": {
    "provider": "local",
    "base_url": "http://localhost:8080",
    "model": "...",
    "timeout_seconds": 180
  },
  "records": []
}
```

Generated output artifacts may contain PHI and are ignored by git.

## OCR Cache

PDF extraction uses a local cache under:

```text
data/output/ocr_cache/
```

The cache stores page-level OCR/native text and combined page-marked text. It is
keyed by source-file SHA256, so changing a PDF creates a new cache entry.

The cache may contain PHI and is ignored by git.

## LLM Response Cache

Successful local LLM JSON responses are cached under:

```text
data/output/llm_cache/
```

The cache key includes model, provider/base URL, system prompt, extraction prompt,
focused context, and generation settings. Failed or malformed LLM responses are
not cached.

The LLM cache may contain PHI and is ignored by git.

## Git/Data Safety

The repo is configured so the following remain local-only:

- Virtual environments.
- Python caches.
- `.env` files.
- Source medical documents in `data/input`.
- Generated extraction output in `data/output`.
- Local reviewed fixtures named `*_expected.json`.

Do not commit real patient records, generated extraction artifacts, or reviewed
fixtures containing patient information.

Safe-to-commit placeholders and documentation are kept with `.gitkeep` and
README files.

## Useful Commands

Compile-check source and scripts:

```bash
.venv/bin/python -m compileall -q src scripts
```

Run the application by scanning `data/input`:

```bash
.venv/bin/python src/main.py
```

Run one file directly:

```bash
.venv/bin/python src/main.py --file data/input/test_record.pdf
```

Write output to a specific file:

```bash
.venv/bin/python src/main.py --file data/input/test_record.pdf --output data/output/review.json
```

Bypass the OCR cache and regenerate OCR/native text extraction:

```bash
.venv/bin/python src/main.py --file data/input/test_record.pdf --no-ocr-cache
```

Bypass the local LLM response cache:

```bash
.venv/bin/python src/main.py --file data/input/test_record.pdf --no-llm-cache
```

Bypass both caches:

```bash
.venv/bin/python src/main.py --file data/input/test_record.pdf --no-ocr-cache --no-llm-cache
```

Run validation:

```bash
.venv/bin/python scripts/validate_test_record.py
```

Run validation while bypassing the OCR cache:

```bash
.venv/bin/python scripts/validate_test_record.py --no-ocr-cache
```

Run validation while bypassing the LLM cache:

```bash
.venv/bin/python scripts/validate_test_record.py --no-llm-cache
```
