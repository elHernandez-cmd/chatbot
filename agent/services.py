import os
import sys
import re
import json
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from contextvars import ContextVar
from dotenv import load_dotenv

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

# --- 1. CONFIGURACIÓN Y CONSTANTES GLOBALES ---
TIMEZONE_MEXICO = ZoneInfo("America/Mexico_City")
ADMIN_PIN = os.getenv("ADMIN_PIN", "RosymarAdmin2026").strip()
ADMIN_SENDER_IDS_ENV = os.getenv("ADMIN_SENDER_IDS", "").strip()
ADMINISTRADORES = set([s.strip() for s in ADMIN_SENDER_IDS_ENV.split(",") if s.strip()])

# ContextVar para asociar el sender_id del cliente activo de forma segura entre llamadas
CURRENT_SENDER_ID: ContextVar[str] = ContextVar("CURRENT_SENDER_ID", default="")

# Rutas seguras de persistencia (usa /tmp en entornos serverless como Vercel)
def _obtener_ruta_persistencia(nombre_archivo: str) -> str:
    if os.path.exists("/tmp"):
        return f"/tmp/{nombre_archivo}"
    return os.path.join(os.path.dirname(__file__), nombre_archivo)

STOCK_FILE = _obtener_ruta_persistencia("stock_rosymar.json")
BLOCKED_FILE = _obtener_ruta_persistencia("bloqueados_rosymar.json")
STRIKES_FILE = _obtener_ruta_persistencia("strikes_rosymar.json")
PENDIENTES_FILE = _obtener_ruta_persistencia("pendientes_noche_rosymar.json")
APARTADOS_FILE = _obtener_ruta_persistencia("apartados_rosymar.json")
HISTORIAL_CONV_FILE = _obtener_ruta_persistencia("historial_conversaciones.json")

def obtener_historial_usuario(sender_id: str) -> list:
    """Obtiene los últimos turnos de conversación para mantener la memoria en Vercel Serverless."""
    if not sender_id:
        return []
    datos = _leer_json(HISTORIAL_CONV_FILE, {})
    return datos.get(str(sender_id), [])

def guardar_intercambio_historial(sender_id: str, mensaje_usuario: str, respuesta_bot: str):
    """Guarda el historial de la conversación de forma persistente."""
    if not sender_id:
        return
    datos = _leer_json(HISTORIAL_CONV_FILE, {})
    hist = datos.get(str(sender_id), [])
    hist.append({"role": "user", "parts": [mensaje_usuario]})
    hist.append({"role": "model", "parts": [respuesta_bot]})
    # Mantener los últimos 14 mensajes para contexto amplio sin saturar tokens
    if len(hist) > 14:
        hist = hist[-14:]
    datos[str(sender_id)] = hist
    _guardar_json(HISTORIAL_CONV_FILE, datos)

# Helpers seguros de JSON
def _leer_json(ruta: str, por_defecto=None):
    if por_defecto is None:
        por_defecto = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return por_defecto

def _guardar_json(ruta: str, datos) -> bool:
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error escribiendo {ruta}: {e}")
        return False

