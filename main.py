import os
import sys
import requests
from fastapi import FastAPI, Request, Response, Query, BackgroundTasks
from dotenv import load_dotenv
from agent.gemini_agent import procesar_mensaje_con_ia

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

app = FastAPI(title="Bot Novedades Rosymar - Facebook Messenger")

FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "RosymarTokenSeguro123").strip()

def enviar_accion_messenger(sender_id: str, accion: str = "typing_on"):
    """Envía una acción a Messenger (ej: 'typing_on' o 'mark_seen')."""
    if not FB_PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v20.0/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": sender_id},
        "sender_action": accion
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error al enviar acción {accion}: {e}")

def enviar_mensaje_messenger(sender_id: str, texto_respuesta: str):
    """Envía la respuesta al chat de Facebook Messenger a través de Meta Graph API."""
    if not FB_PAGE_ACCESS_TOKEN:
        print("ERROR: No se ha configurado FB_PAGE_ACCESS_TOKEN")
        return
        
    url = f"https://graph.facebook.com/v20.0/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    
    # Meta limita los mensajes a un máximo de 2000 caracteres por mensaje
    partes = [texto_respuesta[i:i+1900] for i in range(0, len(texto_respuesta), 1900)] if len(texto_respuesta) > 1900 else [texto_respuesta]
    
    for parte in partes:
        payload = {
            "recipient": {"id": sender_id},
            "message": {"text": parte}
        }
        try:
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code != 200:
                print(f"Error enviando a Messenger ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"Excepción al enviar a Messenger: {e}")

import time
from agent.stock_manager import procesar_comando_admin
from agent.moderation import (
    es_usuario_bloqueado,
    contiene_groserias,
    registrar_infraccion_groseria
)
from agent.schedule_manager import (
    esta_en_horario_atencion,
    guardar_mensaje_pendiente,
    obtener_y_limpiar_pendientes
)

from agent.apartados_manager import (
    procesar_y_enviar_recordatorios,
    obtener_todos_apartados
)

def atender_cliente(sender_id: str, texto_usuario: str):
    """Procesa el mensaje (comandos administrativos, moderación o atención con IA)."""
    print(f"\n[MENSAJE MESSENGER de {sender_id}]: {texto_usuario}")
    
    # 1. Verificar si el usuario está bloqueado permanentemente por insultos
    if es_usuario_bloqueado(sender_id):
        print(f"⛔ [MENSAJE IGNORADO]: El usuario {sender_id} está bloqueado por comportamiento grosero.")
        return

    # 2. Verificar si es un comando administrativo (/actualizar, /verinventario, /limpiarinventario, /bloqueados, /desbloquear, /apartados, /liquidar)
    es_comando, respuesta_admin = procesar_comando_admin(sender_id, texto_usuario)
    if es_comando:
        print(f"[COMANDO ADMIN]: {respuesta_admin}")
        enviar_accion_messenger(sender_id, "mark_seen")
        enviar_mensaje_messenger(sender_id, respuesta_admin)
        from agent.gemini_agent import SESIONES
        SESIONES.clear()
        return

    # 3. Filtro de moderación: Detección estricta de insultos / groserías en México
    if contiene_groserias(texto_usuario):
        bloqueado_ahora = registrar_infraccion_groseria(sender_id)
        if bloqueado_ahora:
            print(f"⛔ [USUARIO BLOQUEADO]: {sender_id} fue bloqueado por insultos reiterados. No se responderá.")
        else:
            print(f"⚠️ [GROSERÍA DETECTADA]: Mensaje ofensivo de {sender_id}. No se envía respuesta.")
        return

    # 4. Control de horario: De 6:00 AM a 7:59 PM activo. Fuera de ese horario, no responder y encolar para la mañana.
    if not esta_en_horario_atencion():
        print(f"🌙 [FUERA DE HORARIO]: Mensaje de {sender_id} recibido después de las 7:59 PM o antes de las 6:00 AM. Guardando en cola para responder por la mañana.")
        guardar_mensaje_pendiente(sender_id, texto_usuario)
        return

    # 5. Si estamos en horario activo (6:00 AM - 7:59 PM), procesar cualquier mensaje pendiente acumulado de la noche
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

    # 6. Verificar y enviar recordatorios a clientes cuyos apartados hayan cumplido 15 días
    try:
        procesar_y_enviar_recordatorios(enviar_mensaje_messenger)
    except Exception as e:
        print(f"Aviso revisando recordatorios de apartados: {e}")

    # 7. Flujo normal de atención diurna: marcar como leído y activar "Escribiendo..."
    enviar_accion_messenger(sender_id, "mark_seen")
    enviar_accion_messenger(sender_id, "typing_on")
    
    # 8. Pausa humana natural
    time.sleep(2)
    
    # 9. Procesar respuesta ultra corta y concreta con Gemini
    respuesta_ia = procesar_mensaje_con_ia(sender_id, texto_usuario)
    print(f"[RESPUESTA IA]: {respuesta_ia}")
    
    # 10. Enviar respuesta final
    enviar_accion_messenger(sender_id, "typing_on")
    time.sleep(1)
    enviar_mensaje_messenger(sender_id, respuesta_ia)

@app.get("/recordatorios")
def ejecutar_recordatorios():
    """Endpoint para revisar y enviar recordatorios de apartados de 15 días."""
    enviados = procesar_y_enviar_recordatorios(enviar_mensaje_messenger)
    return {
        "status": "ok",
        "recordatorios_enviados": enviados,
        "total_apartados": len(obtener_todos_apartados())
    }

# --- 1. VERIFICACIÓN DEL WEBHOOK CON META (GET) ---
@app.get("/webhook")
def verificar_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge")
):
    """Endpoint que Facebook llama para validar el webhook."""
    if mode == "subscribe" and token == FB_VERIFY_TOKEN:
        print("¡Webhook de Facebook verificado con éxito!")
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verificación fallida", status_code=403)

# --- 2. RECEPCIÓN DE MENSAJES (POST) ---
@app.post("/webhook")
async def recibir_mensaje(request: Request):
    """Recibe los mensajes de Messenger y procesa con IA de inmediato."""
    try:
        data = await request.json()
    except Exception:
        return Response(content="INVALID_PAYLOAD", status_code=400)
    
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                message = messaging_event.get("message", {})
                
                # Ignorar ecos
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

@app.get("/")
def home():
    return {
        "negocio": "Novedades Rosymar",
        "canal": "Facebook Messenger",
        "plataforma": "Vercel Serverless",
        "estado": "Activo 24/7"
    }
