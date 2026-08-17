import sys
import os

# Asegurar que los módulos de la carpeta raíz sean accesibles en Vercel
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