# --- 2. MODERACIÓN Y FILTRO DE GROSERÍAS MEXICANAS ---
PATRONES_GROSERIAS_MEXICO = [
    # Ch*ngar
    r"\bch+i+n+g+[a-z0-9]*\b", r"\bch+e+n+g+[a-z0-9]*\b", r"\bch+i+n+g+o+n+[a-z0-9]*\b",
    r"\bch+i+n+g+a+d+[a-z0-9]*\b", r"\bch+i+n+g+a+t+e\b", r"\bch+i+n+g+a tu m+a+d+r+e\b",
    # P*ndejo
    r"\bp+e+n+d+e+j+[a-z0-9]*\b", r"\bp+n+d+j+[a-z0-9]*\b", r"\bp+e+n+d+e+x+[a-z0-9]*\b",
    # P*to, p*ta
    r"\bp+u+t+[oa]s?\b", r"\bp+u+t+i+z+a\b", r"\bp+u+t+a+z+o\b", r"\bp+u+t+a m+a+d+r+e\b",
    r"\bh+i+j+[oa] d+e p+u+t+a\b",
    # V*rga
    r"\bv+e+r+g+[a-z0-9]*\b", r"\bv+r+g+[a-z0-9]*\b", r"\bv+e+r+g+a+z+o[s]?\b",
    r"\ba+l+a+v+e+r+g+a\b", r"\ba la verga\b", r"\bvete a la verga\b", r"\bme vale verga\b", r"\bvaleverga\b",
    # M*madas
    r"\bm+a+m+a+d+[a-z0-9]*\b", r"\bm+a+m+[oó]n+[a-z0-9]*\b", r"\bm+a+m+e+s\b", r"\bno mames\b",
    # C*lero, c*lo
    r"\bc+u+l+e+r+[a-z0-9]*\b", r"\bc+u+l+[oa]s?\b", r"\bo+j+e+t+[a-z0-9]*\b",
    # P*nche, C*brón
    r"\bp+i+n+c+h+e+[s]?\b", r"\bc+a+b+r+[oó]n+[a-z0-9]*\b",
    # Insultos
    r"\be+s+t+[uú]+p+i+d+[a-z0-9]*\b", r"\bi+d+i+o+t+[a-z0-9]*\b", r"\bi+m+b+[eé]+c+i+l+[a-z0-9]*\b",
    r"\bb+a+b+o+s+[a-z0-9]*\b", r"\bt+a+r+a+d+[a-z0-9]*\b", r"\bm+e+n+s+[oa]s?\b",
    r"\bz+o+q+u+e+t+[a-z0-9]*\b", r"\bz+o+p+e+n+c+[a-z0-9]*\b", r"\bm+i+e+r+d+[a-z0-9]*\b",
    r"\bc+o+m+e+m+i+e+r+d+a\b", r"\ba+s+q+u+e+r+o+s+[a-z0-9]*\b", r"\bp+e+r+r+a\b", r"\bz+o+r+r+a\b",
    r"\bm+u+g+r+o+s+[a-z0-9]*\b", r"\bj+o+t+[oa]s?\b", r"\bm+a+r+i+c+[oó]n+[a-z0-9]*\b",
    r"\bm+a+r+i+c+a+[s]?\b", r"\bl+[aá]+r+g+a+t+e\b", r"\blarguese\b",
    # Siglas
    r"\bchsm\b", r"\bctm\b", r"\bchptm\b", r"\balv\b", r"\bhdp\b", r"\bvlv\b", r"\bcsm\b"
]

REGEX_GROSERIAS = [re.compile(p, re.IGNORECASE) for p in PATRONES_GROSERIAS_MEXICO]

def normalizar_texto(texto: str) -> str:
    """Normaliza texto eliminando acentos, números leetspeak y símbolos para detección precisa."""
    if not texto:
        return ""
    t = texto.lower()
    reemplazos = {"@": "a", "4": "a", "3": "e", "1": "i", "!": "i", "|": "i", "0": "o", "5": "s", "$": "s", "7": "t", "*": ""}
    for k, v in reemplazos.items():
        t = t.replace(k, v)
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    t_sin_puntos = re.sub(r'([a-z])[\.\-\_\,\s]+([a-z])', r'\1\2', t)
    return f"{t} {t_sin_puntos}"

def contiene_groserias(texto: str) -> bool:
    """Detecta si el mensaje contiene groserías, albures pesados o insultos comunes en México."""
    if not texto:
        return False
    texto_norm = normalizar_texto(texto)
    return any(regex.search(texto_norm) for regex in REGEX_GROSERIAS)

def es_usuario_bloqueado(sender_id: str) -> bool:
    """Verifica si un usuario se encuentra en la lista de bloqueados."""
    if not sender_id:
        return False
    return str(sender_id) in _leer_json(BLOCKED_FILE, {})

