from fastapi import FastAPI
from pydantic import BaseModel
from contextlib import asynccontextmanager
from clinical_trial_matcher.config import settings
from sentence_transformers import SentenceTransformer
import json
import numpy as np

ml_models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):

    with open("corpus.json")as f:
        data = json.load(f)
        texts = [item["text"] for item in data]
    
    ml_models["embedder"] = SentenceTransformer(settings.embedding_model_name)
    ml_models["corpus"] = data
    ml_models["corpus_vectors"] = ml_models["embedder"].encode(texts)

    print("Model loaded at startup")
    yield 
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


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/search", response_model=SearchResponse) 
def search_trials(search_request: SearchRequest): 
    query_vector = ml_models["embedder"].encode(search_request.query)

    ranks = []

    for item, vec in zip(ml_models["corpus"], ml_models["corpus_vectors"]):
        similarity = float(np.dot(query_vector, vec))
        ranks.append({
            "id": item["id"],
            "trial_text": item["text"],
            "score": similarity,
        })

    ranks.sort(key=lambda x: x["score"], reverse=True)
    top = ranks[:search_request.top_k]

    return {
        "query": search_request.query,
        "result_count": len(top),
        "results": top
    }


