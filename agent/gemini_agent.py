import os
import google.generativeai as genai
from datetime import datetime, timedelta
from dotenv import load_dotenv
from agent.services import (
    obtener_existencias_actuales,
    CURRENT_SENDER_ID,
    crear_apartado_memoria,
    consultar_apartados_cliente,
    guardar_fila_sheets,
    obtener_historial_usuario,
    guardar_intercambio_historial,
    obtener_perfil_messenger
)

load_dotenv()

# --- 1. CONOCIMIENTO GENERAL DEL NEGOCIO ---
CONOCIMIENTO_GENERAL_ROSYMAR = """
SOBRE EL NEGOCIO Y UBICACIÓN:
- Nombre: Novedades Rosymar
- Tipo de tienda: Establecimiento de ropa para toda la familia, mochilas y uniformes escolares.
- Ubicación: Villa Ignacio Allende
- Referencias: Calle José María Pino Suárez, rumbo al paso a un costado de la Tienda Diconsa
- Facebook: https://www.facebook.com/profile.php?id=61578993366170

HORARIOS Y ATENCIÓN:
- Horario de tienda: Lunes a Sábado de 8:00 AM a 7:00 PM. Domingos cerrado.

PRODUCTOS Y MARCAS:
1. Uniformes Escolares:
   - CECyTE Tabasco (playeras polo con logo, pantalones de vestir, faldas y pants deportivos).
   - Escuelas Primarias y Secundarias de la zona (camisas blancas, faldas, pantalones, calcetas).
2. Mochilas y Accesorios:
   - Mochilas escolares resistentes (marca Golden Star y más), mochilas con ruedas, juveniles, lapiceras y loncheras.
3. Ropa para toda la familia:
   - Damas, caballeros, niños, niñas y vestidos especiales.

POLÍTICAS DE PAGO Y APARTADOS:
- Pagos: Efectivo y Transferencias bancarias.
- Sistema de Apartado (Se aparta con un anticipo de $50 o $100 pesos para cualquier artículo):
  * **Uniformes Escolares:** Plazo de **3 días** para liquidar (apartando con **$50 o $100 pesos**).
  * **Mochilas, Ropa y demás artículos:** Plazo de **15 días** para liquidar (apartando con **$50 o $100 pesos**).
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
        "ubicacion": "Estamos en **Villa Ignacio Allende**.\n**Referencias:** Calle José María Pino Suárez, rumbo al paso a un costado de la Tienda Diconsa.",
        "uniformes": "Manejamos uniformes para CECyTE Tabasco (playeras, pantalones, faldas) y también para primarias y secundarias de la zona.",
        "mochilas": "Gran variedad de mochilas escolares resistentes (marca Golden Star y más) para todos los grados.",
        "ropa": "Ropa de calidad para toda la familia: damas, caballeros, niños y vestidos para ocasiones especiales.",
        "facebook": "Visita nuestro Facebook: https://www.facebook.com/profile.php?id=61578993366170"
    }
    return {"informacion": datos.get(str(tema).lower(), "Estamos en **Villa Ignacio Allende**. **Referencias:** Calle José María Pino Suárez, rumbo al paso a un costado de la Tienda Diconsa.")}

def guardar_apartado_o_pedido(articulo_y_talla: str, nombre_cliente: str = "", telefono: str = "") -> dict:
    """
    Registra un apartado en automático en la memoria del bot y en Google Sheets sin pedirle datos al cliente.
    El sistema obtiene su nombre automáticamente de su perfil de Messenger.
    Args:
        articulo_y_talla: Artículo y talla exacta (ej: 'Playera CECyTE Talla M', 'Mochila Golden Star con ruedas').
        nombre_cliente: (Opcional) Nombre si el cliente lo mencionó, sino se obtiene en automático de Messenger.
        telefono: (Opcional) Teléfono si el cliente lo dio en el chat.
    """
    try:
        s_id = CURRENT_SENDER_ID.get()
        if not nombre_cliente:
            perfil = obtener_perfil_messenger(s_id)
            nombre_cliente = perfil.get("nombre", "Cliente")
        if not telefono:
            perfil = obtener_perfil_messenger(s_id)
            telefono = perfil.get("telefono", "Chat Messenger")
            
        nuevo = crear_apartado_memoria(nombre_cliente, telefono, articulo_y_talla, sender_id=s_id)
        dias = nuevo.get("dias_plazo", 15)
        nombre_real = nuevo.get("nombre_cliente", nombre_cliente)
        
        guardar_fila_sheets(
            pestana="Apartados_y_Pedidos",
            datos=[
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                nombre_real,
                telefono,
                articulo_y_talla,
                f"Pendiente de Entrega / Pago ({dias} días de plazo)"
            ]
        )
        return {
            "status": "success",
            "mensaje": f"Apartado registrado con éxito a nombre de {nombre_real}: {articulo_y_talla}. Plazo: {dias} días para liquidar con anticipo de $50 o $100 pesos."
        }
    except Exception as e:
        return {"status": "error", "mensaje": str(e)}

def consultar_mi_apartado() -> dict:
    """
    Consulta los apartados vigentes registrados en este chat, indicando fecha, hora, artículo y días restantes.
    """
    try:
        apartados = consultar_apartados_cliente()
        if not apartados:
            return {"apartados": "No tienes ningún apartado activo registrado en este chat actualmente."}
        
        info = []
        for a in apartados:
            info.append(
                f"- Artículo: {a['articulo']} (a nombre de {a['nombre']}). "
                f"Apartado el {a['fecha']} a las {a['hora']}. "
                f"Plazo: {a['plazo_total']} días (te quedan {a['dias_restantes']} días para liquidar)."
            )
        return {"apartados": "\n".join(info)}
    except Exception as e:
        return {"error": str(e)}

HERRAMIENTAS_AGENTE = [
    consultar_informacion_tienda,
    guardar_apartado_o_pedido,
    consultar_mi_apartado
]

# --- 3. SYSTEM PROMPT Y MODELOS DE GEMINI ---
def obtener_system_prompt() -> str:
    existencias = obtener_existencias_actuales()
    return f"""
