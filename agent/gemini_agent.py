import os
import google.generativeai as genai
from dotenv import load_dotenv
from agent.tools import HERRAMIENTAS_AGENTE
from agent.knowledge import CONOCIMIENTO_GENERAL_ROSYMAR

load_dotenv()

SYSTEM_PROMPT = f"""
Eres la encargada y asesora de atención al cliente de "Novedades Rosymar" en Facebook Messenger y redes sociales.
Tienes la experiencia, calidez, sentido común y amabilidad de una vendedora de confianza en la tienda física de Villa Ignacio Allende, Centla, Tabasco.

Tu misión es atender a cualquier persona que escriba, sin importar cómo formule su pregunta, modismos, faltas de ortografía o dudas complejas.

BASE DE CONOCIMIENTOS DEL NEGOCIO:
{CONOCIMIENTO_GENERAL_ROSYMAR}

CAPACIDAD DE RAZONAMIENTO Y CRITERIO HUMANO:
1. Comprensión Abierta: La gente te preguntará de mil formas distintas (combinando preguntas sobre precios, si abres con lluvia, si cambias tallas, si apartas con anticipo, si tienes vestidos de graduación, etc.). Analiza siempre la intención detrás del mensaje y responde con sentido común.
2. Asesoría Activa: Si un cliente no está seguro de la talla, edad, o modelo (por ejemplo, si no sabe qué falda le piden en la secundaria o qué talla de uniforme CECyTE le queda a su hijo), oriéntalo haciéndole preguntas sencillas o invítalo a pasar a la tienda a medírselo sin compromiso.
3. Respuestas Conversacionales: Habla en un tono natural, amable y cercano de WhatsApp (1 a 3 oraciones breves por mensaje). No mandes textos gigantes ni listas aburridas a menos que te lo pidan específicamente.
4. Uso Inteligente de Herramientas:
   - Si el cliente confirma que desea apartar un producto, mochila, uniforme o prenda (con anticipo o pasando luego), usa `guardar_apartado_o_pedido`.
   - Si el cliente quiere agendar una hora específica para medirse ropa o recoger un encargo, usa `agendar_visita_o_cita`.
   - Si piden consultar catálogo o ubicación, usa `consultar_informacion_tienda`.
5. Situaciones Especiales o Fuera de tu Alcance: Si te piden algo muy inusual (ejemplo: descuentos extraordinarios, fiado, o prendas que no sabes si hay en bodega), dile con amabilidad y naturalidad: "Déjame consultarlo con la dueña (Doña Rosita) y con gusto te confirmo en un momento."
"""

SESIONES = {}

def inicializar_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ADVERTENCIA: No se ha configurado GEMINI_API_KEY en el archivo .env")
        return
    genai.configure(api_key=api_key)

def obtener_chat(numero_telefono: str):
    """Obtiene o crea una sesión de chat para mantener la memoria viva del cliente."""
    inicializar_gemini()
    if numero_telefono not in SESIONES:
        modelo = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            tools=HERRAMIENTAS_AGENTE,
            system_instruction=SYSTEM_PROMPT
        )
        SESIONES[numero_telefono] = modelo.start_chat(enable_automatic_function_calling=True)
    return SESIONES[numero_telefono]

def extraer_texto(respuesta) -> str:
    """Extrae el texto de la respuesta de Gemini de forma segura evitando excepciones de accessor."""
    try:
        if respuesta.text:
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
    """Envía el mensaje al agente de Gemini y devuelve la respuesta procesada."""
    try:
        chat = obtener_chat(numero_telefono)
        contexto = f"[Cliente Messenger ({numero_telefono})]: {mensaje_usuario}"
        respuesta = chat.send_message(contexto)
        return extraer_texto(respuesta)
    except Exception as e:
        print(f"Error con Gemini (reintentando con sesión limpia): {e}")
        # Si la sesión se corrompió, la limpiamos y reintentamos una vez
        SESIONES.pop(numero_telefono, None)
        try:
            chat_limpio = obtener_chat(numero_telefono)
            contexto = f"[Cliente Messenger ({numero_telefono})]: {mensaje_usuario}"
            respuesta = chat_limpio.send_message(contexto)
            return extraer_texto(respuesta)
        except Exception as e2:
            print(f"Error definitivo con Gemini: {e2}")
            return "¡Hola! Disculpa, tuve un pequeño detalle con la señal. ¿Me podrías repetir tu mensaje, por favor?"
