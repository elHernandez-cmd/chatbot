import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ADMIN_PIN = os.getenv("ADMIN_PIN", "RosymarAdmin2026").strip()
ADMIN_SENDER_IDS_ENV = os.getenv("ADMIN_SENDER_IDS", "").strip()

# Conjunto en memoria de administradores autorizados
ADMINISTRADORES = set([s.strip() for s in ADMIN_SENDER_IDS_ENV.split(",") if s.strip()])

# Archivo de persistencia para existencias
STOCK_FILE = "/tmp/stock_rosymar.json" if os.path.exists("/tmp") else os.path.join(os.path.dirname(__file__), "stock_rosymar.json")

# Existencias por defecto
EXISTENCIAS_DEFAULT = """- Uniformes CECyTE (playeras, pantalones, faldas): En existencia.
- Uniformes de Primaria y Secundaria de la zona: En existencia.
- Mochilas escolares Golden Star (juveniles, con ruedas y lapiceras): En existencia.
- Ropa para toda la familia (damas, caballeros, niños): En existencia."""

def obtener_existencias_actuales() -> str:
    """Retorna el texto actual de inventario y existencias."""
    try:
        if os.path.exists(STOCK_FILE):
            with open(STOCK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("existencias", EXISTENCIAS_DEFAULT)
    except Exception as e:
        print(f"Aviso leyendo inventario: {e}")
    return EXISTENCIAS_DEFAULT

def guardar_existencias(texto_nuevas_existencias: str, admin_id: str = "Admin") -> bool:
    """Guarda las existencias actualizadas por un administrador."""
    try:
        data = {
            "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "actualizado_por": admin_id,
            "existencias": texto_nuevas_existencias.strip()
        }
        with open(STOCK_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error guardando existencias: {e}")
        return False

def es_administrador(sender_id: str) -> bool:
    """Verifica si un sender_id está registrado como administrador."""
    return sender_id in ADMINISTRADORES

def registrar_administrador(sender_id: str):
    """Registra un nuevo sender_id como administrador verificado."""
    if sender_id:
        ADMINISTRADORES.add(sender_id)

def procesar_comando_admin(sender_id: str, mensaje: str):
    """
    Procesa comandos de administración que inicien con diagonal (/):
    /actualizar, /verinventario, /limpiarinventario.
    Retorna (es_comando: bool, respuesta: str)
    """
    msg = mensaje.strip()
    if not msg.startswith("/"):
        return False, ""
        
    partes = msg.split(maxsplit=1)
    comando = partes[0].lower()
    resto = partes[1].strip() if len(partes) > 1 else ""
    
    # Comprobar que sea exactamente uno de los comandos válidos (sin alias)
    comandos_validos = ["/actualizar", "/verinventario", "/limpiarinventario"]
    if comando not in comandos_validos:
        return False, ""
    
    # 1. Autorización de administrador
    autorizado = es_administrador(sender_id)
    
    # Si incluye el PIN de administrador en el mensaje, lo autorizamos de inmediato
    if ADMIN_PIN and ADMIN_PIN.lower() in msg.lower():
        autorizado = True
        registrar_administrador(sender_id)
        # Limpiar el PIN del texto restante
        resto = resto.replace(ADMIN_PIN, "").replace(ADMIN_PIN.lower(), "").strip()
        
    if not autorizado:
        return True, (
            "⛔ **Acceso Restringido**: Este comando es exclusivo para administradores de **Novedades Rosymar**.\n"
            "Para autenticarte, incluye tu PIN de administrador en el comando. Ejemplos:\n"
            "• `/actualizar PIN_SECRETO tus existencias...`\n"
            "• `/verinventario PIN_SECRETO`\n"
            "• `/limpiarinventario PIN_SECRETO`"
        )
        
    # 2. Ejecutar comandos estrictos (sin alias)
    if comando == "/actualizar":
        if not resto:
            return True, (
                "ℹ️ **Uso del comando**: Escribe `/actualizar` seguido de las existencias o productos.\n"
                "👉 Ejemplo: `/actualizar Llegaron faldas CECyTE talla 32 y se agotaron los pants deportivos.`"
            )
            
        guardar_existencias(resto, admin_id=sender_id)
        return True, (
            "✅ **¡Inventario actualizado con éxito!**\n\n"
            f"📦 **Nuevas existencias registradas:**\n{resto}\n\n"
            "🤖 A partir de este momento, el chatbot informará estas existencias a los clientes con exactitud."
        )
        
    elif comando == "/verinventario":
        existencias = obtener_existencias_actuales()
        return True, (
            "📋 **Inventario y Existencias Actuales en el Chatbot:**\n\n"
            f"{existencias}\n\n"
            "*(Para actualizar existencias, envía: `/actualizar <nuevos datos>`)*"
        )
        
    elif comando == "/limpiarinventario":
        guardar_existencias(EXISTENCIAS_DEFAULT, admin_id=sender_id)
        return True, "🔄 **Inventario restablecido** a los valores predeterminados de la tienda."
        
    return False, ""
