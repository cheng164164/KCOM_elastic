from typing import Any, Dict, List, Tuple, Union
import json
import re

from app.config import (
    AZURE_OPENAI_CHAT_DEPLOYMENT,
    CONTENT_INDEX,
    CONTENT_INDEXES,
    CONTENT_PHRASE_FIELDS,
    CONTENT_RETURN_ALL_FIELDS,
    CONTENT_RRF_RANK_CONSTANT,
    CONTENT_RRF_RANK_WINDOW_SIZE,
    CONTENT_SEARCH_FIELDS,
    CONTENT_SEARCH_MODE,
    CONTENT_SEMANTIC_FIELD,
    MAX_CHARS_PER_FIELD,
    PARTS_INDEX,
    PARTS_RETURN_ALL_FIELDS,
    PARTS_SEARCH_FIELDS,
    TOP_K,
)
from app.elastic_client import get_es_client
from app.openai_client import get_azure_openai_client


es = get_es_client()

PARTS_EFFECTIVE_SEARCH_FIELDS = list(dict.fromkeys(PARTS_SEARCH_FIELDS))


def safe_text(value: Any, max_chars: int = MAX_CHARS_PER_FIELD) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " | ".join(str(v) for v in value)
    elif isinstance(value, dict):
        try:
            value = json.dumps(value, ensure_ascii=False)
        except Exception:
            value = str(value)
    text = str(value).strip()
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "..."
    return text


def get_return_fields(route: str) -> Union[List[str], bool]:
    if route == "parts":
        return True if PARTS_RETURN_ALL_FIELDS else PARTS_EFFECTIVE_SEARCH_FIELDS
    return True if CONTENT_RETURN_ALL_FIELDS else CONTENT_SEARCH_FIELDS


