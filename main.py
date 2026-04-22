import os
import time
import requests
import threading
from datetime import datetime, timedelta # <-- Nueva importación
from flask import Flask

app = Flask(__name__)

# --- CONFIGURACIÓN DEL BOT ---
TOKEN = "8107696402:AAEwS9w1AcFYY8jY-vrENEtcvkEcAjuq-QI"
CHAT_ID = -1003994301891 

MEXICO_BOUNDS = {
    "lat_min": 14.5, "lat_max": 32.7, 
    "lon_min": -118.4, "lon_max": -86.7
}

def monitorear_sismos():
    vistos = set()
    print("Iniciando monitoreo con hora local...")
    
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
                        props = sismo['properties']
                        mag = props['mag']
                        lugar = props['place']
                        
                        # --- CONVERSIÓN DE HORA ---
                        # Convertimos milisegundos a objeto datetime (UTC)
                        fecha_utc = datetime.fromtimestamp(props['time'] / 1000.0)
                        # Ajustamos a la hora de México (UTC -6 horas)
                        # Nota: Si es horario de verano, cámbialo a -5
                        fecha_mex = fecha_utc - timedelta(hours=6)
                        hora_formateada = fecha_mex.strftime('%d/%m/%Y %H:%M:%S')

                        if mag >= 1.0: # Mantengo 1.0 para tu prueba, cámbialo a 4.0 después
                            mensaje = (f"⚠️ **SISMO DETECTADO (USGS)**\n\n"
                                       f"📈 **Magnitud:** {mag}\n"
                                       f"🕒 **Hora México:** {hora_formateada}\n"
                                       f"📍 **Lugar:** {lugar}\n"
                                       f"🌐 [Más detalles aquí]({props['url']})")
                            
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
    return "🌐 Bot con registro de hora activo..."

if __name__ == "__main__":
    t = threading.Thread(target=monitorear_sismos, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
