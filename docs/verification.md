# Verification Record

This record describes the checks run while assembling the distributable prototype on 18 August 2026.

## Completed checks

- `pytest -o addopts='' -W error::UserWarning` — **41 tests passed**.
- `coverage run -m pytest` followed by `coverage report` — **80% total Python coverage**.
- `python -m compileall -q backend/app scripts` — Python source compiled successfully.
- Backend import smoke — 62 application modules imported.
- FastAPI OpenAPI smoke — 46 paths generated and critical routes confirmed.
- TypeScript AST parse — all application TypeScript/TSX files parsed with zero syntax diagnostics.
- Strict structural TypeScript check — passed using temporary local declaration stubs because npm dependencies could not be downloaded in the execution sandbox.
- Environment/secret scan — no high-confidence real API keys or JWTs found; secret example fields remain empty.
- JSON, TOML and Docker Compose YAML parsing — passed.
- Generated synthetic documents were mirrored into the browser demo assets and checksum-compared.
- ZIP archive integrity — checked after packaging with `unzip -t`.

## Environment-limited checks

The execution sandbox could not resolve `registry.npmjs.org` (`EAI_AGAIN`), so it was not possible to install frontend dependencies or run the real `next build`, ESLint or Vitest commands here. The repository includes the exact commands for a network-enabled machine:

```bash
cd frontend
npm install
npm run test
npm run lint
npm run build
```

Docker, PostgreSQL and the Supabase CLI were not available in the execution sandbox, so Docker image builds and live migration execution were not performed here. SQL contract/security tests and static migration inspection are included; the README contains the live Supabase setup commands.
