from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import ChatRequest
from app.search import answer_question
from app.elastic_client import get_es_client
from app.config import ELASTIC_INDEX

app = FastAPI(title="Elastic + Azure OpenAI Chatbot", version="0.3.0")

# Static files and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse, tags=["ui"])
def home(request: Request):
    """
    Render the initial UI page.
    """
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "question": "",
            "answer": "",
            "results": [],
            "index": ELASTIC_INDEX,
            "error": "",
            "top_k": 5, 
        },
    )


@app.post("/ask", response_class=HTMLResponse, tags=["ui"])
def ask_question(request: Request, question: str = Form(...), top_k: int = Form(5)):
    """
    Handle form submission from the UI page.
    """
    question = question.strip()

    if not question:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "question": "",
                "answer": "",
                "results": [],
                "index": ELASTIC_INDEX,
                "error": "Question cannot be empty.",
                "top_k": top_k,
            },
            status_code=400,
        )

    try:
        result = answer_question(question=question, top_k=top_k)

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "question": result.get("question", question),
                "answer": result.get("answer", ""),
                "results": result.get("results", []),
                "index": result.get("index", ELASTIC_INDEX),
                "error": "",
                "top_k": top_k,
            },
        )
    except Exception as exc:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "question": question,
                "answer": "",
                "results": [],
                "index": ELASTIC_INDEX,
                "error": f"Chat failed: {exc}",
            },
            status_code=500,
        )


@app.get("/health", tags=["health"])
def health():
    try:
        es_client = get_es_client()
        return {
            "ping": es_client.ping(),
            "index": ELASTIC_INDEX,
            "index_exists": bool(es_client.indices.exists(index=ELASTIC_INDEX)),
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/chat", tags=["chat"])
def chat(request: ChatRequest):
    """
    Keep the JSON API endpoint for programmatic use.
    """
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