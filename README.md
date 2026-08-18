# 🤖 Chatbot Novedades Rosymar (Facebook Messenger + Gemini AI)

Bot inteligente con razonamiento y atención al cliente humana para la tienda **Novedades Rosymar** (Villa Ignacio Allende, Centla, Tabasco), integrado con **Google Gemini AI**, **Facebook Messenger**, **Google Sheets** y **Google Calendar**.

---

## 🚀 Opciones para Lanzar a Producción (Sin problemas de CLI)

Si el comando `vercel` desde la terminal te da problemas de autenticación o bloqueo de navegador, tienes **3 alternativas directas y garantizadas**:

---

### Opción 1: Despliegue desde el Panel Web de Vercel (Recomendado ⭐)
No requiere instalar ni autorizar nada en la consola:
1. Sube tu código a un repositorio en **GitHub** (ejemplo: `chatbot-rosymar`).
2. Entra a tu cuenta en [vercel.com](https://vercel.com/dashboard).
3. Haz clic en **"Add New..." ➔ "Project"**.
4. Selecciona tu repositorio de GitHub y haz clic en **Import**.
5. En la sección **Environment Variables**, agrega las variables de tu `.env`:
   - `GEMINI_API_KEY`: Tu clave de Gemini.
   - `FB_PAGE_ACCESS_TOKEN`: Tu token de página de Facebook.
   - `FB_VERIFY_TOKEN`: `RosymarTokenSeguro123` (o el que elijas).
   - *(Opcional)* `GOOGLE_CREDENTIALS_JSON`: El JSON de tu cuenta de servicio si usas Sheets/Calendar.
6. Haz clic en **Deploy**.
7. ¡Listo! Vercel te dará una URL HTTPS como: `https://tu-proyecto.vercel.app`.

---

### Opción 2: Despliegue con Token de Vercel por CLI
Si deseas usar la terminal sin que abra navegador para autorizar:
1. Ve a [vercel.com/account/tokens](https://vercel.com/account/tokens) y crea un nuevo Token (dale cualquier nombre, ej: `token-chatbot`).
2. Copia el token generado.
3. En tu terminal ejecuta:
   ```bash
   vercel --prod --token TU_TOKEN_AQUI
   ```

---

### Opción 3: Despliegue Gratuito en Render.com
1. Crea una cuenta gratuita en [render.com](https://render.com).
2. Haz clic en **New + ➔ Web Service** y conecta tu repositorio de GitHub.
3. Configuración:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Agrega tus Variables de Entorno y haz clic en **Create Web Service**.

---

### Opción 4: Pruebas Inmediatas en Local (con Túnel HTTPS)
Para probar que Facebook Messenger responda en vivo desde tu computadora:
1. Inicia el servidor local:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
2. En otra terminal, abre un túnel HTTPS público (ejemplo con `ngrok` o `localtunnel`):
   ```bash
   npx localtunnel --port 8000
   # o si tienes ngrok:
   ngrok http 8000
   ```
3. Copia la URL HTTPS que te entregue (ejemplo: `https://rosymar-bot.loca.lt`).

---

## 🔗 Configuración del Webhook en Meta for Developers

Una vez que tengas tu URL pública de Vercel, Render o del túnel local:

1. Ve a [developers.facebook.com](https://developers.facebook.com/apps/) y entra a tu App.
2. En el menú lateral ve a **Messenger ➔ Configuración**.
3. En la sección **Webhooks**, haz clic en **Editar / Configurar Webhook**:
   - **URL de devolución de llamada (Callback URL)**: `https://TU_URL_DE_VERCEL_O_TUNEL/webhook`
   - **Token de verificación (Verify Token)**: `RosymarTokenSeguro123` (debe coincidir con `FB_VERIFY_TOKEN`).
4. Haz clic en **Verificar y Guardar**.
5. En los campos de suscripción de la página, activa:
   - ✅ `messages`
   - ✅ `messaging_postbacks`
6. En la sección **Tokens de Acceso**, selecciona tu página de Facebook de *Novedades Rosymar* y genera el `FB_PAGE_ACCESS_TOKEN` para pegarlo en tus variables de entorno.

---

## 👑 Comandos de Administrador (Actualización de Existencias en Vivo)

Los administradores de la página pueden consultar y actualizar el inventario y existencias en tiempo real escribiendo directamente en el chat de Messenger:

* **Actualizar existencias:**
  ```text
  /actualizar RosymarAdmin2026 Llegaron faldas CECyTE talla 32 y se agotaron los pants deportivos talla Grande.
  ```
  *(Una vez que envías el PIN la primera vez, tu usuario queda registrado como administrador y en los siguientes mensajes solo necesitas escribir `/actualizar <tus existencias>` sin volver a poner el PIN).*

* **Ver inventario actual registrado:**
  ```text
  /verinventario
  ```
  *(O con PIN si es la primera vez: `/verinventario RosymarAdmin2026`)*

* **Ver apartados activos y días transcurridos:**
  ```text
  /apartados
  ```

* **Marcar apartado como liquidado/entregado:**
  ```text
  /liquidar ID_APARTADO
  ```

* **Ver usuarios bloqueados por groserías:**
  ```text
  /bloqueados
  ```

* **Desbloquear usuario:**
  ```text
  /desbloquear ID_USUARIO
  ```

---

## 📦 Sistema de Apartados y Recordatorio Automático de 15 Días

* **Registro en Memoria y Sheets:** Cuando un cliente solicita un apartado, el bot guarda el registro en su memoria persistente y en Google Sheets.
* **Política de 15 Días:** El sistema lleva el conteo exacto de días transcurridos desde que se apartó la prenda o producto con anticipo de $50 o $100 pesos.
* **Envío Automático de Recordatorio:** Al cumplirse los **15 días de plazo**, el bot le envía un mensaje personalizado y cordial al cliente en Facebook Messenger invitándolo a pasar a la tienda física a liquidar y recoger su artículo.

---

## 🛡️ Moderación, Filtro de Groserías y Horario Nocturno

* **Filtro de Groserías e Insultos (México):** El bot detecta malas palabras, albures pesados e insultos comunes en México. Si un usuario envía un mensaje ofensivo, el bot **no responde**.
* **Bloqueo Automático de Usuarios:** Si un usuario envía insultos reiterados, el bot lo bloquea permanentemente y descarta todos sus mensajes futuros.
* **Horario de Atención Inteligente:**
  * **Activo:** De **6:00 AM a 7:59 PM** (hora local de Tabasco / Centro de México).
  * **Nocturno (después de 7:59 PM hasta las 6:00 AM):** El bot no responde de noche y guarda los mensajes en una cola segura para responderles automáticamente a los clientes a partir de las 6:00 AM.

---

## 📂 Estructura del Proyecto

```text
chatbot/
├── .env.example             # Plantilla de variables de entorno (con PIN de admin)
├── requirements.txt         # Dependencias de Python (FastAPI, Gemini, etc.)
├── vercel.json              # Configuración de Serverless Rewrite para Vercel
├── main.py                  # API FastAPI, Webhook, Moderación, Horarios y Recordatorios
├── README.md                # Documentación oficial del proyecto
├── api/
│   └── index.py             # Entrada serverless para Vercel
└── agent/
    ├── gemini_agent.py      # Agente inteligente de Gemini (Prompt, Conocimiento y Herramientas)
    └── services.py          # Servicios unificados (Moderación, Existencias, Apartados, Horarios y Google)
```
