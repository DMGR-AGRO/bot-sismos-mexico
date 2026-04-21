from flask import Flask
import threading
import requests
import time

app = Flask(__name__)

# --- CONFIGURACIÓN DEL BOT ---
TOKEN = "8107696402:AAEwS9w1AcFYY8jY-vrENEtcvkEcAjuq-QI"
CHAT_ID = "@AgroDMGRbot"
MEXICO_BOUNDS = {"lat_min": 14.5, "lat_max": 32.7, "lon_min": -118.4, "lon_max": -86.7}

def monitorear_sismos():
    vistos = set()
    while True:
        try:
            url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
            data = requests.get(url).json()
            for s in data['features']:
                coords = s['geometry']['coordinates']
                lon, lat, s_id = coords[0], coords[1], s['id']
                
                if (MEXICO_BOUNDS["lat_min"] <= lat <= MEXICO_BOUNDS["lat_max"] and 
                    MEXICO_BOUNDS["lon_min"] <= lon <= MEXICO_BOUNDS["lon_max"]):
                    
                    if s_id not in vistos:
                        mag = s['properties']['mag']
                        if mag >= 4.0:
                            msg = f"⚠️ **SISMO USGS (MÉXICO)**\nMagnitud: {mag}\nLugar: {s['properties']['place']}"
                            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                          data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                        vistos.add(s_id)
        except:
            pass
        time.sleep(60)

# Esto inicia el bot en un hilo separado para que no bloquee la web
threading.Thread(target=monitorear_sismos, daemon=True).start()

@app.route('/')
def home():
    return "Bot de Sismos México está activo y monitoreando..."

if __name__ == "__main__":
    app.run()
