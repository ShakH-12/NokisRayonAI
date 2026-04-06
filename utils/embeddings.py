"""
embeddings.py
Превращает текст в вектор (список чисел) через Gemini Embedding API.
Два разных task_type для лучшего качества поиска.
"""

from google import genai
from google.genai import types

from utils.config import GEMINI_API_KEY, EMBED_MODEL


def _get_client() -> genai.Client:
    return genai.Client(api_key=GEMINI_API_KEY)


def embed_document(text: str) -> list[float]:
    """
    Эмбеддинг для документа при индексации (ingest).
    task_type=RETRIEVAL_DOCUMENT — оптимизирован для хранения.
    """
    client = _get_client()
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
    )
    return result.embeddings[0].values


def embed_query(text: str) -> list[float]:
    """
    Эмбеддинг для поискового запроса пользователя.
    task_type=RETRIEVAL_QUERY — оптимизирован для поиска.
    """
    client = _get_client()
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    return result.embeddings[0].values
