import os
import re
import json
import unicodedata
from datetime import datetime

# Archivos de persistencia
BLOCKED_FILE = "/tmp/bloqueados_rosymar.json" if os.path.exists("/tmp") else os.path.join(os.path.dirname(__file__), "bloqueados_rosymar.json")
STRIKES_FILE = "/tmp/strikes_rosymar.json" if os.path.exists("/tmp") else os.path.join(os.path.dirname(__file__), "strikes_rosymar.json")

# Lista exhaustiva de raíces, groserías, albures e insultos comunes en México
PATRONES_GROSERIAS_MEXICO = [
    # Ch*ngar y derivados
    r"\bch+i+n+g+[a-z0-9]*\b",
    r"\bch+e+n+g+[a-z0-9]*\b",
    r"\bch+i+n+g+o+n+[a-z0-9]*\b",
    r"\bch+i+n+g+a+d+[a-z0-9]*\b",
    r"\bch+i+n+g+a+t+e\b",
    r"\bch+i+n+g+a+d+e+r+a+[a-z0-9]*\b",
    r"\bch+i+n+g+a tu m+a+d+r+e\b",
    
    # P*ndejo y derivados
    r"\bp+e+n+d+e+j+[a-z0-9]*\b",
    r"\bp+n+d+j+[a-z0-9]*\b",
    r"\bp+e+n+d+e+x+[a-z0-9]*\b",
    
    # P*to, p*ta y derivados
    r"\bp+u+t+[oa]s?\b",
    r"\bp+u+t+i+z+a\b",
    r"\bp+u+t+a+z+o\b",
    r"\bp+u+t+a m+a+d+r+e\b",
    r"\bh+i+j+[oa] d+e p+u+t+a\b",
    r"\bh+i+j+[oa] d+e s+u p+u+t+a m+a+d+r+e\b",
    
    # V*rga y derivados
    r"\bv+e+r+g+[a-z0-9]*\b",
    r"\bv+r+g+[a-z0-9]*\b",
    r"\bv+e+r+g+a+z+o[s]?\b",
    r"\ba+l+a+v+e+r+g+a\b",
    r"\ba la verga\b",
    r"\bvete a la verga\b",
    r"\bme vale verga\b",
    r"\bvaleverga\b",
    
    # M*madas y derivados
    r"\bm+a+m+a+d+[a-z0-9]*\b",
    r"\bm+a+m+[oó]n+[a-z0-9]*\b",
    r"\bm+a+m+a+r\b",
    r"\bm+a+m+e+s\b",
    r"\bno mames\b",
    r"\bno mame\b",
    r"\bno mamen\b",
    r"\bchupa+[a-z0-9]*\b",
    
    # C*lero, c*lo y derivados
    r"\bc+u+l+e+r+[a-z0-9]*\b",
    r"\bc+u+l+[oa]s?\b",
    r"\bc+u+l+i+t+o\b",
    r"\bo+j+e+t+[a-z0-9]*\b",
    
    # P*nche y derivados ofensivos
    r"\bp+i+n+c+h+e+[s]?\b",
    
    # C*brón y derivados
    r"\bc+a+b+r+[oó]n+[a-z0-9]*\b",
    
    # Insultos generales
    r"\be+s+t+[uú]+p+i+d+[a-z0-9]*\b",
    r"\bi+d+i+o+t+[a-z0-9]*\b",
    r"\bi+m+b+[eé]+c+i+l+[a-z0-9]*\b",
    r"\bb+a+b+o+s+[a-z0-9]*\b",
    r"\bt+a+r+a+d+[a-z0-9]*\b",
    r"\bm+e+n+s+[oa]s?\b",
    r"\bz+o+q+u+e+t+[a-z0-9]*\b",
    r"\bz+o+p+e+n+c+[a-z0-9]*\b",
    r"\bm+i+e+r+d+[a-z0-9]*\b",
    r"\bc+o+m+e+m+i+e+r+d+a\b",
    r"\ba+s+q+u+e+r+o+s+[a-z0-9]*\b",
    r"\bp+e+r+r+a\b",
    r"\bz+o+r+r+a\b",
    r"\bm+u+g+r+o+s+[a-z0-9]*\b",
    r"\bj+o+t+[oa]s?\b",
    r"\bm+a+r+i+c+[oó]n+[a-z0-9]*\b",
    r"\bm+a+r+i+c+a+[s]?\b",
    r"\bl+[aá]+r+g+a+t+e\b",
    r"\blarguese\b",
    
    # Abreviaturas y siglas ofensivas comunes en México
    r"\bchsm\b",
    r"\bctm\b",
    r"\bchptm\b",
    r"\balv\b",
    r"\bhdp\b",
    r"\bvlv\b",
    r"\bcsm\b"
]