def bloquear_usuario(sender_id: str, motivo: str = "Insultos o groserías reiteradas"):
    """Bloquea permanentemente a un usuario para no responderle más mensajes."""
    if not sender_id:
        return
    bloqueados = _leer_json(BLOCKED_FILE, {})
    bloqueados[str(sender_id)] = {
        "fecha_bloqueo": datetime.now(TIMEZONE_MEXICO).strftime("%Y-%m-%d %H:%M:%S"),
        "motivo": motivo
    }
    _guardar_json(BLOCKED_FILE, bloqueados)
    print(f"⛔ USUARIO BLOQUEADO: {sender_id} - Motivo: {motivo}")

def desbloquear_usuario(sender_id: str) -> bool:
    """Desbloquea a un usuario y reinicia sus infracciones."""
    if not sender_id:
        return False
    s_id = str(sender_id).strip()
    bloqueados = _leer_json(BLOCKED_FILE, {})
    removido = False
    if s_id in bloqueados:
        del bloqueados[s_id]
        _guardar_json(BLOCKED_FILE, bloqueados)
        removido = True
    strikes = _leer_json(STRIKES_FILE, {})
    if s_id in strikes:
        del strikes[s_id]
        _guardar_json(STRIKES_FILE, strikes)
        removido = True
    return removido

def registrar_infraccion_groseria(sender_id: str) -> bool:
    """Registra infracción por grosería. Si acumula 2, lo bloquea automáticamente."""
    if not sender_id:
        return False
    strikes = _leer_json(STRIKES_FILE, {})
    cuenta = strikes.get(str(sender_id), 0) + 1
    strikes[str(sender_id)] = cuenta
    _guardar_json(STRIKES_FILE, strikes)
    print(f"⚠️ INFRACCIÓN POR GROSERÍA: Usuario {sender_id} (#{cuenta})")
    if cuenta >= 2:
        bloquear_usuario(sender_id, motivo=f"Acumuló {cuenta} mensajes con groserías")
        return True
    return False

def obtener_usuarios_bloqueados() -> dict:
    return _leer_json(BLOCKED_FILE, {})

# --- 3. HORARIO DE ATENCIÓN Y RESPUESTA NOCTURNA ---
MENSAJE_FUERA_DE_HORARIO = (
    "¡Hola! Gracias por escribir a **Novedades Rosymar** ✨\n\n"
    "Por ahora estamos fuera de horario. Con gusto te atenderemos a partir de las **8:00 AM** (Horario en tienda: **Lunes a Sábado de 8:00 AM a 7:00 PM**).\n\n"
    "¡Déjanos tu duda y que tengas una linda noche! 🌙"
)

def esta_en_horario_atencion() -> bool:
    """Activo: 6:00 AM a 7:59 PM (06:00 a 19:59). Fuera de horario (Noche): 8:00 PM a 5:59 AM."""
    hora = datetime.now(TIMEZONE_MEXICO).hour
    return 6 <= hora < 20

def guardar_mensaje_pendiente(sender_id: str, mensaje: str):
    """Guarda un mensaje nocturno recibido fuera de horario."""
    if not sender_id or not mensaje:
        return
    ahora = datetime.now(TIMEZONE_MEXICO).strftime("%Y-%m-%d %H:%M:%S")
    pendientes = _leer_json(PENDIENTES_FILE, [])
    if not isinstance(pendientes, list):
        pendientes = []
    pendientes.append({"sender_id": str(sender_id), "mensaje": mensaje.strip(), "fecha": ahora})
    _guardar_json(PENDIENTES_FILE, pendientes)
    print(f"🌙 [MENSAJE NOCTURNO GUARDADO]: {sender_id} a las {ahora} - Se responderá a las 6:00 AM.")

