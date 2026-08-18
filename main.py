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

def atender_cliente(sender_id: str, texto_usuario: str):
    """Procesa el mensaje (comandos administrativos o atención con IA a clientes)."""
    print(f"\n[MENSAJE MESSENGER de {sender_id}]: {texto_usuario}")
    
    # 1. Verificar si es un comando administrativo (/actualizar, /verinventario, /limpiarinventario)
    es_comando, respuesta_admin = procesar_comando_admin(sender_id, texto_usuario)
    if es_comando:
        print(f"[COMANDO ADMIN]: {respuesta_admin}")
        enviar_accion_messenger(sender_id, "mark_seen")
        enviar_mensaje_messenger(sender_id, respuesta_admin)
        # Limpiar sesiones de chat para que el nuevo inventario se aplique de inmediato
        from agent.gemini_agent import SESIONES
        SESIONES.clear()
        return

    # 2. Flujo normal de cliente: marcar como leído y activar "Escribiendo..."
    enviar_accion_messenger(sender_id, "mark_seen")
    enviar_accion_messenger(sender_id, "typing_on")
    
    # 3. Pausa natural humana (simula lectura del mensaje)
    time.sleep(2)
    
    # 4. Procesar respuesta certera con Gemini
    respuesta_ia = procesar_mensaje_con_ia(sender_id, texto_usuario)
    print(f"[RESPUESTA IA]: {respuesta_ia}")
    
    # 5. Mantener indicador de "Escribiendo..." brevemente antes de enviar
    enviar_accion_messenger(sender_id, "typing_on")
    time.sleep(1)
    
    # 6. Enviar mensaje final
    enviar_mensaje_messenger(sender_id, respuesta_ia)

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
