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

# Modelos en orden de preferencia y alta disponibilidad
MODELOS_PREFERIDOS = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
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