def obtener_y_limpiar_pendientes() -> list:
    """Obtiene todos los mensajes pendientes de la noche y limpia la cola."""
    pendientes = _leer_json(PENDIENTES_FILE, [])
    if not isinstance(pendientes, list):
        pendientes = []
    if pendientes:
        _guardar_json(PENDIENTES_FILE, [])
    return pendientes

# --- 4. INVENTARIO, EXISTENCIAS Y COMANDOS DE ADMINISTRADOR ---
EXISTENCIAS_DEFAULT = """- Preescolar / Jardines de Niños: Jardín de Niños Las Flores, Preescolar Comunitario, Jardín de Niños Benito Juárez García, Jardín de Niños José María Pino Suárez, Jardín de Niños María Montessori.
- Escuelas Primarias: Escuela Primaria Domingo Faustino Sarmiento, Escuela Primaria General Emiliano Zapata, Escuela Primaria Benito Juárez, Escuela Primaria José María Pino Suárez, Escuela Primaria Vicente Suárez.
- Secundarias y Telesecundarias: Escuela Secundaria General Ignacio Allende, Escuela Secundaria Técnica Núm. 4, Escuela Secundaria Lic. Tomás Garrido Canabal, Telesecundaria Guadalupe Victoria, Telesecundaria Álvaro de la Cruz, Telesecundaria General Ignacio Zaragoza.
- Nivel Medio Superior: Plantel Núm. 5 del CECyTE Tabasco, Plantel Núm. 18 del Colegio de Bachilleres de Tabasco (COBATAB).
- Mochilas escolares Golden Star (juveniles, con ruedas y lapiceras): En existencia.
- Ropa para toda la familia (damas, caballeros, niños): En existencia."""

def obtener_existencias_actuales() -> str:
    data = _leer_json(STOCK_FILE, {})
    return data.get("existencias", EXISTENCIAS_DEFAULT) if isinstance(data, dict) else EXISTENCIAS_DEFAULT

def guardar_existencias(texto_nuevas_existencias: str, admin_id: str = "Admin") -> bool:
    data = {
        "ultima_actualizacion": datetime.now(TIMEZONE_MEXICO).strftime("%Y-%m-%d %H:%M:%S"),
        "actualizado_por": admin_id,
        "existencias": texto_nuevas_existencias.strip()
    }
    return _guardar_json(STOCK_FILE, data)

def es_administrador(sender_id: str) -> bool:
    return sender_id in ADMINISTRADORES

def registrar_administrador(sender_id: str):
    if sender_id:
        ADMINISTRADORES.add(sender_id)

