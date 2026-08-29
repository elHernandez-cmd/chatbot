import os
import sys
import io
import json
import time
import requests
from fastapi import FastAPI, Request, Response, Query
from dotenv import load_dotenv

# Asegurar codificación UTF-8 en consola de Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

from agent.gemini_agent import procesar_mensaje_con_ia, SESIONES
from agent.voice_service import generar_audio_elevenlabs, transcribir_audio_gemini
from agent.services import (
    procesar_comando_admin,
    es_usuario_bloqueado,
    contiene_groserias,
    registrar_infraccion_groseria,
    esta_en_horario_atencion,
    MENSAJE_FUERA_DE_HORARIO,
    procesar_y_enviar_recordatorios,
    obtener_total_apartados
)

app = FastAPI(title="Bot Novedades Rosymar - Facebook Messenger")

FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "RosymarTokenSeguro123").strip()

def enviar_accion_messenger(sender_id: str, accion: str = "typing_on"):
    """Envía una acción a Messenger ('typing_on' o 'mark_seen')."""
    if not FB_PAGE_ACCESS_TOKEN or not sender_id:
        return
    url = f"https://graph.facebook.com/v20.0/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "sender_action": accion}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Aviso enviando acción {accion}: {e}")

def enviar_mensaje_messenger(sender_id: str, texto_respuesta: str):
    """Envía la respuesta al chat de Messenger asegurando el límite de 2000 caracteres por mensaje."""
    if not FB_PAGE_ACCESS_TOKEN or not sender_id or not texto_respuesta:
        print("Aviso: Falta token de Messenger, ID o texto de respuesta")
        return
        
    url = f"https://graph.facebook.com/v20.0/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    partes = [texto_respuesta[i:i+1900] for i in range(0, len(texto_respuesta), 1900)] if len(texto_respuesta) > 1900 else [texto_respuesta]
    
    for parte in partes:
        payload = {"recipient": {"id": sender_id}, "message": {"text": parte}}
        try:
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code != 200:
                print(f"Error enviando a Messenger ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"Excepción enviando a Messenger: {e}")

def enviar_audio_messenger(sender_id: str, audio_bytes: bytes):
    """Envía una nota de voz / audio generado por ElevenLabs a Messenger."""
    if not FB_PAGE_ACCESS_TOKEN or not sender_id or not audio_bytes:
        return
    url = f"https://graph.facebook.com/v20.0/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": json.dumps({"id": sender_id}),
        "message": json.dumps({"attachment": {"type": "audio", "payload": {}}})
    }
    files = {
        "filedata": ("respuesta_voz.mp3", io.BytesIO(audio_bytes), "audio/mp3")
    }
    try:
        res = requests.post(url, data=payload, files=files, timeout=15)
        if res.status_code == 200:
            print(f"[AUDIO ENVIADO]: Nota de voz enviada exitosamente a {sender_id}.")
        else:
            print(f"Aviso enviando audio a Messenger ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"Excepción enviando audio a Messenger: {e}")

def atender_cliente(sender_id: str, texto_usuario: str, respondio_con_audio: bool = False):
    """Orquesta la atención completa: moderación, comandos, horarios, recordatorios, IA y voz."""
    print(f"\n[MENSAJE MESSENGER de {sender_id}]: {texto_usuario}")
    
    # 1. Ignorar usuarios bloqueados por conducta ofensiva
    if es_usuario_bloqueado(sender_id):
        print(f"⛔ [IGNORADO]: Usuario {sender_id} bloqueado permanentemente.")
        return

    # 2. Procesar comandos administrativos (/actualizar, /verinventario, /limpiarinventario, /apartados, /liquidar, /bloqueados, /desbloquear)
    es_comando, respuesta_admin = procesar_comando_admin(sender_id, texto_usuario)
    if es_comando:
        print(f"[COMANDO ADMIN]: {respuesta_admin}")
        enviar_accion_messenger(sender_id, "mark_seen")
        enviar_mensaje_messenger(sender_id, respuesta_admin)
        SESIONES.clear()
        return

    # 3. Moderación: Filtro estricto de groserías e insultos mexicanos
    if contiene_groserias(texto_usuario):
        fue_bloqueado = registrar_infraccion_groseria(sender_id)
        if fue_bloqueado:
            print(f"⛔ [BLOQUEO AUTOMÁTICO]: Usuario {sender_id} bloqueado por groserías reiteradas.")
        else:
            print(f"⚠️ [GROSERÍA DETECTADA]: No se responde al mensaje ofensivo de {sender_id}.")
        return

    # 4. Horario Nocturno (8:00 PM a 5:59 AM): Respuesta inmediata y cordial de cortesía (Opción 2)
    if not esta_en_horario_atencion():
        print(f"🌙 [NOCHE / FUERA DE HORARIO]: Enviando mensaje automático de cortesía a {sender_id}.")
        enviar_accion_messenger(sender_id, "mark_seen")
        enviar_accion_messenger(sender_id, "typing_on")
        time.sleep(1)
        enviar_mensaje_messenger(sender_id, MENSAJE_FUERA_DE_HORARIO)
        return

    # 5. Verificar y enviar recordatorios automáticos de apartados a los 15 días
    try:
        procesar_y_enviar_recordatorios(enviar_mensaje_messenger)
    except Exception as e:
        print(f"Aviso verificando recordatorios: {e}")

    # 6. Flujo de atención diurna (6:00 AM a 7:59 PM) con IA
    enviar_accion_messenger(sender_id, "mark_seen")
    enviar_accion_messenger(sender_id, "typing_on")
    
    # 7. Generar respuesta concreta con Gemini
    respuesta_ia = procesar_mensaje_con_ia(sender_id, texto_usuario)
    print(f"[RESPUESTA IA]: {respuesta_ia}")
    
    # 8. Enviar respuesta en texto al cliente
    enviar_mensaje_messenger(sender_id, respuesta_ia)
    
    # 9. Generar y enviar nota de voz con ElevenLabs SOLO si el cliente envió una nota de voz
    if respondio_con_audio:
        try:
            audio_voz = generar_audio_elevenlabs(respuesta_ia)
            if audio_voz:
                enviar_audio_messenger(sender_id, audio_voz)
        except Exception as e:
            print(f"Aviso generando voz de ElevenLabs: {e}")

# --- RUTAS Y ENDPOINTS FASTAPI ---

@app.get("/webhook")
def verificar_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge")
):
    """Endpoint de verificación del Webhook de Meta / Facebook."""
    if mode == "subscribe" and token == FB_VERIFY_TOKEN:
        print("¡Webhook de Facebook verificado con éxito!")
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verificación fallida", status_code=403)

