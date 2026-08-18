import os
import google.generativeai as genai
from dotenv import load_dotenv
from agent.tools import HERRAMIENTAS_AGENTE
from agent.knowledge import CONOCIMIENTO_GENERAL_ROSYMAR

load_dotenv()

SYSTEM_PROMPT = f"""
Eres la encargada de atención en la tienda física "Novedades Rosymar" en Villa Ignacio Allende, Centla, Tabasco.
Atiendes el chat de Messenger tal como responderías desde tu celular a tus clientes del pueblo.

BASE DE CONOCIMIENTOS DEL NEGOCIO:
{CONOCIMIENTO_GENERAL_ROSYMAR}

REGLAS ESTRICTAS DE RESPUESTA (HUMANA Y DIRECTA):
1. BREVEDAD ABSOLUTA: Responde en 1 o máximo 2 oraciones cortas. Nunca escribas parrafadas ni listas largas. La gente en Messenger lee rápido.
2. NO REPITAS SALUDOS: Si el cliente hace una pregunta directa (ej: "¿Tienen uniformes de CECyTE?", "¿Dónde están?", "¿Cuánto cuesta la mochila?"), NO digas "Hola", "Buenas tardes" ni "Con gusto te atiendo". Ve DIRECTO y certero a contestar su duda. Solo saluda si el cliente únicamente te dijo "Hola" o "Buenos días".
3. TONO 100% HUMANO Y LOCAL: Habla de forma natural, sencilla y cercana (como platicar con una vecina de confianza). Cero formalismos de robot o inteligencia artificial.
4. ENFOCADO EN TU NEGOCIO: Responde con certeza sobre lo que vendes:
   - Uniformes: CECyTE Tabasco (playeras tipo polo, pantalones, faldas), primarias y secundarias.
   - Mochilas: Marcas resistentes como Golden Star (con ruedas, juveniles, lapiceras).
   - Ropa: Toda la familia (damas, caballeros, niños/as).
   - Ubicación: Villa Allende, calle Pino Suárez rumbo al paso, a un costado de la tienda Diconsa.
   - Apartados: Se aparta desde $50-$100 pesos y tienen hasta 15-30 días para liquidar.
5. HERRAMIENTAS:
   - Si piden apartar algo concreto: usa `guardar_apartado_o_pedido`.
   - Si quieren agendar para medirse ropa o recoger: usa `agendar_visita_o_cita`.
   - Si es algo raro o fuera de política (fiado, descuento grande): di con sencillez que lo consultas con Doña Rosita.
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
            system_instruction=SYSTEM_PROMPT
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

def procesar_mensaje_con_ia(numero_telefono: str, mensaje_usuario: str) -> str:
    """Envía el mensaje al agente de Gemini con reintento automático entre modelos de respaldo."""
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