def procesar_comando_admin(sender_id: str, mensaje: str):
    """
    Procesa comandos oficiales de administración con prefijo /:
    /actualizar, /verinventario, /limpiarinventario, /bloqueados, /desbloquear, /apartados, /liquidar.
    Retorna (es_comando: bool, respuesta: str)
    """
    msg = mensaje.strip()
    if not msg.startswith("/"):
        return False, ""
        
    partes = msg.split(maxsplit=1)
    comando = partes[0].lower()
    resto = partes[1].strip() if len(partes) > 1 else ""
    
    comandos_validos = ["/actualizar", "/verinventario", "/limpiarinventario", "/bloqueados", "/desbloquear", "/apartados", "/liquidar", "/comandos", "/ayuda"]
    if comando not in comandos_validos:
        return False, ""
    
    autorizado = es_administrador(sender_id)
    if ADMIN_PIN and ADMIN_PIN.lower() in msg.lower():
        autorizado = True
        registrar_administrador(sender_id)
        resto = resto.replace(ADMIN_PIN, "").replace(ADMIN_PIN.lower(), "").strip()
        
    if not autorizado:
        return True, (
            "⛔ **Acceso Restringido**: Este comando es exclusivo para administradores de **Novedades Rosymar**.\n"
            "Para autenticarte, incluye tu PIN de administrador en el comando. Ejemplos:\n"
            "• `/comandos PIN_SECRETO`\n"
            "• `/actualizar PIN_SECRETO tus existencias...`\n"
            "• `/verinventario PIN_SECRETO`\n"
            "• `/apartados PIN_SECRETO`\n"
            "• `/bloqueados PIN_SECRETO`"
        )
        
    if comando in ["/comandos", "/ayuda"]:
        return True, (
            "📋 **Lista de Comandos de Administrador (Novedades Rosymar):**\n\n"
            "📦 **Inventario y Existencias:**\n"
            "• `/actualizar <datos>` : Actualiza las existencias disponibles o agotadas.\n"
            "• `/verinventario` : Consulta el inventario que el bot tiene cargado.\n"
            "• `/limpiarinventario` : Restablece el inventario a los valores por defecto.\n\n"
            "⏰ **Control de Apartados (15 Días):**\n"
            "• `/apartados` : Muestra los apartados registrados, días transcurridos y estado.\n"
            "• `/liquidar <ID_APARTADO>` : Marca un apartado como entregado/liquidado.\n\n"
            "🛡️ **Moderación y Bloqueos:**\n"
            "• `/bloqueados` : Muestra los usuarios bloqueados por insultos o groserías.\n"
            "• `/desbloquear <ID_USUARIO>` : Reactiva la atención para un usuario.\n\n"
            "ℹ️ **Información:**\n"
            "• `/comandos` : Muestra esta lista de comandos disponibles."
        )
        
    if comando == "/actualizar":
        if not resto:
            return True, "ℹ️ **Uso**: `/actualizar <nuevos artículos en existencia o agotados>`"
        guardar_existencias(resto, admin_id=sender_id)
        return True, f"✅ **¡Inventario actualizado con éxito!**\n\n📦 **Nuevas existencias:**\n{resto}"
        
    elif comando == "/verinventario":
        existencias = obtener_existencias_actuales()
        return True, f"📋 **Inventario Actual en el Chatbot:**\n\n{existencias}\n\n*(Para actualizar: `/actualizar <datos>`)*"
        
    elif comando == "/limpiarinventario":
        guardar_existencias(EXISTENCIAS_DEFAULT, admin_id=sender_id)
        return True, "🔄 **Inventario restablecido** a los valores predeterminados de la tienda."
        
    elif comando == "/bloqueados":
        bloqueados = obtener_usuarios_bloqueados()
        if not bloqueados:
            return True, "✅ No hay usuarios bloqueados actualmente."
        lista = "\n".join([f"• ID `{uid}`: {info.get('motivo')} ({info.get('fecha_bloqueo')})" for uid, info in bloqueados.items()])
        return True, f"⛔ **Usuarios Bloqueados por Groserías:**\n\n{lista}\n\n*(Para desbloquear: `/desbloquear ID_USUARIO`)*"
        
    elif comando == "/desbloquear":
        if not resto:
            return True, "ℹ️ Escribe `/desbloquear <ID_USUARIO>` para reactivar la atención."
        res = desbloquear_usuario(resto)
        return True, f"✅ El usuario `{resto}` ha sido desbloqueado." if res else f"ℹ️ El usuario `{resto}` no estaba bloqueado."
        
    elif comando == "/apartados":
        apartados = _leer_json(APARTADOS_FILE, [])
        if not apartados:
            return True, "📦 No hay apartados registrados en la memoria actualmente."
        ahora = datetime.now(TIMEZONE_MEXICO)
        lineas = []
        for a in apartados:
            dias_trans = "?"
            try:
                dt_c = datetime.strptime(a.get("fecha_creacion", ""), "%Y-%m-%d %H:%M:%S").replace(tzinfo=TIMEZONE_MEXICO)
                dias_trans = str((ahora - dt_c).days)
            except Exception:
                pass
            estado_icon = "🟢" if a.get("estado") == "pendiente" else "✅"
            notif = " (🔔 Notificado)" if a.get("recordatorio_enviado") else ""
            lineas.append(f"{estado_icon} **{a.get('id')}**: {a.get('nombre_cliente')} - {a.get('articulo_y_talla')} | Tel: {a.get('telefono')} | {dias_trans}/15 días [{a.get('estado').upper()}]{notif}")
        return True, "📋 **Control de Apartados (15 días de plazo):**\n\n" + "\n".join(lineas) + "\n\n*(Para liquidar: `/liquidar ID_APARTADO`)*"
        
    elif comando == "/liquidar":
        if not resto:
            return True, "ℹ️ Escribe `/liquidar <ID_APARTADO>` (ej: `/liquidar APT-1`)."
        apartados = _leer_json(APARTADOS_FILE, [])
        modificado = False
        for apt in apartados:
            if apt.get("id", "").lower() == resto.lower() or resto.lower() in apt.get("nombre_cliente", "").lower():
                apt["estado"] = "liquidado"
                modificado = True
        if modificado:
            _guardar_json(APARTADOS_FILE, apartados)
            return True, f"✅ El apartado `{resto}` ha sido marcado como **LIQUIDADO / ENTREGADO**."
        return True, f"⚠️ No se encontró el apartado `{resto}`."
        
    return False, ""