def classify_query_route(question: str) -> Tuple[str, str]:
    aoai_client = get_azure_openai_client()
    system_prompt = (
        "You route user questions to one of two search routes. "
        "Return only valid JSON with keys route and reason. "
        "Allowed route values: parts, content. "
        "Choose 'parts' when the question is about part numbers, SKUs, replacement parts, "
        "part recommendations, part categories, parts selection, or part lookup. "
        "Choose 'content' for general Komatsu website content, machine information, brochures, "
        "features, manuals, specifications, documentation, attached documents, or general informational questions."
    )

    try:
        response = aoai_client.chat.completions.create(
            model=AZURE_OPENAI_CHAT_DEPLOYMENT,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        route = str(data.get("route", "content")).strip().lower()
        if route not in {"parts", "content"}:
            route = "content"
        reason = str(data.get("reason", "LLM route selection")).strip()
        return route, reason or "LLM route selection"
    except Exception as exc:
        return "content", f"LLM routing failed; defaulted to content: {exc}"


def is_probable_part_number(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9]+(?:[- ][A-Za-z0-9]+)+", text))


def build_content_lexical_should(question: str) -> List[Dict[str, Any]]:
    should_clauses: List[Dict[str, Any]] = [
        {
            "multi_match": {
                "query": question,
                "fields": CONTENT_SEARCH_FIELDS,
                "type": "most_fields",
                "operator": "and",
            }
        }
    ]

    for field in CONTENT_PHRASE_FIELDS:
        if field in CONTENT_SEARCH_FIELDS:
            should_clauses.append(
                {
                    "match_phrase": {
                        field: {
                            "query": question,
                        }
                    }
                }
            )

    should_clauses.append(
        {
            "multi_match": {
                "query": question,
                "fields": CONTENT_SEARCH_FIELDS,
                "type": "best_fields",
                "operator": "or",
                "fuzziness": "AUTO",
            }
        }
    )

    return should_clauses


def build_content_search_query(question: str, top_k: int) -> Dict[str, Any]:
    """
    Regular full-text search.

    This is intentionally kept close to the original implementation. It can be used
    for one or more content indexes, but the recommended multi-index content mode
    for now is `rrf`.
    """
    return {
        "size": top_k,
        "query": {
            "bool": {
                "should": build_content_lexical_should(question),
                "minimum_should_match": 1,
            }
        },
        "_source": get_return_fields("content"),
    }


def build_content_hybrid_query(question: str, top_k: int) -> Dict[str, Any]:
    """
    Placeholder for the original hybrid behavior: full-text + semantic in a bool query.

    Use this mode only when every content index in CONTENT_INDEXES has the semantic
    field configured, for example body_content_semantic as semantic_text. Until then,
    prefer CONTENT_SEARCH_MODE=rrf or full_text.
    """
    lexical_should = build_content_lexical_should(question)

    return {
        "size": top_k,
        "query": {
            "bool": {
                "should": [
                    {
                        "bool": {
                            "should": lexical_should,
                            "minimum_should_match": 1,
                        }
                    },
                    {
                        "semantic": {
                            "field": CONTENT_SEMANTIC_FIELD,
                            "query": question,
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        },
        "_source": get_return_fields("content"),
    }


def build_content_rrf_query(question: str, top_k: int) -> Dict[str, Any]:
    """
    Elasticsearch RRF search using full-text lexical retrievers only.

    This mode searches all CONTENT_INDEXES in one Elasticsearch request. It does not
    use semantic/vector retrieval, so it is safe while one content index has semantic
    vectors and another one does not.
    """
    phrase_should = [
        {
            "match_phrase": {
                field: {
                    "query": question,
                }
            }
        }
        for field in CONTENT_PHRASE_FIELDS
        if field in CONTENT_SEARCH_FIELDS
    ]

    retrievers: List[Dict[str, Any]] = [
        {
            "standard": {
                "query": {
                    "multi_match": {
                        "query": question,
                        "fields": CONTENT_SEARCH_FIELDS,
                        "type": "most_fields",
                        "operator": "and",
                    }
                }
            }
        },
        {
            "standard": {
                "query": {
                    "multi_match": {
                        "query": question,
                        "fields": CONTENT_SEARCH_FIELDS,
                        "type": "best_fields",
                        "operator": "or",
                        "fuzziness": "AUTO",
                    }
                }
            }
        },
    ]

    if phrase_should:
        retrievers.append(
            {
                "standard": {
                    "query": {
                        "bool": {
                            "should": phrase_should,
                            "minimum_should_match": 1,
                        }
                    }
                }
            }
        )

    return {
        "size": top_k,
        "retriever": {
            "rrf": {
                "retrievers": retrievers,
                "rank_constant": CONTENT_RRF_RANK_CONSTANT,
                "rank_window_size": max(CONTENT_RRF_RANK_WINDOW_SIZE, top_k),
            }
        },
        "_source": get_return_fields("content"),
    }


def build_parts_search_query(question: str, top_k: int) -> Dict[str, Any]:
    should_clauses: List[Dict[str, Any]] = [
        {
            "multi_match": {
                "query": question,
                "fields": PARTS_EFFECTIVE_SEARCH_FIELDS,
                "type": "most_fields",
                "operator": "and",
            }
        }
    ]

    for field in ["short_description", "combined_field", "description"]:
        if field in PARTS_EFFECTIVE_SEARCH_FIELDS:
            should_clauses.append(
                {
                    "match_phrase": {
                        field: {
                            "query": question,
                        }
                    }
                }
            )

    should_clauses.append(
        {
            "multi_match": {
                "query": question,
                "fields": PARTS_EFFECTIVE_SEARCH_FIELDS,
                "type": "best_fields",
                "operator": "or",
                "fuzziness": "AUTO",
            }
        }
    )

    if is_probable_part_number(question):
        exact_term_fields = ["sku", "kx_title", "url_key"]
        for field in exact_term_fields:
            should_clauses.append(
                {
                    "term": {
                        field: question.lower() if field == "url_key" else question
                    }
                }
            )

    return {
        "size": top_k,
        "query": {
            "bool": {
                "should": should_clauses,
                "minimum_should_match": 1,
            }
        },
        "_source": get_return_fields("parts"),
    }


def build_query(question: str, top_k: int, route: str) -> Dict[str, Any]:
    if route == "parts":
        return build_parts_search_query(question, top_k)

    if CONTENT_SEARCH_MODE == "hybrid":
        return build_content_hybrid_query(question, top_k)
    if CONTENT_SEARCH_MODE == "rrf":
        return build_content_rrf_query(question, top_k)
    return build_content_search_query(question, top_k)


def format_hit(hit: Dict[str, Any], route: str) -> Dict[str, Any]:
    source = hit.get("_source", {}) or {}
    item = {
        "score": hit.get("_score"),
        "id": hit.get("_id"),
        "index": hit.get("_index"),
        "fields": {},
    }

    if route == "parts" and PARTS_RETURN_ALL_FIELDS:
        for field, value in source.items():
            item["fields"][field] = safe_text(value)
        return item

    if route == "content" and CONTENT_RETURN_ALL_FIELDS:
        for field, value in source.items():
            item["fields"][field] = safe_text(value)
        return item

    fields_to_return = CONTENT_SEARCH_FIELDS if route == "content" else PARTS_EFFECTIVE_SEARCH_FIELDS
    for field in fields_to_return:
        # Ignore field boost suffixes if user ever configures fields like title^2.
        plain_field = field.split("^", 1)[0]
        if plain_field in source:
            item["fields"][plain_field] = safe_text(source.get(plain_field))
    return item


def build_context(hits: List[Dict[str, Any]], route: str) -> str:
    if not hits:
        return "No relevant documents were found."

    lines: List[str] = []
    for i, hit in enumerate(hits, start=1):
        fields = hit.get("fields", {})
        lines.append(f"[Document {i}]")
        if hit.get("index"):
            lines.append(f"index: {hit.get('index')}")

        if route == "parts":
            url = fields.get("url") or fields.get("url_key") or ""
            lines.append(f"url: {url}")

            preferred_order = [
                "sku",
                "kx_title",
                "short_description",
                "description",
                "combined_field",
                "level_one_commodity_code",
                "level_three_commodity_code",
                "brand",
                "sales_hierarchy",
                "status_value",
                "is_out_of_stock",
            ]
            seen = set()
            for key in preferred_order:
                value = fields.get(key)
                if value:
                    lines.append(f"{key}: {value}")
                    seen.add(key)

            for key, value in fields.items():
                if key not in seen and value:
                    lines.append(f"{key}: {value}")
        else:
            for key, value in fields.items():
                if value:
                    lines.append(f"{key}: {value}")

        lines.append("")
    return "\n".join(lines).strip()


def generate_answer(question: str, context: str, route: str) -> str:
    aoai_client = get_azure_openai_client()

    if route == "parts":
        system_prompt = (
            "You are a helpful Komatsu parts assistant. "
            "Use only the provided Elasticsearch search results. "
            "Your goal is to help the user narrow down part selection and recommend the most relevant parts they may need. "
            "Do not claim part compatibility unless it is explicitly stated in the search results. "
            "When presenting a part, always start with the URL if available. "
            "Summarize the top relevant results with key information, including part number, part name, engineering or product descriptions, "
            "category or commodity details, and any useful status or stock details if present. "
            "If the search results are insufficient, say so clearly. Keep the answer concise, factual, and organized."
        )
    else:
        system_prompt = (
            "You are a helpful product assistant. "
            "Answer only from the provided Elasticsearch search results. "
            "If the search results do not contain enough information, say so clearly. "
            "Keep answers concise and factual."
        )

    response = aoai_client.chat.completions.create(
        model=AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system_prompt},
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

    return (response.choices[0].message.content or "").strip()


def get_content_search_indexes() -> List[str]:
    return CONTENT_INDEXES or [CONTENT_INDEX]


def get_content_search_index_name() -> str:
    return ",".join(get_content_search_indexes())


def answer_question(question: str, top_k: int = None) -> Dict[str, Any]:
    route, route_reason = classify_query_route(question)

    effective_top_k = top_k or TOP_K
    query_body = build_query(
        question=question,
        top_k=effective_top_k,
        route=route,
    )
    searched_indexes = [PARTS_INDEX] if route == "parts" else get_content_search_indexes()
    index_name = ",".join(searched_indexes)

    response = es.search(index=index_name, body=query_body)

    raw_hits = response.get("hits", {}).get("hits", [])
    hits = [format_hit(hit, route) for hit in raw_hits]
    context = build_context(hits, route)

    if not hits:
        answer = f"I could not find relevant information in the Elasticsearch {route} index."
    else:
        answer = generate_answer(question=question, context=context, route=route)

    return {
        "question": question,
        "answer": answer,
        "mode": CONTENT_SEARCH_MODE if route == "content" else "parts_full_text",
        "route": route,
        "route_reason": route_reason,
        "index": index_name,
        "searched_indexes": searched_indexes,
        "index_display": ", ".join(searched_indexes),
        "results": hits,
    }