REGEX_GROSERIAS = [re.compile(p, re.IGNORECASE) for p in PATRONES_GROSERIAS_MEXICO]

def normalizar_texto(texto: str) -> str:
    """Normaliza texto removiendo acentos, caracteres especiales y sustituciones leet."""
    if not texto:
        return ""
        
    t = texto.lower()
    # Reemplazos leetspeak comunes
    reemplazos = {
        "@": "a", "4": "a",
        "3": "e",
        "1": "i", "!": "i", "|": "i",
        "0": "o",
        "5": "s", "$": "s",
        "7": "t",
        "*": ""
    }
    for k, v in reemplazos.items():
        t = t.replace(k, v)
        
    # Remover diacríticos/acentos
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    
    # Limpiar espacios repetidos y símbolos extraños entre letras
    t_sin_puntos = re.sub(r'([a-z])[\.\-\_\,\s]+([a-z])', r'\1\2', t)
    return f"{t} {t_sin_puntos}"

def contiene_groserias(texto: str) -> bool:
    """Detecta si el mensaje contiene groserías, albures pesados o insultos comunes en México."""
    if not texto:
        return False
    texto_norm = normalizar_texto(texto)
    for regex in REGEX_GROSERIAS:
        if regex.search(texto_norm):
            return True
    return False

def _leer_json(ruta: str) -> dict:
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _guardar_json(ruta: str, datos: dict):
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error escribiendo {ruta}: {e}")

def es_usuario_bloqueado(sender_id: str) -> bool:
    """Verifica si un usuario se encuentra en la lista negra de bloqueados."""
    if not sender_id:
        return False
    bloqueados = _leer_json(BLOCKED_FILE)
    return str(sender_id) in bloqueados

def bloquear_usuario(sender_id: str, motivo: str = "Insultos o groserías reiteradas"):
    """Bloquea permanentemente a un usuario para no responderle ningún mensaje."""
    if not sender_id:
        return
    bloqueados = _leer_json(BLOCKED_FILE)
    bloqueados[str(sender_id)] = {
        "fecha_bloqueo": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "motivo": motivo
    }
    _guardar_json(BLOCKED_FILE, bloqueados)
    print(f"⛔ USUARIO BLOQUEADO: {sender_id} - Motivo: {motivo}")

def registrar_infraccion_groseria(sender_id: str) -> bool:
    """
    Registra una infracción por grosería/insulto.
    Si acumula 2 infracciones o más, es bloqueado automáticamente.
    Retorna True si fue bloqueado en este intento.
    """
    if not sender_id:
        return False
    
    strikes = _leer_json(STRIKES_FILE)
    cuenta = strikes.get(str(sender_id), 0) + 1
    strikes[str(sender_id)] = cuenta
    _guardar_json(STRIKES_FILE, strikes)
    
    print(f"⚠️ INFRACCIÓN POR GROSERÍA: Usuario {sender_id} (Infracción #{cuenta})")
    
    if cuenta >= 2:
        bloquear_usuario(sender_id, motivo=f"Acumuló {cuenta} mensajes con groserías o insultos")
        return True
    return False

def obtener_usuarios_bloqueados() -> dict:
    """Retorna el diccionario de usuarios actualmente bloqueados."""
    return _leer_json(BLOCKED_FILE)

def desbloquear_usuario(sender_id: str) -> bool:
    """Desbloquea a un usuario y reinicia sus infracciones."""
    if not sender_id:
        return False
    s_id = str(sender_id).strip()
    bloqueados = _leer_json(BLOCKED_FILE)
    removido = False
    if s_id in bloqueados:
        del bloqueados[s_id]
        _guardar_json(BLOCKED_FILE, bloqueados)
        removido = True
    
    strikes = _leer_json(STRIKES_FILE)
    if s_id in strikes:
        del strikes[s_id]
        _guardar_json(STRIKES_FILE, strikes)
        removido = True
        
    return removido