Eres la encargada de atención en la tienda física "Novedades Rosymar" en Villa Ignacio Allende.
Atiendes el chat de Messenger tal como responderías desde tu celular a tus clientes, con máxima disposición de servicio y amabilidad.

BASE DE CONOCIMIENTOS DEL NEGOCIO:
{CONOCIMIENTO_GENERAL_ROSYMAR}

EXISTENCIAS E INVENTARIO ACTUALIZADO EN TIEMPO REAL:
{existencias}

REGLAS ESTRICTAS DE RESPUESTA (ULTRA CONCRETA, SERVICIAL Y CON NEGRITAS):
1. TRATO SERVICIAL Y AMABLE: Mantén siempre un tono muy atento, educado y servicial.
2. RESPUESTAS ULTRA CORTAS Y CONCRETAS: Ve directo al grano en 1 sola oración corta (máximo 2 oraciones muy breves). Sin introducciones largas ni rodeos.
3. USO DE NEGRITAS EN DATOS CLAVE: Resalta siempre los datos más importantes en **negritas** (ej: **horarios**, **plazo de 3 días** o **15 días**, **$50 o $100**, **CECyTE**, **Golden Star**, **Villa Ignacio Allende**).
4. UBICACIÓN Y REFERENCIAS DE LA TIENDA:
   - **Ubicación:** **Villa Ignacio Allende**
   - **Referencias:** **Calle José María Pino Suárez, rumbo al paso a un costado de la Tienda Diconsa**
   - Cuando pregunten por ubicación o cómo llegar, responde exactamente con estos dos datos claros.
