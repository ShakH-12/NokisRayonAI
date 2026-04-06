"""
chunker.py
Нарезает большой текст на смысловые чанки для эмбеддингов.

БЫЛО: нарезка по символам — слова и предложения резались посередине.
СТАЛО: сначала разбиваем по абзацам/предложениям, потом собираем
       чанки нужного размера. Смысл на границах не теряется.
"""

import re
from utils.config import CHUNK_SIZE, CHUNK_OVERLAP


def _split_into_sentences(text: str) -> list[str]:
    """
    Разбивает текст на предложения по знакам препинания и переносам строк.
    Работает для русского, каракалпакского, узбекского текста.
    """
    # Сначала разбиваем по двойным переносам (абзацы)
    paragraphs = re.split(r'\n{2,}', text)

    sentences = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Внутри абзаца разбиваем по концу предложения
        # Поддерживаем . ! ? с учётом кавычек и скобок после
        parts = re.split(r'(?<=[.!?])\s+', para)
        for part in parts:
            part = part.strip()
            if part:
                sentences.append(part)

    return sentences


def split_text(
    text: str,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """
    Нарезает текст на чанки, уважая границы предложений.

    Алгоритм:
    1. Делим текст на предложения
    2. Набираем предложения в чанк пока не превысим size символов
    3. Когда чанк заполнен — сохраняем, откатываемся на overlap символов назад
       (берём последние предложения из предыдущего чанка)

    Так смысл на стыке чанков не теряется, и слова не режутся.
    """
    sentences = _split_into_sentences(text)
    if not sentences:
        return []

    chunks = []
    current_sentences = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        # Если одно предложение длиннее чанка — добавляем как есть
        if sentence_len >= size:
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_len = 0
            chunks.append(sentence)
            continue

        # Если добавление предложения превысит лимит — закрываем чанк
        if current_len + sentence_len + 1 > size and current_sentences:
            chunks.append(" ".join(current_sentences))

            # Откат: берём последние предложения для перекрытия
            overlap_sentences = []
            overlap_len = 0
            for s in reversed(current_sentences):
                if overlap_len + len(s) + 1 <= overlap:
                    overlap_sentences.insert(0, s)
                    overlap_len += len(s) + 1
                else:
                    break

            current_sentences = overlap_sentences
            current_len = overlap_len

        current_sentences.append(sentence)
        current_len += sentence_len + 1

    # Последний чанк
    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return [c.strip() for c in chunks if c.strip()]