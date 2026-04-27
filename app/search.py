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

# # Auto-generate fields here
# SEARCH_FIELDS = get_searchable_fields(es, ELASTIC_INDEX)
# print(f"[INFO] Auto-detected SEARCH_FIELDS: {SEARCH_FIELDS}")

# BM25 fields only. Do NOT include the semantic_text field here.
SEARCH_FIELDS = [
    "combined_field",
    "title",
    "kx_title",
    "meta_description",
    "kx_description",
    "body_content",
    "body",
    "meta_keywords",
]

RETURN_FIELDS = [
    "combined_field",
    "body_content",
    "meta_description",
    "kx_description",
    "kx_title",
    "body",
    "title",
    "meta_keywords",
]


# Hardcoded semantic settings
SEMANTIC_FIELD = "body_content_semantic"
SEMANTIC_INFERENCE_ID = ".elser_model_2_linux-x86_64"

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
    """
    BM25 / full-text only
    """
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


def build_hybrid_query(question: str, top_k: int) -> Dict[str, Any]:
    """
    Hybrid search without RRF:
    BM25 + semantic query on semantic_text field
    """
    return {
        "size": top_k,
        "query": {
            "bool": {
                "should": [
                    {
                        "multi_match": {
                            "query": question,
                            "fields": SEARCH_FIELDS,
                            "type": "best_fields",
                            "operator": "or",
                            "fuzziness": "AUTO",
                            "boost": 1.0,
                        }
                    },
                    {
                        "semantic": {
                            "field": SEMANTIC_FIELD,
                            "query": question,
                            "boost": 2.0,
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        },
        "_source": RETURN_FIELDS,
    }


def build_rrf_query(question: str, top_k: int) -> Dict[str, Any]:
    """
    Hybrid search with RRF using retrievers.
    Lexical retriever + semantic retriever.
    """
    return {
        "size": top_k,
        "retriever": {
            "rrf": {
                "retrievers": [
                    {
                        "standard": {
                            "query": {
                                "multi_match": {
                                    "query": question,
                                    "fields": SEARCH_FIELDS,
                                    "type": "best_fields",
                                    "operator": "or",
                                    "fuzziness": "AUTO",
                                }
                            }
                        }
                    },
                    {
                        "standard": {
                            "query": {
                                "semantic": {
                                    "field": SEMANTIC_FIELD,
                                    "query": question}
                            }
                        }
                    },
                ],
                "rank_constant": 20,
                "rank_window_size": 50,
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


def generate_answer(question: str, context: str) -> str:
    aoai_client = get_azure_openai_client()
    SYSTEM_PROMPT= "You are a helpful product assistant. Answer only from the provided Elasticsearch search results. \
                    If the search results do not contain enough information, say so clearly. Keep answers concise and factual."
    response = aoai_client.chat.completions.create(
        model=AZURE_OPENAI_CHAT_DEPLOYMENT,
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


def answer_question(question: str, top_k: int = None, mode: str = "hybrid") -> Dict[str, Any]:
    top_k = top_k or TOP_K

    if mode == "rrf":
        query_body = build_rrf_query(question, top_k)
    elif mode == "hybrid":
        query_body = build_hybrid_query(question, top_k)
    else:
        query_body = build_search_query(question, top_k)

    response = es.search(
        index=ELASTIC_INDEX,
        body=query_body,
    )

    raw_hits = response.get("hits", {}).get("hits", [])
    hits = [format_hit(hit) for hit in raw_hits]
    context = build_context(hits)

    if not hits:
        answer = "I could not find relevant information in the Elasticsearch index."
    else:
        answer = generate_answer(question=question, context=context)

    return {
        "question": question,
        "answer": answer,
        "mode": mode,
        "index": ELASTIC_INDEX,
        "results": hits,
    }