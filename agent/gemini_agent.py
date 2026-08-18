import os
import google.generativeai as genai
from dotenv import load_dotenv
from agent.tools import HERRAMIENTAS_AGENTE
from agent.knowledge import CONOCIMIENTO_GENERAL_ROSYMAR
from agent.stock_manager import obtener_existencias_actuales

load_dotenv()

def obtener_system_prompt() -> str:
    """Genera el System Prompt inyectando el inventario y existencias más recientes en tiempo real."""
    existencias = obtener_existencias_actuales()
    return f"""
Eres la encargada de atención en la tienda física "Novedades Rosymar" en Villa Ignacio Allende, Centla, Tabasco.
Atiendes el chat de Messenger tal como responderías desde tu celular a tus clientes, con máxima disposición de servicio y amabilidad.

BASE DE CONOCIMIENTOS DEL NEGOCIO:
{CONOCIMIENTO_GENERAL_ROSYMAR}

EXISTENCIAS E INVENTARIO ACTUALIZADO EN TIEMPO REAL:
{existencias}

REGLAS ESTRICTAS DE RESPUESTA (ULTRA CONCRETA, SERVICIAL Y CON NEGRITAS):
1. TRATO SERVICIAL Y AMABLE: Mantén siempre un tono muy atento, educado y servicial, tal como una encargada atiende en persona.
2. RESPUESTAS ULTRA CORTAS Y CONCRETAS: Ve directo al grano en 1 sola oración corta (máximo 2 oraciones muy breves). Sin introducciones largas ni rodeos innecesarios.
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

# Modelos en orden de preferencia, máxima velocidad y alta disponibilidad
MODELOS_PREFERIDOS = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-3.7-flash"
]

SESIONES = {}

def inicializar_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ADVERTENCIA: No se ha configurado GEMINI_API_KEY en el archivo .env")
        return False
    genai.configure(api_key=api_key)
    return True

def obtener_chat(numero_telefono: str, modelo_idx: int = 0):
    """Obtiene o crea una sesión de chat para mantener la memoria viva del cliente."""
    if not inicializar_gemini():
        return None
        
    model_name = MODELOS_PREFERIDOS[modelo_idx % len(MODELOS_PREFERIDOS)]
    clave_sesion = f"{numero_telefono}_{model_name}"
    
    if clave_sesion not in SESIONES:
        modelo = genai.GenerativeModel(
            model_name=model_name,
            tools=HERRAMIENTAS_AGENTE,
            system_instruction=obtener_system_prompt()
        )
        SESIONES[clave_sesion] = modelo.start_chat(enable_automatic_function_calling=True)
    return SESIONES[clave_sesion]

def extraer_texto(respuesta) -> str:
    """Extrae el texto de la respuesta de Gemini de forma segura evitando excepciones de accessor."""
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
    except Exception as e:
        print(f"Error extrayendo candidatos: {e}")
        
    return "¡Hola! Con gusto te atiendo en Novedades Rosymar. ¿En qué prenda, mochila o uniforme te puedo ayudar hoy?"

from agent.apartados_manager import CURRENT_SENDER_ID

def procesar_mensaje_con_ia(numero_telefono: str, mensaje_usuario: str) -> str:
    """Envía el mensaje al agente de Gemini con reintento automático entre modelos de respaldo."""
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
            print(f"Aviso con modelo {nombre_modelo}: {e}. Probando respaldo...")
            # Limpiar sesión corrupta si aplica
            SESIONES.pop(f"{numero_telefono}_{nombre_modelo}", None)
            
    # Respuesta cálida de respaldo si todos los modelos fallaran
    return "¡Hola! Con gusto te atiendo en Novedades Rosymar. ¿Qué uniforme escolar, mochila o prenda de vestir estás buscando hoy?"
