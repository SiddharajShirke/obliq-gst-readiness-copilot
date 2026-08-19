# Local Setup

## Self-contained mode

1. Copy `.env.example` to `.env`.
2. Keep `USE_IN_MEMORY_DB=true`, `AI_MODE=mock`, and `WHATSAPP_PROVIDER=mock`.
3. Install backend and frontend dependencies.
4. Generate demo files.
5. Start FastAPI and Next.js.

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e './backend[dev]'
python scripts/generate_demo_documents.py
(cd backend && python -m uvicorn app.main:app --reload)
(cd frontend && npm install && npm run dev)
```

On Windows, if `python`, `pip`, and `uvicorn` resolve to different installations, use
the virtual-environment interpreter directly instead of relying on PATH or activation:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe" -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -e ".\backend[dev]"
& ".\.venv\Scripts\python.exe" scripts\generate_demo_documents.py
Set-Location backend
& "..\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
```

Use the Partner demo button at `/auth/login`, then click **Reset demo** on the dashboard before running the guided Raj Traders flow.

## Local Supabase mode

Install Docker and Supabase CLI, then:

```bash
supabase start
supabase db reset
```

Copy local credentials printed by the CLI into `.env`, set `USE_IN_MEMORY_DB=false`, and run:

```bash
python scripts/seed_demo.py
python scripts/ingest_knowledge.py
```

For direct Next.js development, copy `frontend/.env.local.example` to `frontend/.env.local`. Keep service-role and Meta secrets only in the backend/root `.env`.
