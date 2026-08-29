import os
import sys
import re
import requests
import google.generativeai as genai
from dotenv import load_dotenv

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
# Voz predeterminada en español (Laura: FGY2WhTYpPnrIDTdsKH5 o Sarah: EXAVITQu4vr4xnSDxMaL)
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "FGY2WhTYpPnrIDTdsKH5").strip()

def limpiar_texto_para_voz(texto: str) -> str:
    """Elimina formato Markdown, enlaces y caracteres especiales para una locución natural."""
    if not texto:
        return ""
    # Quitar negritas y cursivas (**texto**, *texto*)
    limpio = re.sub(r"\*\*([^*]+)\*\*", r"\1", texto)
    limpio = re.sub(r"\*([^*]+)\*", r"\1", limpio)
    limpio = re.sub(r"_([^_]+)_", r"\1", limpio)
    # Quitar URLs
    limpio = re.sub(r"https?://\S+", "nuestras redes sociales", limpio)
    # Quitar viñetas o listas (- elemento)
    limpio = re.sub(r"^\s*[-*•]\s+", "", limpio, flags=re.MULTILINE)
    # Normalizar espacios
    limpio = re.sub(r"\s+", " ", limpio).strip()
    return limpio

VOZ_RESPALDO_GRATUITA = "FGY2WhTYpPnrIDTdsKH5"  # Laura (Predeterminada gratuita)

def generar_audio_elevenlabs(texto: str, voice_id: str = None) -> bytes | None:
    """
    Genera audio MP3 ultra realista usando la API de ElevenLabs.
    Si la voz configurada requiere plan de pago en ElevenLabs, utiliza automáticamente la voz de respaldo.
    """
    if not ELEVENLABS_API_KEY:
        return None

    vid = voice_id or ELEVENLABS_VOICE_ID
    texto_locucion = limpiar_texto_para_voz(texto)
    if not texto_locucion:
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": texto_locucion,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=12)
        if response.status_code == 200 and response.content:
            print(f"[ELEVENLABS]: Audio generado con éxito ({len(response.content)} bytes).")
            return response.content
        elif response.status_code == 402 and vid != VOZ_RESPALDO_GRATUITA:
            print(f"[ELEVENLABS 402]: La voz {vid} requiere plan de pago. Usando voz de respaldo gratuita ({VOZ_RESPALDO_GRATUITA})...")
            return generar_audio_elevenlabs(texto, voice_id=VOZ_RESPALDO_GRATUITA)
        else:
            print(f"[ELEVENLABS ERROR {response.status_code}]: {response.text[:120]}")
            return None
    except Exception as e:
        print(f"[ELEVENLABS EXCEPCION]: {e}")
        return None

def transcribir_audio_gemini(audio_bytes: bytes, mime_type: str = "audio/mp4") -> str:
    """
    Utiliza Gemini para escuchar y transcribir directamente el audio enviado por el cliente.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not audio_bytes:
        return ""
    
    try:
        genai.configure(api_key=api_key)
        modelo = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = (
            "Transcribe el contenido exacto de este mensaje de audio en español. "
            "Devuelve únicamente la transcripción exacta sin comentarios adicionales ni introducciones."
        )
        
        resultado = modelo.generate_content([
            {"mime_type": mime_type, "data": audio_bytes},
            prompt
        ])
        
        texto_transcrito = resultado.text.strip() if hasattr(resultado, "text") and resultado.text else ""
        print(f"[AUDIO TRANSCRITO POR GEMINI]: {texto_transcrito}")
        return texto_transcrito
    except Exception as e:
        print(f"[ERROR TRANSCRIBIENDO AUDIO]: {e}")
        return ""

