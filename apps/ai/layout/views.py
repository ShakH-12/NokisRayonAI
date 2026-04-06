"""
views.py  — Voice endpoint
POST /api/voice/
  Body: multipart { audio: <file> }
  Response: { "answer_text": "...", "audio_url": "/media/answers/answer_xyz.mp3" }
"""

import os
import time
import uuid
import asyncio

from django.conf import settings
from rest_framework.views    import APIView
from rest_framework.response import Response
from rest_framework          import status

from google import genai
import edge_tts


GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_KEY_HERE")
VOICE      = "kk-KZ-AigulNeural"   # казахский нейро-голос — лучше всего читает каракалпакский


class VoiceView(APIView):
    """
    POST /api/voice/
    Принимает аудио от пользователя → транскрибирует через Gemini
    → генерирует ответ → озвучивает через edge_tts → возвращает текст + mp3
    """

    def post(self, request):
        audio_file = request.FILES.get("audio")
        if not audio_file:
            return Response({"detail": "Поле audio обязательно"}, status=400)

        # ── 1. Сохраняем входящее аудио ──────────────────────
        upload_dir = os.path.join(settings.MEDIA_ROOT, "voice_uploads")
        answer_dir = os.path.join(settings.MEDIA_ROOT, "answers")
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(answer_dir, exist_ok=True)

        uid         = uuid.uuid4().hex
        # Браузер пишет webm, сохраняем как есть — Gemini поддерживает
        ext         = os.path.splitext(audio_file.name)[1] or ".webm"
        input_path  = os.path.join(upload_dir, f"q_{uid}{ext}")
        output_name = f"answer_{uid}.mp3"
        output_path = os.path.join(answer_dir, output_name)

        with open(input_path, "wb") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)

        # ── 2. Gemini: слушаем + отвечаем ────────────────────
        try:
            answer_text = self._ask_gemini(input_path)
        except Exception as e:
            return Response({"detail": f"Gemini error: {e}"}, status=502)
        finally:
            # Удаляем входящий файл после обработки
            try: os.remove(input_path)
            except: pass

        # ── 3. edge_tts: озвучиваем ответ ────────────────────
        try:
            asyncio.run(self._tts(answer_text, output_path))
        except Exception as e:
            return Response({"detail": f"TTS error: {e}"}, status=502)

        # ── 4. Возвращаем текст + URL аудио ──────────────────
        audio_url = f"{settings.MEDIA_URL}answers/{output_name}"
        return Response({
            "answer_text": answer_text,
            "audio_url":   audio_url,
        }, status=200)

    # ─────────────────────────────────────────────────────────
    def _ask_gemini(self, audio_path: str) -> str:
        client = genai.Client(api_key=GEMINI_KEY)

        # Загружаем файл в Gemini Files API
        myfile = client.files.upload(file=audio_path)

        # Ждём обработки
        while myfile.state.name == "PROCESSING":
            time.sleep(2)
            myfile = client.files.get(name=myfile.name)

        # Запрос: транскрибируй + ответь на каракалпакском
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                myfile,
                (
                    "Тыңла аудионы. Мынадай тапсырма: "
                    "1) Аудиодағы сөзді толық жаз. "
                    "2) Сол сұраққа каракалпак тілінде (кирилл) жауап бер. "
                    "Тек жауап мәтінін ғана қайтар, басқа ештеңе жазба. "
                    "Егер аудио түсініксіз болса: 'Мен сизди тусинбедим' деп жаз."
                )
            ]
        )

        # Удаляем файл из Gemini
        try: client.files.delete(name=myfile.name)
        except: pass

        return response.text.strip()

    async def _tts(self, text: str, output_path: str):
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(output_path)