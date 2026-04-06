"""
responder.py
Ищет релевантные чанки и генерирует ответ через Gemini.
Эту функцию вызывает Django view при вопросе пользователя.
"""

from pathlib import Path

from google import genai
from google.genai import types

from utils.config       import GEMINI_API_KEY, CHAT_MODEL, SYSTEM_PROMPT, TOP_K
from utils.vector_store import VectorStore


# Минимальный score для включения чанка в контекст.
# БЫЛО: брались все чанки подряд даже нерелевантные (score 0.3-0.4)
# СТАЛО: берём только действительно похожие (score >= 0.45)
MIN_SCORE = 0.45


def get_answer(
    question:     str,
    history:      list[dict] | None = None,
    top_k:        int = TOP_K,
) -> dict:
    """
    Принимает вопрос пользователя и (опционально) историю диалога.

    history — список словарей вида:
      [
        {"role": "user",  "text": "..."},
        {"role": "model", "text": "..."},
      ]

    Возвращает словарь:
    {
        "answer":   "текст ответа",
        "sources":  ["файл1.pdf", "файл2.docx"],
        "chunks":   [{ text, source, score }, ...]  ← для дебага
        "status":   "ok" | "empty_db" | "not_found"
    }
    """
    store = VectorStore()

    # 1. Проверяем что база не пустая
    if store.count() == 0:
        return {
            "answer":  "База знаний пуста. Сначала загрузите файлы.",
            "sources": [],
            "chunks":  [],
            "status":  "empty_db",
        }

    # 2. Ищем похожие чанки
    all_chunks = store.search(question, top_k=top_k)

    # ФИКС: фильтруем чанки с низким score — они добавляют шум в контекст
    chunks = [c for c in all_chunks if c["score"] >= MIN_SCORE]

    # Если после фильтрации ничего нет — берём лучший из того что есть
    # (на случай если в базе мало данных и все score низкие)
    if not chunks and all_chunks:
        chunks = all_chunks[:2]

    if not chunks:
        return {
            "answer":  "В загруженных документах не найдено информации по этому вопросу.",
            "sources": [],
            "chunks":  [],
            "status":  "not_found",
        }

    # 3. Собираем контекст — ФИКС: убрали score из контекста чтобы не путать модель
    context_parts = []
    for i, c in enumerate(chunks, 1):
        filename = Path(c['source']).name
        context_parts.append(
            f"[Фрагмент {i} | Файл: {filename}]\n{c['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    # 4. Сообщение пользователя с контекстом
    user_message = (
        f"Контекст из документов:\n{context}\n\n"
        f"Вопрос: {question}"
    )

    # 5. Строим contents с историей (multi-turn)
    contents = []
    for msg in (history or []):
        contents.append(
            types.Content(
                role=msg["role"],
                parts=[types.Part(text=msg["text"])],
            )
        )
    contents.append(
        types.Content(role="user", parts=[types.Part(text=user_message)])
    )

    # 6. Запрос к Gemini
    client   = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=CHAT_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,   # ФИКС: было 0.2 — снижаем для более точных ответов
            max_output_tokens=2048,
        ),
    )

    answer  = response.text
    sources = list({Path(c["source"]).name for c in chunks})

    return {
        "answer":  answer,
        "sources": sources,
        "chunks":  chunks,
        "status":  "ok",
    }