# --- 5. MEMORIA DE APARTADOS Y RECORDATORIOS (3 DÍAS UNIFORMES / 15 DÍAS OTROS) ---
CACHE_PERFILES = {}

def obtener_perfil_messenger(sender_id: str) -> dict:
    """Obtiene el nombre real del cliente desde la Graph API de Facebook Messenger."""
    import requests
    if not sender_id:
        return {"nombre": "Cliente", "telefono": "Chat Messenger"}
    s_id = str(sender_id).strip()
    if s_id in CACHE_PERFILES:
        return CACHE_PERFILES[s_id]
        
    token = os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
    if not token:
        return {"nombre": "Cliente", "telefono": f"Messenger ({s_id})"}
        
    try:
        url = f"https://graph.facebook.com/v20.0/{s_id}?fields=first_name,last_name,name&access_token={token}"
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            data = r.json()
            nombre = data.get("name") or data.get("first_name") or "Cliente"
            perfil = {"nombre": nombre.strip(), "telefono": f"Messenger ({s_id})"}
            CACHE_PERFILES[s_id] = perfil
            return perfil
    except Exception as e:
        print(f"Aviso consultando perfil de Messenger ({s_id}): {e}")
        
    return {"nombre": "Cliente", "telefono": f"Messenger ({s_id})"}

def crear_apartado_memoria(nombre_cliente: str = "", telefono: str = "", articulo_y_talla: str = "", sender_id: str = None, dias_plazo: int = None) -> dict:
    """Registra un nuevo apartado asociando el chat del cliente y obteniendo su nombre automáticamente."""
    if not sender_id:
        sender_id = CURRENT_SENDER_ID.get()
        
    if not nombre_cliente or nombre_cliente.strip().lower() in ["", "cliente", "estimado cliente", "estimado/a cliente"]:
        perfil = obtener_perfil_messenger(sender_id)
        nombre_cliente = perfil.get("nombre", "Cliente")
        
    if not telefono or telefono.strip().lower() in ["", "messenger", "chat messenger"]:
        perfil = obtener_perfil_messenger(sender_id)
        telefono = perfil.get("telefono", f"Messenger ({sender_id})")
        
    ahora = datetime.now(TIMEZONE_MEXICO)
    apartados = _leer_json(APARTADOS_FILE, [])
    if not isinstance(apartados, list):
        apartados = []
        
    art_lower = articulo_y_talla.lower()
    if dias_plazo is None:
        # Uniformes escolares y Mochilas tienen 3 días de plazo máximo para liquidar; ropa y demás tienen 15 días
        palabras_3_dias = [
            "uniforme", "cecyte", "cobatab", "bachiller", "primaria", "secundaria", "telesecundaria",
            "jardin", "preescolar", "comunitario", "montessori", "sarmiento", "zapata", "vicente suarez",
            "tomas garrido", "guadalupe victoria", "alvaro de la cruz", "zaragoza", "las flores",
            "benito juarez", "pino suarez", "tecnica 4", "playera", "falda", "pantalon", "pants",
            "mochila", "golden star", "lapicera", "lonchera"
        ]
        if any(w in art_lower for w in palabras_3_dias):
            dias_plazo = 3
        else:
            dias_plazo = 15
            
    nuevo_id = f"APT-{len(apartados) + 1}"
    nuevo_apartado = {
        "id": nuevo_id,
        "sender_id": str(sender_id) if sender_id else "",
        "nombre_cliente": nombre_cliente.strip(),
        "telefono": telefono.strip(),
        "articulo_y_talla": articulo_y_talla.strip(),
        "fecha_creacion": ahora.strftime("%Y-%m-%d %H:%M:%S"),
        "dias_plazo": dias_plazo,
        "estado": "pendiente",
        "recordatorio_enviado": False,
        "fecha_recordatorio": None
    }
    apartados.append(nuevo_apartado)
    _guardar_json(APARTADOS_FILE, apartados)
    print(f"📦 [APARTADO REGISTRADO]: {nuevo_id} para {nombre_cliente} ({articulo_y_talla}) - Plazo: {dias_plazo} días.")
    return nuevo_apartado

