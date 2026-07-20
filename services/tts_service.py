import requests
import os
import uuid
from datetime import datetime

LANGUAGE_CODES = {
    "tamil": "ta-IN",
    "hindi": "hi-IN",
    "telugu": "te-IN",
    "kannada": "kn-IN",
    "malayalam": "ml-IN",
    "english": "en-IN"
}

VOICE_NAMES = {
    "tamil": "ta-IN-Standard-A",
    "hindi": "hi-IN-Standard-A",
    "telugu": "te-IN-Standard-A",
    "kannada": "kn-IN-Standard-A",
    "malayalam": "ml-IN-Standard-A",
    "english": "en-IN-Standard-A"
}

class TTSService:

    @staticmethod
    def generate_audio(text: str, language: str = "english") -> str:
        os.makedirs("static/avatar_audio", exist_ok=True)

        api_key = os.getenv("GOOGLE_TTS_API_KEY")
        lang_code = LANGUAGE_CODES.get(language, "en-IN")
        voice_name = VOICE_NAMES.get(language, "en-IN-Standard-A")

        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": lang_code,
                "name": voice_name,
                "ssmlGender": "FEMALE"
            },
            "audioConfig": {"audioEncoding": "MP3"}
        }

        response = requests.post(
            f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}",
            json=payload
        )
        response.raise_for_status()
        audio_content = response.json()["audioContent"]

        import base64
        filename = f"{uuid.uuid4()}.mp3"
        filepath = f"static/avatar_audio/{filename}"
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(audio_content))

        return f"/static/avatar_audio/{filename}"

    @staticmethod
    def build_subtitle_schedule(text: str, audio_url: str) -> list:
        # Split text into chunks of ~8 words
        # Estimate timing — average speaking rate ~150 words per minute
        words = text.split()
        chunks = []
        chunk_size = 8
        words_per_second = 2.5

        current_time = 0
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            duration = len(words[i:i+chunk_size]) / words_per_second
            chunks.append({
                "from": round(current_time, 2),
                "to": round(current_time + duration, 2),
                "text": chunk
            })
            current_time += duration

        return chunks