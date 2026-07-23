# TMR Project Knowledge Base

## Project Overview
- **Project Path:** /Users/grant/tmr
- **Python venv:** /Users/grant/tmr/.venv
- **Main Command:** .venv/bin/python src/main.py
- **Validation Script:** .venv/bin/python scripts/validate_test_record.py
- **Local LLM Endpoint:** http://localhost:8080
- **Current Model:** unsloth/gemma-4-12b-it

## Infrastructure
### Git Server
- **Hostname:** macmini
- **IP Address:** 10.0.1.195
- **Username:** grant
- **Remote URL:** grant@10.0.1.195:~/git/tmr.git

### PostgreSQL Database
- **Host:** 10.0.1.195
- **Port:** 5432
- **Database Name:** tmr_db
- **Username:** tmr_user
- **Password:** TMR_Project_Pass_2024 (Change as needed)

## Hardware & Environment
- **Server Hardware:** Mac Mini (Intel CPU, 4 Cores, 34GB RAM)
- **Server OS:** macOS 15.7.7
- **Local Environment:** MacBook Pro
- **Homebrew Path:** /usr/local/bin/brew (Mac Mini)

## Data Handling & Rules
- **Sensitive Files (Ignored):**
    - .venv/
    - data/input/test_record.pdf
    - data/output/ocr_cache/
    - data/output/llm_cache/
    - tests/fixtures/test_record_expected.json
- **File Normalization:** All text/source files use LF (line feed) endings.
- **Storage Strategy:** Binaries (PDFs, images) are stored on local disk; paths are stored in the database.
- **Database Logic:** PostgreSQL handles JSONB for semi-structured data and relational links for project entities.

## Setup Notes
- **SSH Access:** Configured via `~/.ssh/config` using key `id_rsa`.
- **PostgreSQL Config:** Remote access enabled in `postgresql.conf` (listen_addresses='*') and `pg_hba.conf` (host all all 10.0.1.0/24 md5).
