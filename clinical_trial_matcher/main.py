from fastapi import FastAPI, Depends
from pydantic import BaseModel
from contextlib import asynccontextmanager
from clinical_trial_matcher.config import settings
from clinical_trial_matcher import retrieval
from sentence_transformers import SentenceTransformer, CrossEncoder
from psycopg_pool import ConnectionPool
from clinical_trial_matcher import generation
from clinical_trial_matcher.llm import LLMClient, OllamaClient

ml_models = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    ml_models["embedder"] = SentenceTransformer(settings.embedding_model_name)
    # Cross-encoder: ~5s cold load, additive with the embedder's. Both are
    # scale-to-zero cold-start cost on Container Apps (Week 3 Day 4).
    ml_models["cross_encoder"] = CrossEncoder(
        settings.cross_encoder_model_name, max_length=256
    )
    ml_models["pool"] = ConnectionPool(settings.database_url, min_size=1, max_size=4)
    ml_models["llm"] = OllamaClient(
        settings.llm_base_url,
        settings.llm_model_name,
        temperature=settings.llm_temperature,
    )
    print("Models loaded at startup")
    yield
    ml_models["pool"].close()
    ml_models["llm"].close()
    ml_models.clear()
    print("Models cleared at shutdown")


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

def get_llm() -> LLMClient:
    return ml_models["llm"]

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse)
def search_trials(
    search_request: SearchRequest,
    pool: ConnectionPool = Depends(get_pool),
):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            results = retrieval.search(
                cur,
                ml_models["embedder"],
                ml_models["cross_encoder"],
                search_request.query,
                search_request.top_k,
            )

    return {
        "query": search_request.query,
        "result_count": len(results),
        "results": results,
    }

class AnswerRequest(BaseModel):
    query: str
    top_k: int = 5


class EvidenceItem(BaseModel):
    number: int
    nct_id: str
    brief_title: str
    section: str
    text: str


class AnswerResponse(BaseModel):
    query: str
    answer: str | None
    citations: list[int]
    evidence: list[EvidenceItem]
    generation_available: bool
    reason: str | None


@app.post("/answer", response_model=AnswerResponse)
def answer_query(
    answer_request: AnswerRequest,
    pool: ConnectionPool = Depends(get_pool),
    llm: LLMClient = Depends(get_llm),
):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            results = retrieval.search(
                cur,
                ml_models["embedder"],
                ml_models["cross_encoder"],
                answer_request.query,
                answer_request.top_k,
            )

    result = generation.generate_answer(
        llm, answer_request.query, results, settings.llm_max_tokens
    )
    return {"query": answer_request.query, **result}