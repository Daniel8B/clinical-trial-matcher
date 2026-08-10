from fastapi import FastAPI, Depends
from pydantic import BaseModel
from contextlib import asynccontextmanager
from clinical_trial_matcher.config import settings
from sentence_transformers import SentenceTransformer
from psycopg_pool import ConnectionPool

ml_models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):

    ml_models["embedder"] = SentenceTransformer(settings.embedding_model_name)
    ml_models["pool"] = ConnectionPool(settings.database_url, min_size=1, max_size=4)

    print("Model loaded at startup")
    yield
    ml_models["pool"].close()
    ml_models.clear()
    print ("Model cleared at shutdown")

app = FastAPI(lifespan=lifespan)

class SearchResult(BaseModel):
    id: int
    trial_text: str  
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

@app.post("/search", response_model=SearchResponse)
def search_trials(search_request: SearchRequest, pool: ConnectionPool = Depends(get_pool)):
    query_vector = ml_models["embedder"].encode(search_request.query).tolist()

    # <#> is negative inner product. MiniLM returns unit vectors, so inner product
    # equals cosine similarity, and <#> is cheaper than <=> because it skips the
    # norm division. It returns a negative value, so ORDER BY ... ASC ranks best
    # first; the SELECT negates it back to a positive similarity for the API.
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, trial_text, -(embedding <#> %s::vector) AS score FROM trials "
                "ORDER BY embedding <#> %s::vector ASC LIMIT %s",
                (query_vector, query_vector, search_request.top_k),
            )
            rows = cur.fetchall()

    results = [
        {"id": row[0], "trial_text": row[1], "score": float(row[2])}
        for row in rows
    ]

    return {
        "query": search_request.query,
        "result_count": len(results),
        "results": results
    }


