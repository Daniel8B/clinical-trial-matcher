# Clinical Trial Matcher

A service for matching patients to clinical trials that are recruiting participants.

The finished system will be a RAG pipeline over ClinicalTrials.gov and PubMed data. This is week 1 of the build: the API skeleton, containerisation, and test suite are in place. Retrieval, the vector store, and the trial data land in weeks 2–4.

## Status

Working: a FastAPI service with three endpoints, a pinned dependency set, environment-based configuration, a Docker image, and a pytest suite. `/search` accepts and validates real queries but returns an echo — there is no retrieval yet.

## Stack

- **FastAPI** — web framework: routing, request/response validation, auto-generated docs
- **uvicorn** — ASGI server; owns the port and passes requests to the app
- **Pydantic / pydantic-settings** — request and response models, configuration from the environment
- **Docker** — containerised build
- **pytest** — test suite
- **scikit-learn / joblib** — placeholder model artifact (see Endpoints)

## Running it

### Docker

```bash
git clone https://github.com/Daniel8B/clinical-trial-matcher.git
cd clinical-trial-matcher
docker build -t trial-matcher .
docker run -p 8000:8000 trial-matcher
```

### Local development

```bash
git clone https://github.com/Daniel8B/clinical-trial-matcher.git
cd clinical-trial-matcher
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python train_model.py              # regenerates model.joblib
uvicorn clinical_trial_matcher.main:app --reload
```

Interactive API docs at `http://127.0.0.1:8000/docs`.

### Tests

```bash
pytest
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check. Currently reports process health only; will check the database connection once Postgres is added in week 2. |
| `POST` | `/search` | Takes a `query` string and `top_k`. Validates input and returns an echo — retrieval is implemented in week 4. |

## Design decisions

**The model is loaded once at startup, not per request.** A `lifespan` handler loads the artifact into memory before the server accepts traffic, and every request reads the same object. Loading per request costs the full load time on every call, and peak memory becomes `concurrent requests × model size`. The slot this occupies is filled by the embedding model and the pgvector connection pool in weeks 2–3.

**Dependencies are installed before application code is copied in.** Docker caches each layer and invalidates everything below a change. `pip install` takes ~20 seconds and its inputs rarely change; application code changes constantly. This ordering keeps the expensive layer cached, so a code edit rebuilds in ~2 seconds instead of ~40.

**The image contains only what is needed to serve.** The Dockerfile copies the package, the pinned requirements, and the model artifact — not the training script, tests, or documentation. Smaller image, and less inside it than needs to be.

**Training is separate from serving.** `train_model.py` runs by hand and writes an artifact; the service only loads it. The two have different lifecycles — training is slow and occasional and needs data, serving is fast and constant and needs only the artifact. The model artifact is committed today and moves to S3 in week 5, when it becomes too large for git.

**Responses are declared with `response_model`.** This pins the API contract and drops any field not declared on it. Once real retrieval lands, database rows will carry internal IDs, similarity scores, and chunk offsets; the response model is what stops them reaching callers.

**Configuration comes from the environment, not from code.** `pydantic-settings` reads a local `.env` in development and real environment variables in production, so the same image runs in both without a rebuild and no secrets enter the repository.

**Handlers are synchronous (`def`).** None of them currently wait on anything external — FastAPI runs them in a threadpool, so they cannot block the event loop. `/search` becomes `async def` in week 4, when it waits on an LLM API call, and only alongside an async HTTP client.

**uvicorn binds to `0.0.0.0` in the container.** A container has its own network stack and its own loopback address; binding to `127.0.0.1` would leave the service running but unreachable from outside the container.