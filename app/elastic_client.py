from elasticsearch import Elasticsearch
from app.config import (
    ELASTIC_URL,
    ELASTIC_API_KEY,
    ELASTIC_USERNAME,
    ELASTIC_PASSWORD,
    ELASTIC_TIMEOUT,
)


def get_es_client() -> Elasticsearch:
    if ELASTIC_API_KEY:
        return Elasticsearch(
            ELASTIC_URL,
            api_key=ELASTIC_API_KEY,
            request_timeout=ELASTIC_TIMEOUT,
        )

    if ELASTIC_USERNAME and ELASTIC_PASSWORD:
        return Elasticsearch(
            ELASTIC_URL,
            basic_auth=(ELASTIC_USERNAME, ELASTIC_PASSWORD),
            request_timeout=ELASTIC_TIMEOUT,
        )

    return Elasticsearch(
        ELASTIC_URL,
        request_timeout=ELASTIC_TIMEOUT,
    )

def get_searchable_fields(es: Elasticsearch, index: str):
    """
    Auto-detect searchable fields from index mapping
    """
    mapping = es.indices.get_mapping(index=index)

    properties = mapping[index]["mappings"].get("properties", {})

    searchable_fields = []

    def extract_fields(props, prefix=""):
        for field, value in props.items():
            field_path = f"{prefix}.{field}" if prefix else field

            field_type = value.get("type")

            # Include text + keyword fields
            if field_type in ["text", "keyword"]:
                searchable_fields.append(field_path)

            # Handle nested/object fields
            if "properties" in value:
                extract_fields(value["properties"], field_path)

    extract_fields(properties)

    return searchable_fields

def debug_es_connection():
    """Read-only diagnostics. Run: python -m app.elastic_client"""
    import os
    from urllib.parse import urlsplit
    from elasticsearch import AuthenticationException, AuthorizationException, ApiError

    def check(label, operation):
        print(f"\n[TEST] {label}")
        try:
            result = operation()
            print(f"[PASS] {label}")
            return True, result
        except AuthenticationException as exc:
            print(f"[FAIL] HTTP 401: Elasticsearch rejected the credentials. {exc.__class__.__name__}")
        except AuthorizationException as exc:
            print(f"[FAIL] HTTP 403: Credentials accepted but permissions insufficient. {exc.__class__.__name__}")
        except ApiError as exc:
            print(f"[FAIL] Elasticsearch HTTP {exc.status_code}: {exc.__class__.__name__}")
        except Exception as exc:
            print(f"[FAIL] {type(exc).__name__}: {str(exc)[:300]}")
        return False, None

    from app.config import CONTENT_INDEXES
    print("=== Elasticsearch connection diagnostics ===")
    parsed = urlsplit(ELASTIC_URL)
    print("Endpoint host:", parsed.hostname or "MISSING")
    print("Endpoint scheme:", parsed.scheme or "MISSING")
    print("Authentication mode:", "API key" if ELASTIC_API_KEY else
          "Basic auth" if ELASTIC_USERNAME and ELASTIC_PASSWORD else "NONE")
    print("API key configured:", bool(ELASTIC_API_KEY))
    print("Timeout:", ELASTIC_TIMEOUT)
    print("Indexes:", ", ".join(CONTENT_INDEXES))
    if not ELASTIC_URL or not (ELASTIC_API_KEY or (ELASTIC_USERNAME and ELASTIC_PASSWORD)):
        print("[STOP] Missing endpoint or credentials. Check .env and working directory.")
        return
    try:
        es = get_es_client()
    except Exception as exc:
        print(f"[STOP] Client construction failed: {type(exc).__name__}: {exc}")
        return
    try:
        ok, identity = check("Authenticate", lambda: es.security.authenticate())
        if not ok:
            print("[STOP] Resolve authentication before testing indexes.")
            return
        print("Authenticated username:", identity.get("username", "unknown"))
        ok, info = check("Cluster information", lambda: es.info())
        if ok:
            print("Cluster:", info.get("cluster_name", "unknown"))
            print("Version:", info.get("version", {}).get("number", "unknown"))
        for index in CONTENT_INDEXES:
            ok, result = check(f"Index existence: {index}", lambda index=index: es.indices.exists(index=index))
            if not ok:
                continue
            if not bool(result):
                print(f"[WARN] Index '{index}' not found or not visible to this credential.")
                continue
            print("Index exists: yes")
            ok, result = check(f"Read one document: {index}", lambda index=index: es.search(
                index=index, size=1, query={"match_all": {}}, _source=False,
            ))
            if ok:
                print("Returned hits:", len(result.get("hits", {}).get("hits", [])))
        print("\n[DONE] Diagnostics finished. No data was modified.")
    finally:
        es.close()


if __name__ == "__main__":
    debug_es_connection()
