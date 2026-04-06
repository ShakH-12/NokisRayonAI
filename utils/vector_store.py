"""
vector_store.py
Работает с ChromaDB: сохраняет чанки с векторами, ищет похожие.
"""

import hashlib
from pathlib import Path

import chromadb

from utils.config import DB_DIR, TOP_K
from utils.embeddings import embed_document, embed_query


class VectorStore:
    def __init__(self, db_dir: str = DB_DIR):
        """Открывает (или создаёт) ChromaDB коллекцию на диске."""
        self.chroma     = chromadb.PersistentClient(path=db_dir)
        self.collection = self.chroma.get_or_create_collection(
            name="rag_docs",
            metadata={"hnsw:space": "cosine"},
        )

    # ── Запись ────────────────────────────────────────────────
    def add_chunks(self, chunks: list[str], source: str) -> int:
        """
        Принимает список чанков и имя источника (путь к файлу).
        Считает эмбеддинг каждого чанка и сохраняет в БД.
        Возвращает количество добавленных чанков.
        """
        ids, vectors, docs, metas = [], [], [], []

        for i, chunk in enumerate(chunks):
            # Уникальный ID: md5 от (источник + индекс + начало текста)
            uid = hashlib.md5(f"{source}_{i}_{chunk[:50]}".encode()).hexdigest()
            ids.append(uid)
            vectors.append(embed_document(chunk))
            docs.append(chunk)
            metas.append({"source": source, "chunk_index": i})

        self.collection.upsert(
            ids=ids,
            embeddings=vectors,
            documents=docs,
            metadatas=metas,
        )
        return len(chunks)

    # ── Поиск ─────────────────────────────────────────────────
    def search(self, query: str, top_k: int = TOP_K) -> list[dict]:
        """
        Принимает текст запроса.
        Возвращает top_k самых похожих чанков в виде списка словарей:
          [{ text, source, chunk_index, score }, ...]
        """
        if self.collection.count() == 0:
            return []

        q_vector = embed_query(query)
        results  = self.collection.query(
            query_embeddings=[q_vector],
            n_results=min(top_k, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "text":        doc,
                "source":      meta["source"],
                "chunk_index": meta["chunk_index"],
                "score":       round(1 - dist, 3),  # cosine similarity: 1 = идентично
            })
        return output

    # ── Удаление по источнику ─────────────────────────────────
    def delete_by_source(self, source: str) -> int:
        """
        Удаляет все чанки из конкретного файла.
        Полезно когда файл переиндексируется или удаляется.
        Возвращает количество удалённых записей.
        """
        results = self.collection.get(
            where={"source": source},
            include=["documents"],
        )
        ids = results.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)

    # ── Статистика ────────────────────────────────────────────
    def count(self) -> int:
        """Общее количество чанков в базе."""
        return self.collection.count()
