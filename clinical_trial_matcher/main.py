import fastapi

app = fastapi.FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}