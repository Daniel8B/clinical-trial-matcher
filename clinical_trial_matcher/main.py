from fastapi import FastAPI, Depends
from pydantic import BaseModel
from contextlib import asynccontextmanager
from clinical_trial_matcher.config import settings
from sentence_transformers import SentenceTransformer
from psycopg_pool import ConnectionPool

ml_models = {}

# Chunks fetched per requested trial before deduplication. One verbose trial can
# own many of the top chunks, so the inner query must over-fetch to have a good
# chance of yielding top_k distinct trials.
OVERFETCH = 5

# hnsw.ef_search is the size of the candidate list HNSW keeps while searching.
# Default is 40; a LIMIT above that degrades recall silently. Set per query.
EF_SEARCH = 200


@asynccontextmanager
async def lifespan(app: FastAPI):
    ml_models["embedder"] = SentenceTransformer(settings.embedding_model_name)
    ml_models["pool"] = ConnectionPool(settings.database_url, min_size=1, max_size=4)
    print("Model loaded at startup")
    yield
    ml_models["pool"].close()
    ml_models.clear()
    print("Model cleared at shutdown")


app = FastAPI(lifespan=lifespan)


class SearchResult(BaseModel):
    nct_id: str
    brief_title: str
    section: str
    chunk_text: str
    score: float


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchResponse(BaseModel):
    query: str
    result_count: int
    results: list[SearchResult]


def get_pool() -> ConnectionPool:
    return ml_models["pool"]


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Inner query: HNSW-accelerated top-N chunk search. ORDER BY on the distance
# operator alone is the only form the index can serve.
# Outer query: DISTINCT ON collapses to the best chunk per trial (max-over-chunks),
# joins trial metadata, and re-sorts by score.
SEARCH_SQL = """
WITH candidates AS (
    SELECT nct_id, section, chunk_text,
           -(embedding <#> %s::vector) AS score
    FROM chunks
    ORDER BY embedding <#> %s::vector ASC
    LIMIT %s
),
best_per_trial AS (
    SELECT DISTINCT ON (nct_id) nct_id, section, chunk_text, score
    FROM candidates
    ORDER BY nct_id, score DESC
)
SELECT b.nct_id, t.brief_title, b.section, b.chunk_text, b.score
FROM best_per_trial b
JOIN trials t ON t.nct_id = b.nct_id
ORDER BY b.score DESC
LIMIT %s
"""


@app.post("/search", response_model=SearchResponse)
def search_trials(
    search_request: SearchRequest,
    pool: ConnectionPool = Depends(get_pool),
):
    query_vector = ml_models["embedder"].encode(search_request.query).tolist()
    candidate_limit = search_request.top_k * OVERFETCH

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('hnsw.ef_search', %s, true)", (str(EF_SEARCH),)
            )
            cur.execute(
                SEARCH_SQL,
                (query_vector, query_vector, candidate_limit, search_request.top_k),
            )
            rows = cur.fetchall()

    results = [
        {
            "nct_id": row[0],
            "brief_title": row[1],
            "section": row[2],
            "chunk_text": row[3],
            "score": float(row[4]),
        }
        for row in rows
    ]

    return {
        "query": search_request.query,
        "result_count": len(results),
        "results": results,
    }