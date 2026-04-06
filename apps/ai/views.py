import uuid
import time
import struct

from django.shortcuts import render
from django.conf import settings
from rest_framework import permissions, parsers
from rest_framework.views import APIView
from rest_framework.response import Response

import os

from apps.ai.models import Prompts
from utils.ingestor import ingest_file
from utils.responder import get_answer

from google import genai
from google.genai import types


GEMINI_KEY = "AIzaSyCEf1DAHRhq108qkKqxaCAeN7phBxPfi1Y"
VOICE      = "Aoede"   # Варианты: Aoede, Charon, Fenrir, Kore, Puck
MAX_WAIT   = 30


def custom_404(request, exception):
    return render(request, '404.html')


class UploadFileView(APIView):
    parser_classes = (parsers.FormParser, parsers.MultiPartParser)
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        file = request.FILES['file']
        if not file:
            return Response({"detail": "Файл не передан"}, status=400)

        save_dir = "media/rag_uploads"
        os.makedirs(save_dir, exist_ok=True)
        filename = os.path.basename(file.name)
        file_path = os.path.join(save_dir, filename)

        with open(file_path, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)

        reindex = request.data.get("reindex", "false").lower() == "true"
        result = ingest_file(file_path, reindex=reindex)

        if result["status"] == "error":
            return Response(result, status=422)

        return Response(result, status=201)


class AskView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        question = request.data.get("question", "").strip()
        if not question:
            return Response({"detail": "Поле question обязательно"}, status=400)

        history = request.data.get("history", [])
        result = get_answer(question, history=history)

        return Response(result, status=200)


class ListCreatePrompt(APIView):
    queryset = Prompts.objects.all()

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


class VoiceChatView(APIView):
    parser_classes = (parsers.FormParser, parsers.MultiPartParser)

    def post(self, request):
        audio_file = request.FILES.get("audio")
        if not audio_file:
            return Response({"detail": "Поле audio обязательно"}, status=400)

        upload_dir = os.path.join(settings.MEDIA_ROOT, "voice_uploads")
        answer_dir = os.path.join(settings.MEDIA_ROOT, "answers")
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(answer_dir, exist_ok=True)

        uid       = uuid.uuid4().hex
        raw_path  = os.path.join(upload_dir, f"q_{uid}.webm")
        conv_path = os.path.join(upload_dir, f"q_{uid}.ogg")
        out_name  = f"answer_{uid}.wav"
        out_path  = os.path.join(answer_dir, out_name)

        # 1. Сохраняем входящее аудио
        with open(raw_path, "wb") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)

        # 2. Конвертируем webm → ogg (если pydub установлен)
        input_path = raw_path
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(raw_path)
            audio.export(conv_path, format="ogg")
            input_path = conv_path
        except Exception:
            input_path = raw_path

        # 3. Gemini: слушаем вопрос → генерируем текстовый ответ
        try:
            answer_text = self._ask_gemini(input_path)
        except Exception as e:
            return Response({"detail": f"Gemini error: {e}"}, status=502)
        finally:
            for p in [raw_path, conv_path]:
                try:
                    os.remove(p)
                except Exception:
                    pass

        # 4. Gemini TTS: озвучиваем ответ
        # Используем Gemini вместо edge_tts — работает через тот же API ключ,
        # не требует подключения к серверам Microsoft
        audio_url   = None
        tts_warning = None
        try:
            self._gemini_tts(answer_text, out_path)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                audio_url = f"{settings.MEDIA_URL}answers/{out_name}"
            else:
                tts_warning = "TTS вернул пустой файл"
        except Exception as e:
            tts_warning = str(e)
            try:
                os.remove(out_path)
            except Exception:
                pass

        response_data = {
            "answer_text": answer_text,
            "audio_url":   audio_url,
        }
        if tts_warning:
            response_data["tts_warning"] = tts_warning

        return Response(response_data, status=200)

    # ──────────────────────────────────────────────────────────
    def _ask_gemini(self, audio_path: str) -> str:
        """Отправляем аудио в Gemini Files API, получаем текстовый ответ."""
        client = genai.Client(api_key=GEMINI_KEY)
        myfile = None

        try:
            myfile = client.files.upload(file=audio_path)

            waited = 0
            while myfile.state.name == "PROCESSING":
                if waited >= MAX_WAIT:
                    raise ValueError("Timeout: файл слишком долго обрабатывается")
                time.sleep(2)
                waited += 2
                myfile = client.files.get(name=myfile.name)

            if myfile.state.name != "ACTIVE":
                raise ValueError(
                    f"Файл не обработан (state={myfile.state.name}). "
                    "Проверьте микрофон."
                )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    myfile,
                    (
                        "Тыңла аудионы. "
                        "1) Аудиодағы сөзді каракалпак кирилл жазуында жаз. "
                        "2) Сол сұраққа каракалпак тілінде (кирилл) жауап бер. "
                        "Тек жауап мәтінін ғана қайтар. "
                        "Егер аудио түсініксіз болса тек: 'Мен сизди тусинбедим' деп жаз."
                    )
                ]
            )
            return response.text.strip()

        finally:
            if myfile:
                try:
                    client.files.delete(name=myfile.name)
                except Exception:
                    pass

    def _gemini_tts(self, text: str, output_path: str):
        """
        Синтез речи через Gemini TTS.
        Возвращает PCM аудио (L16, 24kHz, mono) — упаковываем в WAV.
        Не требует edge_tts и подключения к Microsoft.
        """
        client = genai.Client(api_key=GEMINI_KEY)

        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=VOICE,
                        )
                    )
                ),
            ),
        )

        # Gemini TTS отдаёт сырые PCM байты (L16, 24000 Hz, mono)
        audio_data = response.candidates[0].content.parts[0].inline_data.data

        # Оборачиваем PCM в WAV заголовок
        self._pcm_to_wav(audio_data, output_path, sample_rate=24000)

    @staticmethod
    def _pcm_to_wav(pcm_data: bytes, output_path: str, sample_rate: int = 24000):
        """Упаковывает сырые PCM16 байты в валидный WAV файл."""
        num_channels    = 1
        bits_per_sample = 16
        byte_rate       = sample_rate * num_channels * bits_per_sample // 8
        block_align     = num_channels * bits_per_sample // 8
        data_size       = len(pcm_data)

        with open(output_path, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + data_size))
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write(struct.pack("<I", 16))
            f.write(struct.pack("<H", 1))             # PCM
            f.write(struct.pack("<H", num_channels))
            f.write(struct.pack("<I", sample_rate))
            f.write(struct.pack("<I", byte_rate))
            f.write(struct.pack("<H", block_align))
            f.write(struct.pack("<H", bits_per_sample))
            f.write(b"data")
            f.write(struct.pack("<I", data_size))
            f.write(pcm_data)