@app.post("/webhook")
async def recibir_mensaje(request: Request):
    """Recibe y procesa los eventos entrantes de Facebook Messenger (Texto y Notas de Voz)."""
    try:
        data = await request.json()
    except Exception:
        return Response(content="INVALID_PAYLOAD", status_code=400)
    
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                message = messaging_event.get("message", {})
                if message.get("is_echo"):
                    continue
                
                # Caso A: Mensaje de Texto tradicional
                texto_usuario = message.get("text")
                if sender_id and texto_usuario:
                    try:
                        atender_cliente(sender_id, texto_usuario, respondio_con_audio=False)
                    except Exception as e:
                        print(f"Error atendiendo a {sender_id}: {e}")
                    continue

                # Caso B: Nota de Voz / Audio enviado por el cliente
                attachments = message.get("attachments", [])
                for att in attachments:
                    tipo_adjunto = att.get("type", "").lower()
                    audio_url = att.get("payload", {}).get("url")
                    
                    if audio_url and (tipo_adjunto in ["audio", "voice", "file", "fallback"] or ".mp4" in audio_url or ".aac" in audio_url or ".mp3" in audio_url):
                        if sender_id:
                            try:
                                print(f"🎧 [AUDIO ENTRANTE de {sender_id}]: Descargando nota de voz ({tipo_adjunto})...")
                                enviar_accion_messenger(sender_id, "mark_seen")
                                enviar_accion_messenger(sender_id, "typing_on")
                                headers = {"User-Agent": "Mozilla/5.0"}
                                audio_res = requests.get(audio_url, headers=headers, timeout=15)
                                if audio_res.status_code == 200 and audio_res.content:
                                    texto_transcrito = transcribir_audio_gemini(audio_res.content)
                                    if texto_transcrito:
                                        atender_cliente(sender_id, texto_transcrito, respondio_con_audio=True)
                                    else:
                                        print(f"Aviso: Audio de {sender_id} no pudo ser interpretado.")
                                        enviar_mensaje_messenger(sender_id, "¡Hola! No pude escuchar con claridad tu nota de voz. ¿Podrías repetirla o escribirme tu consulta?")
                            except Exception as e:
                                print(f"Error procesando nota de voz de {sender_id}: {e}")
        return Response(content="EVENT_RECEIVED", status_code=200)

    return {"status": "ok"}

@app.get("/recordatorios")
def ejecutar_recordatorios():
    """Consulta y ejecuta manualmente la verificación de recordatorios de 15 días."""
    enviados = procesar_y_enviar_recordatorios(enviar_mensaje_messenger)
    return {
        "status": "ok",
        "recordatorios_enviados": enviados,
        "total_apartados": obtener_total_apartados()
    }

@app.get("/")
def home():
    return {
        "negocio": "Novedades Rosymar",
        "canal": "Facebook Messenger",
        "plataforma": "Vercel Serverless",
        "estado": "Activo 24/7"
    }
