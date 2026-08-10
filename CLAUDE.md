# clinical-trial-matcher — working rules

RAG service matching patients to clinical trials by semantic search over
ClinicalTrials.gov data. FastAPI + Postgres/pgvector + local sentence-transformers.

## Environment
- Windows 11, PowerShell 5.1, Python 3.12.7 in `.venv` (Anaconda-parented). No `py` launcher.
- **Run everything from the repo root.** uvicorn imports, Docker build context,
  and relative paths in code all assume it.
- Postgres runs under `docker compose` (service `db`, image `pgvector/pgvector:pg16`).
  Reachable at `db:5432` from inside the compose network, `localhost:5432` from Windows.

## Hard rules
- **Parameterised SQL only** (`%s` placeholders). Never f-string interpolation into SQL.
- **Convert numpy types at every boundary**: `.tolist()` before a DB insert,
  `float()`/`int()` before returning through Pydantic. numpy does not cross
  the API or the DB boundary.
- **`def` handlers, not `async def`**, unless the handler waits on an external
  system *and* the library is async-compatible. psycopg 3 here is synchronous.
- **pgvector operator is `<#>`**, not `<=>`. MiniLM returns unit vectors
  (measured norm 1.0), so negative inner product is correct and cheaper.
  It returns a *negative* value — check ORDER BY direction and the sign.
- **Tests assert shape and ordering, never specific scores or ids.** A test that
  breaks when the embedding model is swapped, while the API works, is worse than no test.
- **Config comes from `config.py` (pydantic-settings), never hardcoded strings.**
  It is strict: a key in `.env` with no matching field is a startup failure.
  Adding or removing a config field means updating `.env` in the same change.
- **Never regenerate `requirements.txt` with `>`** — PowerShell 5.1 writes UTF-16
  and pip in the Linux container may fail to parse it. Use
  `pip freeze | Out-File -Encoding ascii requirements.txt`.
- **Do not run git commands that change state.** Branching, committing, pushing
  and merging are done by the human.
- **Do not edit README.md, PROGRESS.md, ROADMAP.md or COMMANDS.md** unless
  explicitly asked in the current prompt.
- Do not create files that were not asked for.

## Style
- Explain a design choice in a comment only where the reason is non-obvious
  (e.g. why the norm division is dropped from cosine). No narrating comments.
- Keep changes to the files named in the request. If a change requires touching
  another file, say so and stop rather than doing it silently.