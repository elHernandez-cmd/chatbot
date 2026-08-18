import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from contextvars import ContextVar

TIMEZONE_MEXICO = ZoneInfo("America/Mexico_City")

# ContextVar para asociar el sender_id del cliente activo de forma segura
CURRENT_SENDER_ID: ContextVar[str] = ContextVar("CURRENT_SENDER_ID", default="")

APARTADOS_FILE = "/tmp/apartados_rosymar.json" if os.path.exists("/tmp") else os.path.join(os.path.dirname(__file__), "apartados_rosymar.json")

def _leer_apartados() -> list:
    if os.path.exists(APARTADOS_FILE):
        try:
            with open(APARTADOS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"Aviso leyendo apartados: {e}")
    return []

def _guardar_apartados(apartados: list):
    try:
        with open(APARTADOS_FILE, "w", encoding="utf-8") as f:
            json.dump(apartados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando apartados: {e}")

def crear_apartado_memoria(nombre_cliente: str, telefono: str, articulo_y_talla: str, sender_id: str = None) -> dict:
    """Registra un nuevo apartado en la memoria persistente del chatbot."""
    if not sender_id:
        sender_id = CURRENT_SENDER_ID.get()
        
    ahora = datetime.now(TIMEZONE_MEXICO)
    apartados = _leer_apartados()
    
    nuevo_id = f"APT-{len(apartados) + 1}"
    nuevo_apartado = {
        "id": nuevo_id,
        "sender_id": str(sender_id) if sender_id else "",
        "nombre_cliente": nombre_cliente.strip(),
        "telefono": telefono.strip(),
        "articulo_y_talla": articulo_y_talla.strip(),
        "fecha_creacion": ahora.strftime("%Y-%m-%d %H:%M:%S"),
        "dias_plazo": 15,
        "estado": "pendiente",  # 'pendiente' | 'liquidado' | 'cancelado'
        "recordatorio_enviado": False,
        "fecha_recordatorio": None
    }
    
    apartados.append(nuevo_apartado)
    _guardar_apartados(apartados)
    print(f"📦 [APARTADO REGISTRADO EN MEMORIA]: {nuevo_id} para {nombre_cliente} ({articulo_y_talla})")
    return nuevo_apartado

def obtener_todos_apartados() -> list:
    """Retorna todos los apartados registrados."""
    return _leer_apartados()

def marcar_apartado_liquidado(identificador: str) -> bool:
    """Marca un apartado como liquidado/entregado para no enviar más recordatorios."""
    apartados = _leer_apartados()
    modificado = False
    id_busqueda = str(identificador).strip().lower()
    
    for apt in apartados:
        if apt.get("id", "").lower() == id_busqueda or apt.get("sender_id", "").lower() == id_busqueda or id_busqueda in apt.get("nombre_cliente", "").lower():
            apt["estado"] = "liquidado"
            modificado = True
            print(f"✅ [APARTADO LIQUIDADO]: {apt.get('id')} de {apt.get('nombre_cliente')}")
            
    if modificado:
        _guardar_apartados(apartados)
    return modificado

def verificar_apartados_vencidos(dias_limite: int = 15) -> list:
    """Identifica los apartados pendientes que ya cumplieron los 15 días y aún no han recibido recordatorio."""
    ahora = datetime.now(TIMEZONE_MEXICO)
    apartados = _leer_apartados()
    vencidos = []
    
    for apt in apartados:
        if apt.get("estado") == "pendiente" and not apt.get("recordatorio_enviado"):
            fecha_str = apt.get("fecha_creacion")
            if not fecha_str:
                continue
            try:
                fecha_creacion = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TIMEZONE_MEXICO)
                dias_transcurridos = (ahora - fecha_creacion).days
                if dias_transcurridos >= dias_limite:
                    apt["_dias_transcurridos"] = dias_transcurridos
                    vencidos.append(apt)
            except Exception as e:
                print(f"Error calculando días para apartado {apt.get('id')}: {e}")
                
    return vencidos

def procesar_y_enviar_recordatorios(enviar_mensaje_callback) -> int:
    """
    Revisa los apartados con 15 días vencidos y envía un recordatorio automático por Messenger.
    Retorna la cantidad de recordatorios enviados.
    """
    vencidos = verificar_apartados_vencidos(dias_limite=15)
    if not vencidos:
        return 0
        
    apartados = _leer_apartados()
    ahora_str = datetime.now(TIMEZONE_MEXICO).strftime("%Y-%m-%d %H:%M:%S")
    enviados = 0
    
    for v in vencidos:
        s_id = v.get("sender_id")
        nombre = v.get("nombre_cliente", "Estimado cliente")
        articulo = v.get("articulo_y_talla", "su artículo")
        
        # Si tiene sender_id de Messenger, enviar recordatorio directo
        if s_id:
            mensaje = (
                f"¡Hola **{nombre}**! Te saludamos con mucho gusto de **Novedades Rosymar**.\n\n"
                f"Te recordamos amablemente que hoy se cumplen los **15 días de plazo** de tu apartado de **{articulo}**.\n\n"
                f"Quedamos a tus órdenes en la tienda física en Villa Ignacio Allende para que pases a liquidarlo y recogerlo. ¡Que tengas un excelente día! ✨"
            )
            try:
                print(f"🔔 [ENVIANDO RECORDATORIO DE 15 DÍAS a {s_id} ({nombre})]: {articulo}")
                enviar_mensaje_callback(s_id, mensaje)
                enviados += 1
            except Exception as e:
                print(f"Error enviando recordatorio a {s_id}: {e}")
                
        # Marcar recordatorio_enviado = True en la memoria persistente
        for apt in apartados:
            if apt.get("id") == v.get("id"):
                apt["recordatorio_enviado"] = True
                apt["fecha_recordatorio"] = ahora_str
                
    _guardar_apartados(apartados)
    return enviados
