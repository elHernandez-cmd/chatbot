import os
import sys
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
from agent.services import (
    procesar_comando_admin,
    es_usuario_bloqueado,
    contiene_groserias,
    registrar_infraccion_groseria,
    esta_en_horario_atencion,
    guardar_mensaje_pendiente,
    obtener_y_limpiar_pendientes,
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

def atender_cliente(sender_id: str, texto_usuario: str):
    """Orquesta la atención completa: moderación, comandos, horarios, recordatorios e IA."""
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

    # 4. Control de horario: Activo 6:00 AM a 7:59 PM. Fuera de ese rango se encola para la mañana.
    if not esta_en_horario_atencion():
        print(f"🌙 [NOCHE / FUERA DE HORARIO]: Mensaje de {sender_id} guardado para responder a las 6:00 AM.")
        guardar_mensaje_pendiente(sender_id, texto_usuario)
        return

    # 5. Si es horario diurno, responder mensajes nocturnos pendientes acumulados
    pendientes = obtener_y_limpiar_pendientes()
    for item in pendientes:
        p_id = item.get("sender_id")
        p_msg = item.get("mensaje")
        if p_id and p_msg and not es_usuario_bloqueado(p_id):
            try:
                print(f"🌅 [RESPONDIENDO PENDIENTE NOCTURNO a {p_id}]: {p_msg}")
                enviar_accion_messenger(p_id, "mark_seen")
                enviar_accion_messenger(p_id, "typing_on")
                resp_pendiente = procesar_mensaje_con_ia(p_id, p_msg)
                enviar_mensaje_messenger(p_id, resp_pendiente)
                time.sleep(1)
            except Exception as e:
                print(f"Error respondiendo pendiente a {p_id}: {e}")

    # 6. Verificar y enviar recordatorios automáticos de apartados a los 15 días
    try:
        procesar_y_enviar_recordatorios(enviar_mensaje_messenger)
    except Exception as e:
        print(f"Aviso verificando recordatorios: {e}")

    # 7. Flujo normal de atención diurna con IA
    enviar_accion_messenger(sender_id, "mark_seen")
    enviar_accion_messenger(sender_id, "typing_on")
    time.sleep(2)
    
    # 8. Generar y enviar respuesta ultra concreta con Gemini
    respuesta_ia = procesar_mensaje_con_ia(sender_id, texto_usuario)
    print(f"[RESPUESTA IA]: {respuesta_ia}")
    enviar_accion_messenger(sender_id, "typing_on")
    time.sleep(1)
    enviar_mensaje_messenger(sender_id, respuesta_ia)

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
    """Recibe y procesa los eventos entrantes de Facebook Messenger."""
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
                texto_usuario = message.get("text")
                if sender_id and texto_usuario:
                    try:
                        atender_cliente(sender_id, texto_usuario)
                    except Exception as e:
                        print(f"Error atendiendo a {sender_id}: {e}")
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
