from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import ChatRequest
from app.search import answer_question
from app.elastic_client import get_es_client
from app.config import CONTENT_INDEX, CONTENT_INDEXES, CONTENT_SEARCH_MODE, PARTS_INDEX


def format_index_display(indexes):
    if isinstance(indexes, str):
        return indexes
    if not indexes:
        return CONTENT_INDEX
    return ", ".join(indexes)


def default_content_index_display():
    return format_index_display(CONTENT_INDEXES or [CONTENT_INDEX])

app = FastAPI(title="Elastic + Azure OpenAI Chatbot", version="0.4.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse, tags=["ui"])
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "question": "",
            "answer": "",
            "results": [],
            "index": default_content_index_display(),
            "searched_indexes": CONTENT_INDEXES or [CONTENT_INDEX],
            "index_label": "Indexes" if len(CONTENT_INDEXES or [CONTENT_INDEX]) > 1 else "Index",
            "error": "",
            "top_k": 5,
        },
    )


@app.post("/ask", response_class=HTMLResponse, tags=["ui"])
def ask_question(request: Request, question: str = Form(...), top_k: int = Form(5)):
    question = question.strip()

    if not question:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "question": "",
                "answer": "",
                "results": [],
                "index": default_content_index_display(),
                "searched_indexes": CONTENT_INDEXES or [CONTENT_INDEX],
                "index_label": "Indexes" if len(CONTENT_INDEXES or [CONTENT_INDEX]) > 1 else "Index",
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
                "index": result.get("index_display", result.get("index", CONTENT_INDEX)),
                "searched_indexes": result.get("searched_indexes", [result.get("index", CONTENT_INDEX)]),
                "index_label": "Indexes" if len(result.get("searched_indexes", [result.get("index", CONTENT_INDEX)])) > 1 else "Index",
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
                "index": default_content_index_display(),
                "searched_indexes": CONTENT_INDEXES or [CONTENT_INDEX],
                "index_label": "Indexes" if len(CONTENT_INDEXES or [CONTENT_INDEX]) > 1 else "Index",
                "error": f"Chat failed: {exc}",
                "top_k": top_k,
            },
            status_code=500,
        )


@app.get("/health", tags=["health"])
def health():
    try:
        es_client = get_es_client()
        return {
            "ping": es_client.ping(),
            "content_search_mode": CONTENT_SEARCH_MODE,
            "content_indexes": CONTENT_INDEXES,
            "content_index_exists": {
                index: bool(es_client.indices.exists(index=index)) for index in CONTENT_INDEXES
            },
            "parts_index": PARTS_INDEX,
            "parts_index_exists": bool(es_client.indices.exists(index=PARTS_INDEX)),
        }
    except Exception as exc:
        return {"error": str(exc)}


@app.post("/chat", tags=["chat"])
def chat(request: ChatRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        return answer_question(question=question, top_k=request.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}") from exc
