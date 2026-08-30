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

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "sk_716bc086998261e19411bf6b540a397bb7d43c023d7f8204").strip()
# Voz configurada: Daniela - Vendedora (wBnAJRbu3cj93gnAm02O) con respaldo gratuito en Laura (FGY2WhTYpPnrIDTdsKH5)
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "wBnAJRbu3cj93gnAm02O").strip()
VOZ_RESPALDO_GRATUITA = "FGY2WhTYpPnrIDTdsKH5"  # Laura (Predeterminada gratuita)

MODELOS_AUDIO = [
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-flash-lite-latest"
]

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

def eliminar_audio_de_historial(history_item_id: str, api_key: str):
    """Elimina el registro de audio del historial de ElevenLabs para mantener la cuenta limpia y privada."""
    if not history_item_id or not api_key:
        return
    try:
        url = f"https://api.elevenlabs.io/v1/history/{history_item_id}"
        headers = {"xi-api-key": api_key}
        res = requests.delete(url, headers=headers, timeout=5)
        if res.status_code == 200:
            print(f"[ELEVENLABS HISTORIAL]: Audio {history_item_id} eliminado del historial con éxito.")
    except Exception:
        pass

def generar_audio_elevenlabs(texto: str, voice_id: str = None) -> bytes | None:
    """
    Genera audio MP3 ultra realista usando la API de ElevenLabs.
    Si la voz configurada requiere plan de pago en ElevenLabs, utiliza automáticamente la voz de respaldo.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY", ELEVENLABS_API_KEY).strip()
    if not api_key:
        return None

    vid = voice_id or os.getenv("ELEVENLABS_VOICE_ID", ELEVENLABS_VOICE_ID).strip()
    texto_locucion = limpiar_texto_para_voz(texto)
    if not texto_locucion:
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
    headers = {
        "xi-api-key": api_key,
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
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200 and response.content:
            print(f"[ELEVENLABS]: Audio generado con éxito ({len(response.content)} bytes).")
            # Borrar automáticamente del historial de ElevenLabs
            hid = response.headers.get("history-item-id")
            if hid:
                eliminar_audio_de_historial(hid, api_key)
            return response.content
        elif response.status_code in [401, 402, 403] and vid != VOZ_RESPALDO_GRATUITA:
            print(f"[ELEVENLABS {response.status_code}]: La voz {vid} requiere plan de pago. Usando voz de respaldo gratuita ({VOZ_RESPALDO_GRATUITA})...")
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
    
    genai.configure(api_key=api_key)
    prompt = (
        "Eres el transcriptor de audios de Novedades Rosymar. "
        "Escucha atentamente este audio y escribe exactamente lo que el cliente dice o pregunta. "
        "Devuelve solo el texto transcrito sin comentarios ni explicaciones adicionales."
    )

    mimes_a_probar = [mime_type, "audio/mp4", "audio/aac", "audio/m4a", "audio/mp3", "audio/ogg", "audio/wav"]
    
    for nombre_modelo in MODELOS_AUDIO:
        for mime in mimes_a_probar:
            try:
                modelo = genai.GenerativeModel(nombre_modelo)
                resultado = modelo.generate_content([
                    {"mime_type": mime, "data": audio_bytes},
                    prompt
                ])
                texto_transcrito = resultado.text.strip() if hasattr(resultado, "text") and resultado.text else ""
                if texto_transcrito:
                    print(f"[AUDIO TRANSCRITO POR GEMINI ({nombre_modelo})]: {texto_transcrito}")
                    return texto_transcrito
            except Exception as e:
                # Probar siguiente formato/modelo
                continue

    print("[AVISO]: No se pudo transcribir el audio con los modelos disponibles.")
    return ""


