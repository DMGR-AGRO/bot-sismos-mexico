import os
import time
import requests
import threading
from flask import Flask

# Inicializar la aplicación Flask
app = Flask(__name__)

# --- CONFIGURACIÓN DEL BOT ---
TOKEN = "8107696402:AAEwS9w1AcFYY8jY-vrENEtcvkEcAjuq-QI"
CHAT_ID = -1003994301891  # Tu ID confirmado

# Coordenadas geográficas de México
MEXICO_BOUNDS = {
    "lat_min": 14.5, 
    "lat_max": 32.7, 
    "lon_min": -118.4, 
    "lon_max": -86.7
}

def monitorear_sismos():
    vistos = set()
    print("Iniciando monitoreo de prueba (Mag >= 1.0)...")
    
    while True:
        try:
            url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            for sismo in data['features']:
                coords = sismo['geometry']['coordinates']
                lon, lat, s_id = coords[0], coords[1], sismo['id']
                
                if (MEXICO_BOUNDS["lat_min"] <= lat <= MEXICO_BOUNDS["lat_max"] and 
                    MEXICO_BOUNDS["lon_min"] <= lon <= MEXICO_BOUNDS["lon_max"]):
                    
                    if s_id not in vistos:
                        mag = sismo['properties']['mag']
                        lugar = sismo['properties']['place']
                        
                        # CAMBIO DE PRUEBA: Bajamos a 1.0 para ver mensajes rápido
                        if mag >= 1.0:
                            mensaje = (f"⚠️ **SISMO DETECTADO (PRUEBA)**\n\n"
                                       f"📈 **Magnitud:** {mag}\n"
                                       f"📍 **Lugar:** {lugar}\n"
                                       f"🌐 [Más detalles]({sismo['properties']['url']})")
                            
                            requests.post(
                                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                                data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
                            )
                        
                        vistos.add(s_id)
                        
        except Exception as e:
            print(f"Error: {e}")
            
        time.sleep(60)

@app.route('/')
def home():
    return "🌐 Bot en MODO PRUEBA (Mag 1.0) activo..."

if __name__ == "__main__":
    t = threading.Thread(target=monitorear_sismos, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
