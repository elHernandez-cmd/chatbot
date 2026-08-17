from datetime import datetime, timedelta
from agent.google_services import insertar_evento_calendar, guardar_fila_sheets

def consultar_informacion_tienda(tema: str) -> dict:
    """
    Consulta información detallada de productos, uniformes, ubicación y referencias de Novedades Rosymar.
    
    Args:
        tema: Tema de la consulta ('ubicacion', 'uniformes', 'mochilas', 'ropa', 'facebook').
    """
    datos = {
        "ubicacion": "Estamos en Villa Ignacio Allende, Centla, Tabasco. Sobre la calle José María Pino Suárez, rumbo al paso, a un costado de la tienda Diconsa (a dos cuadras del parque central).",
        "uniformes": "Manejamos uniformes para CECyTE Tabasco (playeras, pantalones, faldas) y también para escuelas primarias y secundarias de la zona.",
        "mochilas": "Tenemos gran variedad de mochilas escolares resistentes (marca Golden Star y más) para todos los grados.",
        "ropa": "Contamos con ropa de calidad para toda la familia: damas, caballeros, niños, niñas y vestidos para ocasiones especiales.",
        "facebook": "Puedes ver nuestras fotos y novedades en Facebook: https://www.facebook.com/profile.php?id=61578993366170"
    }
    
    resultado = datos.get(tema.lower(), "Ofrecemos uniformes escolares (CECyTE, primaria, secundaria), mochilas Golden Star y ropa para toda la familia.")
    return {"informacion": resultado}

def guardar_apartado_o_pedido(nombre_cliente: str, telefono: str, articulo_y_talla: str) -> dict:
    """
    Registra un apartado de ropa, uniforme o mochila en Google Sheets para que el personal de la tienda lo separe.
    
    Args:
        nombre_cliente: Nombre del cliente que aparta.
        telefono: Número de WhatsApp del cliente.
        articulo_y_talla: Descripción exacta de lo que desea apartar (ej: 'Playera CECyTE Talla M' o 'Mochila Golden Star azul').
    """
    try:
        guardar_fila_sheets(
            pestana="Apartados_y_Pedidos",
            datos=[
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                nombre_cliente,
                telefono,
                articulo_y_talla,
                "Pendiente de Entrega / Pago"
            ]
        )
        return {
            "status": "success",
            "mensaje": f"Apartado registrado con éxito para {nombre_cliente}: {articulo_y_talla}."
        }
    except Exception as e:
        return {"status": "error", "mensaje": str(e)}

def agendar_visita_o_cita(nombre_cliente: str, telefono: str, fecha: str, hora: str, motivo: str) -> dict:
    """
    Agenda una visita o cita en Google Calendar (ej: ir a medirse uniformes o recoger pedido).
    
    Args:
        nombre_cliente: Nombre del cliente.
        telefono: Número de WhatsApp del cliente.
        fecha: Fecha en formato AAAA-MM-DD (ej: 2026-08-20).
        hora: Hora en formato 24h (ej: 17:00).
        motivo: Motivo de la visita (ej: 'Medición de uniforme CECyTE').
    """
    try:
        fecha_hora_str = f"{fecha} {hora}"
        inicio = datetime.strptime(fecha_hora_str, "%Y-%m-%d %H:%M")
        fin = inicio + timedelta(minutes=30)
        
        insertar_evento_calendar(
            titulo=f"Visita: {nombre_cliente} ({motivo})",
            fecha_inicio_iso=inicio.isoformat(),
            fecha_fin_iso=fin.isoformat(),
            descripcion=f"Cliente: {nombre_cliente}\nTeléfono: {telefono}\nMotivo: {motivo}"
        )
        
        guardar_fila_sheets(
            pestana="Visitas_Agendadas",
            datos=[
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                nombre_cliente,
                telefono,
                f"{fecha} a las {hora}",
                motivo
            ]
        )
        return {"status": "success", "mensaje": f"Visita confirmada para el {fecha} a las {hora}."}
    except Exception as e:
        return {"status": "error", "mensaje": str(e)}

# Lista de herramientas entregadas a Gemini
HERRAMIENTAS_AGENTE = [
    consultar_informacion_tienda,
    guardar_apartado_o_pedido,
    agendar_visita_o_cita
]