def consultar_apartados_cliente(sender_id: str = None) -> list:
    """Consulta los apartados vigentes asociados a este chat de cliente."""
    if not sender_id:
        sender_id = CURRENT_SENDER_ID.get()
    if not sender_id:
        return []
        
    apartados = _leer_json(APARTADOS_FILE, [])
    if not isinstance(apartados, list):
        return []
        
    ahora = datetime.now(TIMEZONE_MEXICO)
    mis_apartados = []
    
    for a in apartados:
        if str(a.get("sender_id")) == str(sender_id) and a.get("estado") == "pendiente":
            dias_plazo = a.get("dias_plazo", 15)
            fecha_str = a.get("fecha_creacion", "")
            dias_transcurridos = 0
            fecha_bonita = fecha_str
            hora_bonita = ""
            
            if fecha_str:
                try:
                    dt = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TIMEZONE_MEXICO)
                    dias_transcurridos = (ahora - dt).days
                    dias_restantes = max(0, dias_plazo - dias_transcurridos)
                    fecha_bonita = dt.strftime("%d/%m/%Y")
                    hora_bonita = dt.strftime("%I:%M %p")
                except Exception:
                    dias_restantes = dias_plazo
            else:
                dias_restantes = dias_plazo

            mis_apartados.append({
                "articulo": a.get("articulo_y_talla"),
                "nombre": a.get("nombre_cliente"),
                "fecha": fecha_bonita,
                "hora": hora_bonita,
                "plazo_total": dias_plazo,
                "dias_restantes": dias_restantes
            })
            
    return mis_apartados

