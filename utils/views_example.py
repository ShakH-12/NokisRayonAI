"""
views.py  (пример — показывает как использовать utils в Django)
────────────────────────────────────────────────────────────────
Два эндпоинта:
  POST /api/upload/   — загружает файл и индексирует
  POST /api/ask/      — принимает вопрос, возвращает ответ
"""

import os
from rest_framework.views     import APIView
from rest_framework.response  import Response
from rest_framework           import status

from utils.ingestor  import ingest_file
from utils.responder import get_answer


# ── 1. Загрузка файла ─────────────────────────────────────────
class UploadFileView(APIView):
    """
    POST /api/upload/
    Body: multipart/form-data
      file    — файл любого типа
      reindex — (опционально) "true" если переиндексировать
    """

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"detail": "Файл не передан"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Сохраняем файл на диск (в media/)
        save_dir  = "media/rag_uploads"
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, file.name)

        with open(file_path, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)

        # Индексируем через utils
        reindex = request.data.get("reindex", "false").lower() == "true"
        result  = ingest_file(file_path, reindex=reindex)

        if result["status"] == "error":
            return Response(result, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response(result, status=status.HTTP_201_CREATED)


# ── 2. Ответ на вопрос ────────────────────────────────────────
class AskView(APIView):
    """
    POST /api/ask/
    Body: application/json
      {
        "question": "Что написано в договоре?",
        "history":  [                           ← (опционально)
          {"role": "user",  "text": "..."},
          {"role": "model", "text": "..."}
        ]
      }
    """

    def post(self, request):
        question = request.data.get("question", "").strip()
        if not question:
            return Response(
                {"detail": "Поле question обязательно"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        history = request.data.get("history", [])

        # Получаем ответ через utils
        result = get_answer(question, history=history)

        return Response(result, status=status.HTTP_200_OK)
