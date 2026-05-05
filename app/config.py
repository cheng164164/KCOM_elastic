import os
from dotenv import load_dotenv

load_dotenv()

# Elasticsearch
ELASTIC_URL = os.getenv("ELASTIC_URL", "")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY", "")
ELASTIC_USERNAME = os.getenv("ELASTIC_USERNAME", "")
ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD", "")
ELASTIC_TIMEOUT = int(os.getenv("ELASTIC_TIMEOUT", "30"))

CONTENT_INDEX = os.getenv("CONTENT_INDEX", os.getenv("ELASTIC_INDEX", "search-kx_content_en-us"))
PARTS_INDEX = os.getenv("PARTS_INDEX", "magento2_product_1_v13")

CONTENT_SEARCH_FIELDS = [
    field.strip()
    for field in os.getenv(
        "SEARCH_FIELDS",
        "combined_field,body_content,meta_description,kx_description,kx_title,body,title,meta_keywords, headings",
    ).split(",")
    if field.strip()
]

PARTS_SEARCH_FIELDS = [
    field.strip()
    for field in os.getenv(
        "PARTS_SEARCH_FIELDS",
        "kx_title,short_description,description,combined_field,level_one_commodity_code",
    ).split(",")
    if field.strip()
]

CONTENT_RETURN_ALL_FIELDS = os.getenv("CONTENT_RETURN_ALL_FIELDS", "false").lower() == "true"
PARTS_RETURN_ALL_FIELDS = os.getenv("PARTS_RETURN_ALL_FIELDS", "true").lower() == "true"

TOP_K = int(os.getenv("TOP_K", "5"))
MAX_CHARS_PER_FIELD = int(os.getenv("MAX_CHARS_PER_FIELD", "10000"))

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "")
