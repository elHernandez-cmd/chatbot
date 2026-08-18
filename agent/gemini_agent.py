import os
import google.generativeai as genai
from datetime import datetime, timedelta
from dotenv import load_dotenv
from agent.services import (
    obtener_existencias_actuales,
    CURRENT_SENDER_ID,
    crear_apartado_memoria,
    guardar_fila_sheets,
    insertar_evento_calendar
)

load_dotenv()

# --- 1. CONOCIMIENTO GENERAL DEL NEGOCIO ---
CONOCIMIENTO_GENERAL_ROSYMAR = """
SOBRE EL NEGOCIO Y UBICACIÓN:
- Nombre: Novedades Rosymar
- Tipo de tienda: Establecimiento local de ropa para toda la familia, mochilas y uniformes escolares.
- Ubicación: Villa Ignacio Allende, Centla, Tabasco, México.
- Referencias: Calle José María Pino Suárez, rumbo al paso (embarcadero fluvial), a un costado de la tienda Diconsa (a dos cuadras del parque central).
- Facebook: https://www.facebook.com/profile.php?id=61578993366170

HORARIOS Y ATENCIÓN:
- Horario de tienda: Lunes a Sábado de 8:00 AM a 7:00 PM. Domingos cerrado.

PRODUCTOS Y MARCAS:
1. Uniformes Escolares:
   - CECyTE Tabasco (playeras polo con logo, pantalones de vestir, faldas y pants deportivos).
   - Escuelas Primarias y Secundarias locales (camisas blancas, faldas, pantalones, calcetas).
2. Mochilas y Accesorios:
   - Mochilas escolares de alta resistencia (Golden Star y más), mochilas con ruedas, juveniles, lapiceras y loncheras.
3. Ropa para toda la familia:
   - Damas, caballeros, niños, niñas y vestidos especiales.

POLÍTICAS DE PAGO Y APARTADOS:
- Pagos: Efectivo y Transferencias bancarias.
- Sistema de Apartado: Anticipo de $50 o $100 pesos con plazo máximo de 15 días para liquidar.
- Cambios de talla: Se aceptan cambios si la prenda está limpia, con etiquetas y en perfecto estado.
"""

# --- 2. HERRAMIENTAS DIRECTAS PARA EL AGENTE DE GEMINI ---
def consultar_informacion_tienda(tema: str) -> dict:
    """
    Consulta información de uniformes, mochilas, ropa, ubicación y redes sociales de Novedades Rosymar.
    Args:
        tema: 'ubicacion', 'uniformes', 'mochilas', 'ropa', 'facebook'.
    """
    datos = {
        "ubicacion": "Estamos en Villa Ignacio Allende, Centla, Tabasco. Sobre la calle José María Pino Suárez, rumbo al paso, a un costado de Diconsa.",
        "uniformes": "Manejamos uniformes para CECyTE Tabasco (playeras, pantalones, faldas) y también para primarias y secundarias de la zona.",
        "mochilas": "Gran variedad de mochilas escolares resistentes (marca Golden Star y más) para todos los grados.",
        "ropa": "Ropa de calidad para toda la familia: damas, caballeros, niños y vestidos para ocasiones especiales.",
        "facebook": "Visita nuestro Facebook: https://www.facebook.com/profile.php?id=61578993366170"
    }
    return {"informacion": datos.get(str(tema).lower(), "Ofrecemos uniformes escolares CECyTE, mochilas Golden Star y ropa para toda la familia.")}

def guardar_apartado_o_pedido(nombre_cliente: str, telefono: str, articulo_y_talla: str) -> dict:
    """
    Registra un apartado de ropa, uniforme o mochila en la memoria del bot y en Google Sheets con plazo de 15 días.
    Args:
        nombre_cliente: Nombre de quien aparta.
        telefono: Teléfono de WhatsApp.
        articulo_y_talla: Artículo y talla exacta (ej: 'Playera CECyTE Talla M').
    """
    try:
        crear_apartado_memoria(nombre_cliente, telefono, articulo_y_talla)
        guardar_fila_sheets(
            pestana="Apartados_y_Pedidos",
            datos=[
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                nombre_cliente,
                telefono,
                articulo_y_talla,
                "Pendiente de Entrega / Pago (15 días de plazo)"
            ]
        )
        return {"status": "success", "mensaje": f"Apartado guardado para {nombre_cliente}: {articulo_y_talla} (Plazo 15 días)."}
    except Exception as e:
        return {"status": "error", "mensaje": str(e)}

def agendar_visita_o_cita(nombre_cliente: str, telefono: str, fecha: str, hora: str, motivo: str) -> dict:
    """
    Agenda una visita o cita en Google Calendar y Sheets (ej: para medirse uniformes).
    Args:
        nombre_cliente: Nombre del cliente.
        telefono: Teléfono del cliente.
        fecha: Fecha en formato AAAA-MM-DD (ej: 2026-08-20).
        hora: Hora en formato 24h (ej: 17:00).
        motivo: Motivo de la cita (ej: 'Medición de uniforme CECyTE').
    """
    try:
        inicio = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
        fin = inicio + timedelta(minutes=30)
        insertar_evento_calendar(
            titulo=f"Visita: {nombre_cliente} ({motivo})",
            fecha_inicio_iso=inicio.isoformat(),
            fecha_fin_iso=fin.isoformat(),
            descripcion=f"Cliente: {nombre_cliente}\nTeléfono: {telefono}\nMotivo: {motivo}"
        )
        guardar_fila_sheets(
            pestana="Visitas_Agendadas",
            datos=[datetime.now().strftime("%Y-%m-%d %H:%M"), nombre_cliente, telefono, f"{fecha} {hora}", motivo]
        )
        return {"status": "success", "mensaje": f"Visita confirmada para el {fecha} a las {hora}."}
    except Exception as e:
        return {"status": "error", "mensaje": str(e)}