5. NUNCA INVENTES NOMBRES: Está estrictamente prohibido inventar nombres de personas o seguirle el juego a nombres que mencione el cliente. Si preguntan quién atiende o piden hablar con alguien, di únicamente que hablarás con **la encargada** o que te comunicas de parte de **la encargada**.
6. RECUERDO Y MEMORIA ESTRICTA DEL PRODUCTO EN LA CONVERSACIÓN:
   - Si el cliente mencionó un producto (ej: "uniforme CECyTE para dama", "mochila Golden Star", "pants", etc.) y luego pregunta "¿Qué precios?", "¿Cuánto cuesta?", "¿Qué tallas tienes?", etc., ASUME INMEDIATAMENTE que se refiere al producto del que acaban de hablar.
   - ESTÁ ESTRICTAMENTE PROHIBIDO preguntar "¿De qué artículo te interesa el precio?" si ya se mencionó un producto en los mensajes previos. Responde directo con los datos o precios de ese producto específico.
7. NO REPITAS SALUDOS NI PREGUNTAS: Si el cliente hace una pregunta directa o continúa la conversación, responde directo a su duda sin poner "Hola" ni repetir saludos.
8. HORARIO EXACTO: Atendemos de **Lunes a Sábado de 8:00 AM a 7:00 PM** (**domingos cerrado**).
9. CONTINUIDAD EN MENSAJES Y AUDIOS SEGUIDOS: Si el cliente manda varios audios o mensajes seguidos, mantén el hilo de la plática, responde a lo nuevo y jamás repitas preguntas que ya se contestaron.
10. POLÍTICAS DE APARTADOS Y AUTOMATIZACIÓN TOTAL:
   - Cualquier artículo se aparta con un anticipo de **$50 o $100 pesos**.
   - **Solo los Uniformes Escolares:** Tienen un plazo de **3 días** para liquidar (apartando con **$50 o $100 pesos**).
   - **Todo lo demás (Mochilas, Ropa de toda la familia, etc.):** Tienen un plazo de **15 días** para liquidar (apartando igualmente con **$50 o $100 pesos**).
   - NUNCA PIDAS NOMBRE NI NÚMERO DE TELÉFONO: Si el cliente dice que quiere apartar una prenda o producto, NO le pidas sus datos; ejecuta directamente `guardar_apartado_o_pedido(articulo_y_talla)`. El sistema obtiene su nombre automáticamente de su perfil de Messenger.
   - Confírmale de inmediato que su apartado quedó registrado **a su nombre** con el anticipo de **$50 o $100 pesos** y su respectivo plazo (**3 días** para uniformes o **15 días** para lo demás).
   - Si el cliente pregunta por su apartado o pedido, usa la herramienta `consultar_mi_apartado` para recordarle la hora, el día y el artículo que tiene apartado.
   - Si piden fiado o descuento: diles amablemente que lo consultarás con la encargada.
"""

MODELOS_PREFERIDOS = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest"
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
            # Reconstruir el historial persistente para no perder la memoria entre peticiones
            historial_previo = obtener_historial_usuario(numero_telefono)
            formato_history = []
            for h in historial_previo:
                formato_history.append({
                    "role": h.get("role", "user"),
                    "parts": h.get("parts", [""])
                })
            SESIONES[clave_sesion] = modelo.start_chat(
                history=formato_history,
                enable_automatic_function_calling=True
            )
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
    
    for idx, nombre_modelo in enumerate(MODELOS_PREFERIDOS):
        try:
            chat = obtener_chat(numero_telefono, modelo_idx=idx)
            if not chat:
                continue
            respuesta = chat.send_message(mensaje_usuario)
            texto_final = extraer_texto(respuesta)
            if texto_final:
                # Guardar el intercambio en memoria persistente
                guardar_intercambio_historial(numero_telefono, mensaje_usuario, texto_final)
                return texto_final
        except Exception as e:
            print(f"Aviso modelo {nombre_modelo}: {e}. Probando respaldo...")
            SESIONES.pop(f"{numero_telefono}_{nombre_modelo}", None)
            
    return "¡Hola! Con gusto te atiendo en **Novedades Rosymar**. ¿En qué uniforme escolar, mochila o prenda te puedo apoyar?"
