import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE_MEXICO = ZoneInfo("America/Mexico_City")

PENDIENTES_FILE = "/tmp/pendientes_noche_rosymar.json" if os.path.exists("/tmp") else os.path.join(os.path.dirname(__file__), "pendientes_noche_rosymar.json")

def obtener_hora_mexico() -> datetime:
    """Retorna la fecha y hora actual en la zona horaria de Tabasco / Centro de México."""
    return datetime.now(TIMEZONE_MEXICO)

def esta_en_horario_atencion() -> bool:
    """
    Verifica si el chatbot debe responder de inmediato:
    Activo: De 6:00 AM a 7:59 PM (06:00:00 a 19:59:59).
    Inactivo/Noche: De 8:00 PM a 5:59 AM (después de 7:59 PM y antes de 6:00 AM).
    """
    ahora = obtener_hora_mexico()
    hora = ahora.hour
    
    # Activo desde las 6:00 AM (hora 6) hasta las 7:59 PM (hora 19)
    if 6 <= hora < 20:
        return True
    return False

def guardar_mensaje_pendiente(sender_id: str, mensaje: str):
    """Guarda un mensaje recibido fuera de horario para ser respondido a partir de las 6:00 AM."""
    if not sender_id or not mensaje:
        return
        
    ahora = obtener_hora_mexico().strftime("%Y-%m-%d %H:%M:%S")
    pendientes = []
    
    if os.path.exists(PENDIENTES_FILE):
        try:
            with open(PENDIENTES_FILE, "r", encoding="utf-8") as f:
                pendientes = json.load(f)
                if not isinstance(pendientes, list):
                    pendientes = []
        except Exception:
            pendientes = []
            
    pendientes.append({
        "sender_id": str(sender_id),
        "mensaje": mensaje.strip(),
        "fecha": ahora
    })
    
    try:
        with open(PENDIENTES_FILE, "w", encoding="utf-8") as f:
            json.dump(pendientes, f, ensure_ascii=False, indent=2)
        print(f"🌙 [MENSAJE NOCTURNO GUARDADO]: Usuario {sender_id} a las {ahora} - Se responderá a las 6:00 AM.")
    except Exception as e:
        print(f"Error guardando mensaje nocturno: {e}")

def obtener_y_limpiar_pendientes() -> list:
    """Obtiene todos los mensajes pendientes de la noche y limpia la cola."""
    if not os.path.exists(PENDIENTES_FILE):
        return []
        
    pendientes = []
    try:
        with open(PENDIENTES_FILE, "r", encoding="utf-8") as f:
            pendientes = json.load(f)
            if not isinstance(pendientes, list):
                pendientes = []
    except Exception as e:
        print(f"Error leyendo pendientes: {e}")
        return []
        
    # Limpiar archivo
    try:
        with open(PENDIENTES_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    except Exception as e:
        print(f"Error limpiando pendientes: {e}")
        
    return pendientes