HERRAMIENTAS_AGENTE = [
    consultar_informacion_tienda,
    guardar_apartado_o_pedido,
    agendar_visita_o_cita
]

# --- 3. SYSTEM PROMPT Y MODELOS DE GEMINI ---
def obtener_system_prompt() -> str:
    existencias = obtener_existencias_actuales()
    return f"""
Eres la encargada de atención en la tienda física "Novedades Rosymar" en Villa Ignacio Allende, Centla, Tabasco.
Atiendes el chat de Messenger tal como responderías desde tu celular a tus clientes, con máxima disposición de servicio y amabilidad.

BASE DE CONOCIMIENTOS DEL NEGOCIO:
{CONOCIMIENTO_GENERAL_ROSYMAR}

EXISTENCIAS E INVENTARIO ACTUALIZADO EN TIEMPO REAL:
{existencias}

REGLAS ESTRICTAS DE RESPUESTA (ULTRA CONCRETA, SERVICIAL Y CON NEGRITAS):
1. TRATO SERVICIAL Y AMABLE: Mantén siempre un tono muy atento, educado y servicial.
2. RESPUESTAS ULTRA CORTAS Y CONCRETAS: Ve directo al grano en 1 sola oración corta (máximo 2 oraciones muy breves). Sin introducciones largas ni rodeos.
3. USO DE NEGRITAS EN DATOS CLAVE: Resalta siempre los datos más importantes en **negritas** (ej: **horarios**, **plazo de 15 días**, **$50 o $100**, **CECyTE**, **Golden Star**, **ubicación**).
4. CONSULTA DE EXISTENCIAS: Revisa las EXISTENCIAS EN TIEMPO REAL para responder con exactitud si un artículo está disponible o agotado.
5. NO REPITAS SALUDOS: Si el cliente hace una pregunta directa (ej: "¿Tienen mochilas?", "¿Abren hoy?"), responde directo a su duda sin poner "Hola" en cada mensaje. Solo saluda si el cliente envió únicamente un saludo.
6. HORARIO EXACTO: Atendemos de **Lunes a Sábado de 8:00 AM a 7:00 PM** (**domingos cerrado**).
7. APARTADOS Y POLÍTICAS:
   - Apartados con anticipo de **$50 o $100 pesos** y plazo de **15 días** para liquidar.
   - Si piden apartar algo: usa la herramienta `guardar_apartado_o_pedido`.
   - Si quieren agendar para medirse o recoger: usa `agendar_visita_o_cita`.
   - Si piden fiado o descuento: diles amablemente que lo consultarás con la encargada.
"""

MODELOS_PREFERIDOS = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-3.7-flash"
]

SESIONES = {}

def inicializar_gemini() -> bool:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ADVERTENCIA: Falta GEMINI_API_KEY en variables de entorno")
        return False
    genai.configure(api_key=api_key)
    return True

def obtener_chat(numero_telefono: str, modelo_idx: int = 0):
    if not inicializar_gemini():
        return None
    model_name = MODELOS_PREFERIDOS[modelo_idx % len(MODELOS_PREFERIDOS)]
    clave_sesion = f"{numero_telefono}_{model_name}"
    if clave_sesion not in SESIONES:
        try:
            modelo = genai.GenerativeModel(
                model_name=model_name,
                tools=HERRAMIENTAS_AGENTE,
                system_instruction=obtener_system_prompt()
            )
            SESIONES[clave_sesion] = modelo.start_chat(enable_automatic_function_calling=True)
        except Exception as e:
            print(f"Error iniciando modelo {model_name}: {e}")
            return None
    return SESIONES.get(clave_sesion)

def extraer_texto(respuesta) -> str:
    try:
        if hasattr(respuesta, "text") and respuesta.text:
            return respuesta.text.strip()
    except Exception:
        pass
    try:
        if hasattr(respuesta, "candidates") and respuesta.candidates:
            partes = []
            for part in respuesta.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    partes.append(part.text)
            if partes:
                return " ".join(partes).strip()
    except Exception:
        pass
    return "¡Hola! Con gusto te atiendo en Novedades Rosymar. ¿En qué prenda, mochila o uniforme te puedo ayudar hoy?"

def procesar_mensaje_con_ia(numero_telefono: str, mensaje_usuario: str) -> str:
    """Procesa el mensaje con IA de forma resiliente ante cualquier excepción."""
    CURRENT_SENDER_ID.set(str(numero_telefono))
    contexto = f"[Cliente Messenger ({numero_telefono})]: {mensaje_usuario}"
    
    for idx, nombre_modelo in enumerate(MODELOS_PREFERIDOS):
        try:
            chat = obtener_chat(numero_telefono, modelo_idx=idx)
            if not chat:
                continue
            respuesta = chat.send_message(contexto)
            texto_final = extraer_texto(respuesta)
            if texto_final:
                return texto_final
        except Exception as e:
            print(f"Aviso modelo {nombre_modelo}: {e}. Probando respaldo...")
            SESIONES.pop(f"{numero_telefono}_{nombre_modelo}", None)
            
    return "¡Hola! Con gusto te atiendo en **Novedades Rosymar**. ¿En qué uniforme escolar, mochila o prenda te puedo apoyar?"