def procesar_y_enviar_recordatorios(enviar_mensaje_callback) -> int:
    """Revisa los apartados con plazo cumplido (3 días uniformes / 15 días otros) y envía recordatorio cordial."""
    apartados = _leer_json(APARTADOS_FILE, [])
    if not isinstance(apartados, list) or not apartados:
        return 0
        
    ahora = datetime.now(TIMEZONE_MEXICO)
    ahora_str = ahora.strftime("%Y-%m-%d %H:%M:%S")
    enviados = 0
    modificado = False
    
    for apt in apartados:
        if apt.get("estado") == "pendiente" and not apt.get("recordatorio_enviado"):
            fecha_str = apt.get("fecha_creacion")
            if not fecha_str:
                continue
            try:
                dt_c = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TIMEZONE_MEXICO)
                dias_plazo = apt.get("dias_plazo", 15)
                if (ahora - dt_c).days >= dias_plazo:
                    s_id = apt.get("sender_id")
                    nombre = apt.get("nombre_cliente", "Estimado cliente")
                    articulo = apt.get("articulo_y_talla", "su artículo")
                    
                    if s_id:
                        mensaje = (
                            f"¡Hola **{nombre}**! Te saludamos con mucho gusto de **Novedades Rosymar**.\n\n"
                            f"Te recordamos amablemente que hoy se cumplen los **{dias_plazo} días de plazo** de tu apartado de **{articulo}**.\n\n"
                            f"Quedamos a tus órdenes en la tienda física en Ignacio Allende, Centla para que pases a liquidarlo y recogerlo. ¡Que tengas un excelente día! ✨"
                        )
                        try:
                            print(f"🔔 [ENVIANDO RECORDATORIO {dias_plazo} DÍAS a {s_id} ({nombre})]: {articulo}")
                            enviar_mensaje_callback(s_id, mensaje)
                            enviados += 1
                        except Exception as e:
                            print(f"Error enviando recordatorio a {s_id}: {e}")
                            
                    apt["recordatorio_enviado"] = True
                    apt["fecha_recordatorio"] = ahora_str
                    modificado = True
            except Exception as e:
                print(f"Error revisando fecha de apartado {apt.get('id')}: {e}")
                
    if modificado:
        _guardar_json(APARTADOS_FILE, apartados)
    return enviados

def obtener_total_apartados() -> int:
    apartados = _leer_json(APARTADOS_FILE, [])
    return len(apartados) if isinstance(apartados, list) else 0

# --- 6. SERVICIOS DE GOOGLE WORKSPACE (SHEETS Y CALENDAR) ---
CREDS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
CREDS_JSON_RAW = os.getenv("GOOGLE_CREDENTIALS_JSON")
ID_CALENDARIO = os.getenv("GOOGLE_CALENDAR_ID", "primary")
NOMBRE_HOJA_SHEETS = os.getenv("GOOGLE_SHEET_NAME", "CRM_WhatsApp")

def get_google_services():
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        import gspread
        scopes = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/spreadsheets"]
        creds = None
        if CREDS_JSON_RAW:
            creds = Credentials.from_service_account_info(json.loads(CREDS_JSON_RAW), scopes=scopes)
        elif os.path.exists(CREDS_FILE):
            creds = Credentials.from_service_account_file(CREDS_FILE, scopes=scopes)
        if not creds:
            return None, None
        return build("calendar", "v3", credentials=creds), gspread.authorize(creds)
    except Exception as e:
        print(f"Google Workspace no configurado o en simulación: {e}")
        return None, None

def insertar_evento_calendar(titulo: str, fecha_inicio_iso: str, fecha_fin_iso: str, descripcion: str = ""):
    calendar_service, _ = get_google_services()
    if not calendar_service:
        print(f"[SIMULACIÓN CALENDAR] Evento: {titulo} ({fecha_inicio_iso})")
        return "calendar_simulado"
    try:
        evento = {
            "summary": titulo,
            "description": descripcion,
            "start": {"dateTime": fecha_inicio_iso, "timeZone": "America/Mexico_City"},
            "end": {"dateTime": fecha_fin_iso, "timeZone": "America/Mexico_City"}
        }
        res = calendar_service.events().insert(calendarId=ID_CALENDARIO, body=evento).execute()
        return res.get("htmlLink")
    except Exception as e:
        print(f"Error insertando en Calendar: {e}")
        return None

def guardar_fila_sheets(pestana: str, datos: list):
    _, sheets_client = get_google_services()
    if not sheets_client:
        print(f"[SIMULACIÓN SHEETS] Guardando en '{pestana}': {datos}")
        return True
    try:
        import gspread
        sheet = sheets_client.open(NOMBRE_HOJA_SHEETS)
        try:
            worksheet = sheet.worksheet(pestana)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=pestana, rows="100", cols="10")
        worksheet.append_row(datos)
        return True
    except Exception as e:
        print(f"Error guardando en Sheets: {e}")
        return False
