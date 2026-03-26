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