import os
import time
import requests
import threading
from flask import Flask

# Inicializar la aplicación Flask
app = Flask(__name__)

# --- CONFIGURACIÓN DEL BOT ---
# Tu Token y Canal de Telegram
TOKEN = "8107696402:AAEwS9w1AcFYY8jY-vrENEtcvkEcAjuq-QI"
CHAT_ID = "@AgroDMGRbot"

# Coordenadas geográficas que cubren México (Bounding Box)
MEXICO_BOUNDS = {
    "lat_min": 14.5, 
    "lat_max": 32.7, 
    "lon_min": -118.4, 
    "lon_max": -86.7
}

def monitorear_sismos():
    """Hilo secundario que consulta la API de la USGS cada 60 segundos."""
    vistos = set()
    print("Iniciando monitoreo de sismos en México...")
    
    while True:
        try:
            # Consultar el feed de la última hora de la USGS
            url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            for sismo in data['features']:
                coords = sismo['geometry']['coordinates']
                lon, lat, s_id = coords[0], coords[1], sismo['id']
                
                # 1. Filtrar si está en el área de México
                if (MEXICO_BOUNDS["lat_min"] <= lat <= MEXICO_BOUNDS["lat_max"] and 
                    MEXICO_BOUNDS["lon_min"] <= lon <= MEXICO_BOUNDS["lon_max"]):
                    
                    # 2. Verificar si no lo hemos reportado ya
                    if s_id not in vistos:
                        mag = sismo['properties']['mag']
                        lugar = sismo['properties']['place']
                        
                        # 3. Solo avisar si es magnitud relevante (>= 4.0)
                        if mag >= 4.0:
                            mensaje = (f"⚠️ **SISMO DETECTADO (USGS)**\n\n"
                                       f"📈 **Magnitud:** {mag}\n"
                                       f"📍 **Lugar:** {lugar}\n"
                                       f"🌐 [Más detalles aquí]({sismo['properties']['url']})")
                            
                            requests.post(
                                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                                data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
                            )
                        
                        # Añadir a la lista de vistos para no repetir
                        vistos.add(s_id)
                        
        except Exception as e:
            print(f"Error en el monitoreo: {e}")
            
        # Esperar 60 segundos para la siguiente consulta
        time.sleep(60)

# --- RUTAS DE LA WEB APP ---

@app.route('/')
def home():
    """Página principal para que Render y UptimeRobot vean que el bot está vivo."""
    return "🌐 Bot de Sismos México (USGS) está activo y monitoreando..."

@app.route('/health')
def health():
    return {"status": "ok"}, 200

# --- INICIO DEL SERVIDOR ---

if __name__ == "__main__":
    # Iniciar el hilo del bot antes de arrancar el servidor web
    t = threading.Thread(target=monitorear_sismos, daemon=True)
    t.start()
    
    # Render usa la variable de entorno PORT. Si no existe, usa el 5000 por defecto.
    port = int(os.environ.get("PORT", 5000))
    
    # Escuchar en 0.0.0.0 es vital para que Render pueda conectar con el exterior
    app.run(host='0.0.0.0', port=port)
