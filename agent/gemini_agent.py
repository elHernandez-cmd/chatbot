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

CATÁLOGO OFICIAL DE UNIFORMES ESCOLARES EN VENTA:
1. Preescolar:
   - Las Flores
   - Comunitario
   - Benito Juárez García
   - José María Pino Suárez
   - María Montessori
2. Primarias:
   - Domingo Faustino Sarmiento
   - Emiliano Zapata
   - Benito Juárez
   - José María Pino Suárez
   - Vicente Suárez
3. Secundarias y Telesecundarias:
   - Ignacio Allende
   - Técnica Núm. 4
   - Tomás Garrido Canabal
   - Guadalupe Victoria
   - Álvaro de la Cruz
   - Ignacio Zaragoza
4. Nivel Medio Superior / Bachilleratos:
   - CECyTE Tabasco
   - COBATAB 18
(Prendas disponibles: playeras polo con logo bordado, camisas, pantalones de vestir, faldas, calcetas y pants deportivos).

MOCHILAS Y ACCESORIOS:
- Mochilas escolares resistentes (marca Golden Star y más), mochilas con ruedas, juveniles, lapiceras y loncheras.

ROPA PARA TODA LA FAMILIA:
- Damas, caballeros, niños, niñas y vestidos especiales.

POLÍTICAS DE PAGO Y APARTADOS:
- Pagos: Efectivo y Transferencias bancarias.
- Sistema de Apartado (Cualquier artículo se aparta con un anticipo de $50 o $100 pesos):
  * **Uniformes Escolares y Mochilas:** Plazo de **3 días** para liquidar (apartando con **$50 o $100 pesos**).
  * **Ropa y demás artículos:** Plazo de **15 días** para liquidar (apartando con **$50 o $100 pesos**).
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
        "uniformes": (
            "Manejamos uniformes para: Preescolares (Las Flores, Comunitario, Benito Juárez, Pino Suárez, Montessori), "
            "Primarias (Sarmiento, Zapata, Benito Juárez, Pino Suárez, Vicente Suárez), "
            "Secundarias/Telesecundarias (Ignacio Allende, Técnica 4, Tomás Garrido, Guadalupe Victoria, Álvaro de la Cruz, Zaragoza), "
            "CECyTE y COBATAB 18."
        ),
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
            "mensaje": f"¡Listo! Ya quedó apartado tu {articulo_y_talla} para {nombre_real}. Lo apartas con $50 o $100 pesos y tienes {dias} días para pasar a liquidar."
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
                f"- {a['articulo']} para {a['nombre']}. Apartado el {a['fecha']} a las {a['hora']}. Plazo: {a['plazo_total']} días (te quedan {a['dias_restantes']} días)."
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
Respondes desde tu celular por Messenger a tus clientes.

BASE DE CONOCIMIENTOS:
{CONOCIMIENTO_GENERAL_ROSYMAR}

EXISTENCIAS EN TIEMPO REAL:
{existencias}

REGLAS DE RESPUESTA (HUMANA, ULTRA CORTA Y NATURAL):
1. TONO HUMANO Y NATURAL (CERO ROBÓTICO): Habla como una persona real en Messenger: sencilla, amable y directa. PROHIBIDO usar frases de robot o IA como "¡Hola! Claro que sí, con mucho gusto", "¿En qué más te puedo colaborar?", etc.
2. RESPUESTAS ULTRA CORTAS: Responde estrictamente en 1 sola oración corta (máximo 10 a 15 palabras). Ve directo al grano.
3. NEGRITAS EN DATOS CLAVE: Usa **negritas** en lo esencial (**Villa Ignacio Allende**, **CECyTE**, **Golden Star**, **3 días**, **15 días**, **$50 o $100 pesos**).
4. UBICACIÓN:
   - **Ubicación:** **Villa Ignacio Allende**
   - **Referencias:** **Calle José María Pino Suárez, rumbo al paso a un costado de la Tienda Diconsa**
5. NUNCA INVENTES NOMBRES: Si preguntan quién atiende o mencionan nombres de personas, di únicamente que hablarás con **la encargada**.
6. MEMORIA ESTRICTA DE PRODUCTO: Si ya hablaron de un producto (ej: uniforme CECyTE) y luego preguntan precios o tallas, responde directo sobre ese producto. PROHIBIDO preguntar "¿De qué producto buscas?".
7. HORARIO: **Lunes a Sábado de 8:00 AM a 7:00 PM** (**domingos cerrado**).
8. NO REPITAS SALUDOS: Si ya están platicando, no vuelvas a saludar.
9. APARTADOS Y FÓRMULA EXACTA DE CONFIRMACIÓN:
   - **Anticipo para apartar:** Cualquier producto se aparta con un anticipo de **$50 o $100 pesos**.
   - **Plazos para liquidar:**
     * **Uniformes Escolares y Mochilas:** Tienen **3 días** para liquidar.
     * **Ropa y demás artículos:** Tienen **15 días** para liquidar.
   - CERO PREGUNTAS DE DATOS: No pidas nombre ni teléfono. Ejecuta `guardar_apartado_o_pedido(articulo_y_talla)` de inmediato.
   - FÓRMULA EXACTA Y CLARA AL CONFIRMAR (Di exactamente esto):
     «¡Listo! Ya quedó apartado tu [producto] para [nombre_cliente]. Lo apartas con $50 o $100 pesos y tienes [3 días / 15 días] para pasar a liquidar.»
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
    return "¡Hola! Con gusto te atiendo en Novedades Rosymar. ¿En qué te puedo ayudar hoy?"

def procesar_mensaje_con_ia(numero_telefono: str, mensaje_usuario: str) -> str:
    """Procesa el mensaje con IA de forma humana, ultra corta y resiliente."""
    CURRENT_SENDER_ID.set(str(numero_telefono))
    perfil = obtener_perfil_messenger(numero_telefono)
    nombre_perfil = perfil.get("nombre", "Cliente")
    
    contexto = f"[Cliente de Messenger: {nombre_perfil}]: {mensaje_usuario}"
    
    for idx, nombre_modelo in enumerate(MODELOS_PREFERIDOS):
        try:
            chat = obtener_chat(numero_telefono, modelo_idx=idx)
            if not chat:
                continue
            respuesta = chat.send_message(contexto)
            texto_final = extraer_texto(respuesta)
            if texto_final:
                # Guardar el intercambio en memoria persistente
                guardar_intercambio_historial(numero_telefono, mensaje_usuario, texto_final)
                return texto_final
        except Exception as e:
            print(f"Aviso modelo {nombre_modelo}: {e}. Probando respaldo...")
            SESIONES.pop(f"{numero_telefono}_{nombre_modelo}", None)
            
    return "¡Hola! Con gusto te atiendo en **Novedades Rosymar**. ¿Qué prenda o uniforme buscas?"
