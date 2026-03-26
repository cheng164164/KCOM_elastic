from fastapi import FastAPI, HTTPException
from app.models import ChatRequest, HealthResponse
from app.search import answer_question
from app.elastic_client import get_es_client
from app.config import ELASTIC_INDEX

app = FastAPI(title="Elastic + Azure OpenAI Chatbot", version="0.2.0")


@app.get("/", tags=["root"])
def root():
    return {"message": "Elastic + Azure OpenAI chatbot is running."}


@app.get("/health")
def health():
    try:
        es_client = get_es_client()
        return {
            "ping": es_client.ping(),
            "index": ELASTIC_INDEX,
            "index_exists": bool(es_client.indices.exists(index=ELASTIC_INDEX))
        }
    except Exception as e:
        return {"error": str(e)}
    

@app.post("/chat", tags=["chat"])
def chat(request: ChatRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = answer_question(
            question=question,
            top_k=request.top_k
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}") from exc