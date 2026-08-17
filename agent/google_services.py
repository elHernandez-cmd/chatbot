import os
import json
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets"
]

CREDS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
CREDS_JSON_RAW = os.getenv("GOOGLE_CREDENTIALS_JSON")
ID_CALENDARIO = os.getenv("GOOGLE_CALENDAR_ID", "primary")
NOMBRE_HOJA_SHEETS = os.getenv("GOOGLE_SHEET_NAME", "CRM_WhatsApp")

def get_google_services():
    """Inicializa y retorna los clientes de Google Calendar y Google Sheets."""
    try:
        creds = None
        if CREDS_JSON_RAW:
            info = json.loads(CREDS_JSON_RAW)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        elif os.path.exists(CREDS_FILE):
            creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
            
        if not creds:
            return None, None
            
        calendar_service = build("calendar", "v3", credentials=creds)
        sheets_client = gspread.authorize(creds)
        return calendar_service, sheets_client
    except Exception as e:
        print(f"Error al conectar con Google Workspace: {e}")
        return None, None

def insertar_evento_calendar(titulo: str, fecha_inicio_iso: str, fecha_fin_iso: str, descripcion: str = ""):
    """Inserta una cita directamente en Google Calendar."""
    calendar_service, _ = get_google_services()
    if not calendar_service:
        print(f"[SIMULACIÓN CALENDAR] Evento: {titulo} ({fecha_inicio_iso} a {fecha_fin_iso})")
        return "calendar_simulado"
        
    evento = {
        "summary": titulo,
        "description": descripcion,
        "start": {"dateTime": fecha_inicio_iso, "timeZone": "America/Mexico_City"},
        "end": {"dateTime": fecha_fin_iso, "timeZone": "America/Mexico_City"},
    }
    evento_creado = calendar_service.events().insert(calendarId=ID_CALENDARIO, body=evento).execute()
    return evento_creado.get("htmlLink")

def guardar_fila_sheets(pestana: str, datos: list):
    """Guarda una fila en Google Sheets en la pestaña especificada."""
    _, sheets_client = get_google_services()
    if not sheets_client:
        print(f"[SIMULACIÓN SHEETS] Guardando en pestaña '{pestana}': {datos}")
        return True
        
    sheet = sheets_client.open(NOMBRE_HOJA_SHEETS)
    try:
        worksheet = sheet.worksheet(pestana)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=pestana, rows="100", cols="10")
    
    worksheet.append_row(datos)
    return True
