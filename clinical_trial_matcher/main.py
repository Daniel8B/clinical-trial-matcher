from fastapi import FastAPI
from pydantic import BaseModel
import time
import joblib
from contextlib import asynccontextmanager

ml_models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    ml_models["clf"] = joblib.load("model.joblib")
    print("Model loaded at startup")
    yield 
    ml_models.clear()
    print ("Model cleared at shutdown")

app = FastAPI(lifespan=lifespan)

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

class SearchResponse(BaseModel):
    query: str
    result_count: int 

class PredictRequest(BaseModel):
    feature_1: float
    feature_2: float

class PredictResponse(BaseModel):
    prediction: int


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/search", response_model=SearchResponse) 
def search_trials(search_request: SearchRequest): 
    return {"query": search_request.query, "result_count": search_request.top_k}

@app.post("/predict", response_model=PredictResponse)#What goes out
def predict(features: PredictRequest):#What comes in

    start = time.perf_counter()
    clf = ml_models["clf"]
    elapsed_time = time.perf_counter() - start

    result = clf.predict([[features.feature_1, features.feature_2]])

    print(f"Model loading took {elapsed_time:.4f} seconds")

    return {"prediction": int(result[0])}



