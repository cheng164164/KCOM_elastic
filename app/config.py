import os
from dotenv import load_dotenv

load_dotenv()


def _csv_env(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# Elasticsearch
ELASTIC_URL = os.getenv("ELASTIC_URL", "")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY", "")
ELASTIC_USERNAME = os.getenv("ELASTIC_USERNAME", "")
ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD", "")
ELASTIC_TIMEOUT = int(os.getenv("ELASTIC_TIMEOUT", "30"))

# Content indexes
# CONTENT_INDEX is kept for backward compatibility and as the default first content index.
CONTENT_INDEX = os.getenv("CONTENT_INDEX", os.getenv("ELASTIC_INDEX", "search-kx_content_en-us"))
CONTENT_INDEXES = _csv_env(
    "CONTENT_INDEXES",
    f"{CONTENT_INDEX},search-kx_assets",
)
# CONTENT_INDEXES =None


# Search mode for content route only.
# Supported values:
# - full_text: regular Elasticsearch full-text query
# - hybrid: placeholder for your original full-text + semantic bool query; use only when all content indexes have semantic fields
# - rrf: Elasticsearch RRF using full-text lexical retrievers only across CONTENT_INDEXES
CONTENT_SEARCH_MODE = os.getenv("CONTENT_SEARCH_MODE", "rrf").strip().lower()
if CONTENT_SEARCH_MODE not in {"full_text", "hybrid", "rrf"}:
    CONTENT_SEARCH_MODE = "rrf"

CONTENT_SEMANTIC_FIELD = os.getenv("CONTENT_SEMANTIC_FIELD", "body_content_semantic")
CONTENT_RRF_RANK_CONSTANT = int(os.getenv("CONTENT_RRF_RANK_CONSTANT", "20"))
CONTENT_RRF_RANK_WINDOW_SIZE = int(os.getenv("CONTENT_RRF_RANK_WINDOW_SIZE", "50"))

PARTS_INDEX = os.getenv("PARTS_INDEX", "magento2_product_1_v14")

CONTENT_SEARCH_FIELDS = _csv_env(
    "SEARCH_FIELDS",
    "combined_field,body_content,meta_description,kx_description,kx_title,body,title,meta_keywords,headings",
)

CONTENT_PHRASE_FIELDS = _csv_env(
    "CONTENT_PHRASE_FIELDS",
    "combined_field, kx_description, kx_title"
)

PARTS_SEARCH_FIELDS = _csv_env(
    "PARTS_SEARCH_FIELDS",
    "kx_title,short_description,description,combined_field,level_one_commodity_code",
)

CONTENT_RETURN_ALL_FIELDS = os.getenv("CONTENT_RETURN_ALL_FIELDS", "false").lower() == "true"
PARTS_RETURN_ALL_FIELDS = os.getenv("PARTS_RETURN_ALL_FIELDS", "true").lower() == "true"

TOP_K = int(os.getenv("TOP_K", "6"))
MAX_CHARS_PER_FIELD = int(os.getenv("MAX_CHARS_PER_FIELD", "10000"))

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "")
