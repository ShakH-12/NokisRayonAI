"""
ingestor.py
Пайплайн: файл → текст → чанки → векторы → ChromaDB.
Эту функцию вызывает Django view при загрузке файла.
"""

from utils.loaders     import load_file
from utils.chunker     import split_text
from utils.vector_store import VectorStore


def ingest_file(file_path: str, reindex: bool = False) -> dict:
    """
    Принимает путь к файлу (уже сохранённому на диске).
    Загружает, нарезает, индексирует в ChromaDB.

    reindex=True → сначала удалит старые чанки этого файла,
                   потом добавит заново (нужно при повторной загрузке).

    Возвращает словарь с результатом — его можно сразу отдать в Response():
    {
        "source":      "путь/к/файлу.pdf",
        "chunks_added": 42,
        "status":      "ok"
    }
    """
    store = VectorStore()

    # Удалить старую версию если нужно
    if reindex:
        deleted = store.delete_by_source(file_path)

    # 1. Читаем файл → получаем текст
    text = load_file(file_path)
    if not text:
        return {
            "source": file_path,
            "chunks_added": 0,
            "status": "error",
            "detail": "Файл пустой или не удалось прочитать",
        }

    # 2. Нарезаем на чанки
    chunks = split_text(text)

    # 3. Сохраняем в ChromaDB с эмбеддингами
    count = store.add_chunks(chunks, source=file_path)

    return {
        "source":       file_path,
        "chunks_added": count,
        "status":       "ok",
    }
