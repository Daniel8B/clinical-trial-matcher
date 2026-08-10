import json
import psycopg
from sentence_transformers import SentenceTransformer
from clinical_trial_matcher.config import settings

with open("corpus.json") as f:
    corpus = json.load(f)

texts = [item["text"] for item in corpus]

model = SentenceTransformer(settings.embedding_model_name)
embeddings = model.encode(texts)

with psycopg.connect(settings.database_url) as conn:
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("DROP TABLE IF EXISTS trials")
        # embedding_dimension is a type declaration, not a value, so it can't be
        # a %s placeholder; it comes from Settings, never from request/file input.
        cur.execute(
            f"""
            CREATE TABLE trials (
                id SERIAL PRIMARY KEY,
                trial_text TEXT NOT NULL,
                embedding vector({settings.embedding_dimension}) NOT NULL
            )
            """
        )
        for text, vector in zip(texts, embeddings):
            cur.execute(
                "INSERT INTO trials (trial_text, embedding) VALUES (%s, %s)",
                (text, vector.tolist()),
            )
        cur.execute(
            "SELECT count(*), min(vector_dims(embedding)), max(vector_dims(embedding)) FROM trials"
        )
        stats = cur.fetchone()

print(f"Rows inserted: {len(texts)}")
print(f"count, min(vector_dims), max(vector_dims): {stats}")