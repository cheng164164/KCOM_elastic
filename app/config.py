import os
from dotenv import load_dotenv

load_dotenv()

# Elasticsearch
ELASTIC_URL = os.getenv("ELASTIC_URL", "")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY", "")
ELASTIC_USERNAME = os.getenv("ELASTIC_USERNAME", "")
ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD", "")
ELASTIC_INDEX = os.getenv("ELASTIC_INDEX", "search-kx_content_en-us")
ELASTIC_TIMEOUT = int(os.getenv("ELASTIC_TIMEOUT", "30"))

SEARCH_FIELDS = [
    field.strip()
    for field in os.getenv(
        "SEARCH_FIELDS",
        "name,description,short_description,title,content,sku,category"
    ).split(",")
    if field.strip()
]

RETURN_FIELDS = [
    field.strip()
    for field in os.getenv(
        "RETURN_FIELDS",
        "name,sku,description,short_description,category,price,url"
    ).split(",")
    if field.strip()
]

TOP_K = int(os.getenv("TOP_K", "5"))
MAX_CHARS_PER_FIELD = int(os.getenv("MAX_CHARS_PER_FIELD", "10000"))

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "")
