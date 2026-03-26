from typing import Any, Dict, List

from app.config import (
    ELASTIC_INDEX,
    TOP_K,
    MAX_CHARS_PER_FIELD,
    AZURE_OPENAI_CHAT_DEPLOYMENT,
)
from app.elastic_client import get_es_client, get_searchable_fields
from app.openai_client import get_azure_openai_client


es = get_es_client()
aoai_client = get_azure_openai_client()

# # Auto-generate fields here
# SEARCH_FIELDS = get_searchable_fields(es, ELASTIC_INDEX)
# print(f"[INFO] Auto-detected SEARCH_FIELDS: {SEARCH_FIELDS}")

SEARCH_FIELDS=["combined_field", "body_content", "meta_description", "kx_description,headings", "kx_title", "body", "title", "meta_keywords"]
RETURN_FIELDS=["combined_field", "body_content", "meta_description", "kx_description,headings", "kx_title", "body", "title", "meta_keywords"]

def safe_text(value: Any, max_chars: int = MAX_CHARS_PER_FIELD) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " | ".join(str(v) for v in value)
    text = str(value).strip()
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "..."
    return text


def build_search_query(question: str, top_k: int) -> Dict[str, Any]:
    return {
        "size": top_k,
        "query": {
            "multi_match": {
                "query": question,
                "fields": SEARCH_FIELDS,
                "type": "best_fields",
                "operator": "or",
                "fuzziness": "AUTO",
            }
        },
        "_source": RETURN_FIELDS,
    }


def format_hit(hit: Dict[str, Any]) -> Dict[str, Any]:
    source = hit.get("_source", {}) or {}

    item = {
        "score": hit.get("_score"),
        "id": hit.get("_id"),
        "fields": {},
    }

    for field in RETURN_FIELDS:
        if field in source:
            item["fields"][field] = safe_text(source.get(field))

    return item


def build_context(hits: List[Dict[str, Any]]) -> str:
    if not hits:
        return "No relevant documents were found."

    lines = []
    for i, hit in enumerate(hits, start=1):
        fields = hit.get("fields", {})
        lines.append(f"[Document {i}]")
        for key, value in fields.items():
            if value:
                lines.append(f"{key}: {value}")
        lines.append("")
    return "\n".join(lines).strip()


def generate_answer(question: str, context: str, temperature: float) -> str:
    SYSTEM_PROMPT= "You are a helpful product assistant. Answer only from the provided Elasticsearch search results. \
                    If the search results do not contain enough information, say so clearly. Keep answers concise and factual."
    response = aoai_client.chat.completions.create(
        model=AZURE_OPENAI_CHAT_DEPLOYMENT,
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Search Results:\n{context}\n\n"
                    "Answer the question using only the search results."
                ),
            },
        ],
    )

    return response.choices[0].message.content.strip()


def answer_question(question: str, top_k: int = None, temperature: float = None) -> Dict[str, Any]:
    top_k = top_k or TOP_K
    temperature = temperature if temperature is not None else 0.2
    response = es.search(
        index=ELASTIC_INDEX,
        body=build_search_query(question, top_k),
    )

    raw_hits = response.get("hits", {}).get("hits", [])
    hits = [format_hit(hit) for hit in raw_hits]
    context = build_context(hits)

    if not hits:
        answer = (
            "I could not find relevant information in the Elasticsearch index "
            "to answer that question."
        )
    else:
        answer = generate_answer(
            question=question,
            context=context,
            temperature=temperature,
        )

    return {
        "question": question,
        "answer": answer,
        "index": ELASTIC_INDEX,
        "results": hits,
    }